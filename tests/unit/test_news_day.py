from datetime import UTC, date, datetime, time
from pathlib import Path

import numpy as np
import pytest

from trading_bot.backtesting.news_day import (
    NewsEvent,
    NewsRule,
    control_days,
    load_events,
    run_news,
    simulate_event,
)
from trading_bot.backtesting.session_window import CostModel, Sizing

COSTS = CostModel(
    extra_spread_per_oz=0.20, commission_per_lot=8.0, slippage_per_oz=0.10
)
HALF = 0.15
PF = 0.20  # extra spread / 2 + slippage
CPI = NewsEvent(date(2024, 1, 11), "cpi", time(8, 30))  # 08:30 NY = 13:30 UTC
START = int(datetime(2024, 1, 11, 13, 30, tzinfo=UTC).timestamp())
EXIT_MIN = 210  # 12:00 NY is 210 minutes after 08:30


def bars_from(mids: list[float]) -> dict[str, np.ndarray]:
    m = np.array(mids)
    bars = {"minute_utc": START + np.arange(len(m), dtype=np.int64) * 60}
    for side, sign in (("bid", -1), ("ask", 1)):
        for part in ("open", "high", "low", "close"):
            bars[f"{side}_{part}"] = m + sign * HALF
    return bars


# release candle: opens 2000, dips to 1998, closes 2005 (an up move)
RELEASE = [2000.0, 1998.0] + [2003.0] * 12 + [2005.0]


def day(after: list[float]) -> dict[str, np.ndarray]:
    rest = after + [after[-1]] * (EXIT_MIN + 30 - 15 - len(after))
    return bars_from(RELEASE + rest)


def test_momentum_buys_the_move_and_exits_at_noon() -> None:
    t = simulate_event(day([2006.0]), CPI, NewsRule("momentum", None), COSTS, Sizing())
    assert t is not None and t.direction == 1
    assert t.entry_minute == 15 and t.stop == 1998.0
    assert t.entry == pytest.approx(2006.0 + HALF + PF)
    assert t.exit_reason == "time_exit" and t.exit_bar == EXIT_MIN - 1
    assert t.target is None


def test_fade_sells_and_is_stopped_above_the_release_high() -> None:
    t = simulate_event(
        day([2004.0] * 5 + [2010.0]), CPI, NewsRule("fade", None), COSTS, Sizing()
    )
    assert t is not None and t.direction == -1 and t.stop == 2005.0
    assert t.exit_reason == "stop" and t.exit_bar == 20
    assert t.exit == pytest.approx(2010.0 + HALF + PF)  # gapped past the stop
    assert t.pnl_usd < 0


def test_momentum_target_at_two_r() -> None:
    after = [2006.0] * 3 + [2030.0]
    t = simulate_event(day(after), CPI, NewsRule("momentum", 2.0), COSTS, Sizing())
    assert t is not None and t.exit_reason == "target"
    assert t.target == pytest.approx(t.entry + 2 * (t.entry - 1998.0))
    assert t.pnl_usd > 0


def test_flat_release_candle_or_missing_data_gives_no_trade() -> None:
    flat = bars_from([2000.0] * 240)
    assert (
        simulate_event(flat, CPI, NewsRule("momentum", None), COSTS, Sizing()) is None
    )
    short = bars_from(RELEASE[:10])
    assert (
        simulate_event(short, CPI, NewsRule("momentum", None), COSTS, Sizing()) is None
    )


def test_run_news_counts_only_events_with_data() -> None:
    other = NewsEvent(date(2024, 1, 12), "nfp", time(8, 30))
    trades, usable = run_news(
        day([2006.0]),
        [CPI, other],
        NewsRule("momentum", None),
        COSTS,
        Sizing(),
        range(2024, 2025),
    )
    assert usable == 1 and len(trades) == 1


def test_load_events_keeps_the_first_event_of_a_day(tmp_path: Path) -> None:
    p = tmp_path / "ev.csv"
    p.write_text(
        "# comment\ndate,event,time_ny\n"
        "2024-06-12,fomc,14:00\n2024-06-12,cpi,08:30\n2024-06-07,nfp,08:30\n"
    )
    evs = load_events(p)
    assert [(e.day.isoformat(), e.kind) for e in evs] == [
        ("2024-06-07", "nfp"),
        ("2024-06-12", "cpi"),
    ]
    assert evs[1].exit_time == time(12, 0)


def test_control_days_skip_events_and_weekends() -> None:
    start = int(datetime(2024, 1, 10, 12, 0, tzinfo=UTC).timestamp())
    minutes = start + np.arange(0, 4 * 24 * 60, dtype=np.int64) * 60  # Wed..Sun
    ctl = control_days({"minute_utc": minutes}, [CPI], range(2024, 2025))
    assert [e.day for e in ctl] == [date(2024, 1, 10), date(2024, 1, 12)]
