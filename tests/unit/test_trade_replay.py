import json
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from trading_bot.backtesting.session_window import CostModel, Sizing
from trading_bot.backtesting.sweep_strategy import (
    SweepRule,
    TradingDay,
    Zones,
    simulate_day,
)
from trading_bot.backtesting.trade_replay import (
    DATA_MARKER,
    candles,
    cost_split,
    render_page,
    replay_record,
    sweep_context,
)

COSTS = CostModel(
    extra_spread_per_oz=0.20, commission_per_lot=8.0, slippage_per_oz=0.10
)
HALF = 0.15
ZONES = Zones(
    supply_bottom=2010.0, supply_top=2015.0, demand_bottom=1985.0, demand_top=1990.0
)
DAY_START = int(datetime(2024, 1, 9, 23, 0, tzinfo=UTC).timestamp())  # 18:00 New York
SETUP = [
    (2005.0, 2008.0, 2004.0, 2007.0),
    (2007.0, 2011.0, 2006.0, 2010.0),
    (2010.0, 2013.0, 2008.0, 2009.0),  # sweeps 2011 into supply, closes back below
    (2009.0, 2010.0, 2006.0, 2007.0),  # closes below sweep low 2008 -> sell
]


def candles_to_bars(rows: list[tuple[float, ...]]) -> dict[str, np.ndarray]:
    """Each 15-minute candle = 15 flat minutes: open, high, low, then close x12."""
    mids: list[float] = []
    for o, h, lo, c in rows:
        mids += [o, h, lo] + [c] * 12
    m = np.array(mids)
    bars = {"minute_utc": DAY_START + np.arange(len(m), dtype=np.int64) * 60}
    for side, sign in (("bid", -1), ("ask", 1)):
        for part in ("open", "high", "low", "close"):
            bars[f"{side}_{part}"] = m + sign * HALF
    return bars


TARGET_DAY = SETUP + [(2007.0, 2007.0, 1990.0, 1992.0)] + [(1992.0,) * 4] * 4
STOP_DAY = SETUP + [(2007.0, 2016.0, 2006.0, 2012.0), (2012.0, 2012.0, 2012.0, 2014.0)]
STOP_DAY += [(2014.0,) * 4] * 2


def trade_for(candle_rows, rule):
    bars = candles_to_bars(candle_rows)
    n = len(bars["minute_utc"])
    prev = TradingDay(date(2024, 1, 9), 0, 0, 1990.0, 2015.0, 1985.0, 2010.0)
    today = TradingDay(date(2024, 1, 10), 0, n, 0, 0, 0, 0)
    (t,) = simulate_day(bars, today, ZONES, rule, COSTS, Sizing())
    return bars, [prev, today], t


@pytest.mark.parametrize(
    ("rows", "rule", "at_close"),
    [
        (TARGET_DAY, SweepRule(2.0, "close"), False),
        (STOP_DAY, SweepRule(2.0, "close"), True),
        (STOP_DAY, SweepRule(2.0, "touch"), False),
    ],
)
def test_cost_split_adds_up_to_net(rows, rule, at_close) -> None:
    bars, _, t = trade_for(rows, rule)
    c = cost_split(bars, t, COSTS, exit_at_close=at_close)
    assert c.gross_usd - c.spread_usd - c.extra_usd - c.commission_usd == (
        pytest.approx(t.pnl_usd, abs=1e-6)
    )
    assert c.entry_mid == pytest.approx(2007.0)


def test_five_minute_candles_are_mid_prices() -> None:
    bars = candles_to_bars(SETUP)
    rows, starts = candles(bars, 0, 60, 5, ZoneInfo("America/New_York"))
    assert len(rows) == 12 and list(starts[:3]) == [0, 5, 10]
    # first 15-minute candle: minutes o, h, lo, then closes; first 5 min hold o/h/lo
    assert rows[0][1:] == [2005.0, 2008.0, 2004.0, 2007.0]
    assert rows[0][0] == "18:00"


def test_replay_record_marks_entry_exit_and_setup() -> None:
    bars, days, t = trade_for(TARGET_DAY, SweepRule(2.0, "close"))
    ctx = sweep_context(bars, days, 1, t)
    assert [h.label for h in ctx.highlights] == ["SWEEP", "CONFIRM"]
    assert ctx.zone == (ZONES.supply_bottom, ZONES.supply_top)
    rec = replay_record(
        bars,
        t,
        COSTS,
        exit_at_close=False,
        window=(0, len(bars["minute_utc"])),
        context=ctx,
    )
    assert rec["dir"] == "SELL" and rec["reason"] == "target"
    assert rec["entry_i"] == 12  # entry at minute 60 -> 5-minute candle 12
    assert rec["exit_i"] >= rec["entry_i"]
    sweep, confirm = rec["highlights"]
    assert (sweep["from"], sweep["to"]) == (6, 8)  # 15-minute candle 3
    assert (confirm["from"], confirm["to"]) == (9, 11)
    assert rec["gross"] - rec["spread"] - rec["extra"] - rec["comm"] == (
        pytest.approx(rec["net"], abs=0.02)
    )


def test_window_must_contain_trade() -> None:
    bars, _, t = trade_for(TARGET_DAY, SweepRule(2.0, "close"))
    with pytest.raises(ValueError):
        replay_record(bars, t, COSTS, exit_at_close=False, window=(0, 30))


def test_render_page_embeds_data_safely() -> None:
    bars, days, t = trade_for(TARGET_DAY, SweepRule(2.0, "close"))
    rec = replay_record(
        bars, t, COSTS, exit_at_close=False, window=(0, len(bars["minute_utc"]))
    )
    html = render_page(
        title="Test <replay>",
        subtitle="sub",
        rules=["rule with </script> inside"],
        records=[rec],
        all_trades=[t],
    )
    assert DATA_MARKER not in html
    assert "<title>Test &lt;replay&gt;</title>" in html
    assert "</script> inside" not in html
    start = html.index("const DATA = ") + len("const DATA = ")
    payload = json.loads(html[start : html.index(";\n", start)])
    assert payload["summary"]["n"] == 1
    assert payload["trades"][0]["net"] == rec["net"]
