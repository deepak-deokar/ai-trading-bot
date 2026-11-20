from datetime import date

import numpy as np
import pytest

from trading_bot.backtesting.daily_model import DayRow
from trading_bot.backtesting.move_strategy import breakout_trade
from trading_bot.backtesting.session_window import CostModel, Sizing

COSTS = CostModel(
    extra_spread_per_oz=0.20, commission_per_lot=8.0, slippage_per_oz=0.10
)
HALF = 0.15


def bars_from(
    mids: list[float], highs: list[float] | None = None, lows: list[float] | None = None
) -> dict[str, np.ndarray]:
    m = np.array(mids)
    h = np.array(highs) if highs else m
    lo = np.array(lows) if lows else m
    bars = {"minute_utc": 1_700_000_000 + np.arange(len(m), dtype=np.int64) * 60}
    for side, sign in (("bid", -1), ("ask", 1)):
        bars[f"{side}_open"] = m + sign * HALF
        bars[f"{side}_close"] = m + sign * HALF
        bars[f"{side}_high"] = h + sign * HALF
        bars[f"{side}_low"] = lo + sign * HALF
    return bars


def row(n: int) -> DayRow:
    # 08:00 mid 2000, ADR 10 (risk field = half of it); k=0.2 -> levels 2002 / 1998
    return DayRow(date(2024, 1, 10), 0, n - 1, 2000.0, 5.0, (), 0)


def test_buy_breakout_hits_target() -> None:
    mids = [2000.0, 2001.0, 2002.5, 2003.0, 2008.0, 2013.0] + [2013.0] * 4
    t = breakout_trade(bars_from(mids), row(len(mids)), 0.2, 2.0, COSTS, Sizing())
    assert t is not None and t.direction == 1 and t.entry_minute == 2
    assert t.entry == pytest.approx(2002.5 + HALF + 0.20)
    assert t.stop == 1998.0 and t.exit_reason == "target"
    assert t.exit == pytest.approx(2013.0 - HALF - 0.20)


def test_buy_then_stopped_at_the_other_level() -> None:
    mids = [2000.0, 2002.5, 2001.0, 1997.0] + [1997.0] * 4
    t = breakout_trade(bars_from(mids), row(len(mids)), 0.2, 2.0, COSTS, Sizing())
    assert t is not None and t.exit_reason == "stop"
    assert t.exit == pytest.approx(1997.0 - HALF - 0.20)  # gapped below 1998
    assert t.pnl_usd < 0


def test_both_levels_in_one_minute_or_none_gives_no_trade() -> None:
    mids = [2000.0, 2000.0, 2000.0]
    both = bars_from(
        mids, highs=[2000.0, 2003.0, 2000.0], lows=[2000.0, 1997.0, 2000.0]
    )
    assert breakout_trade(both, row(3), 0.2, 2.0, COSTS, Sizing()) is None
    quiet = bars_from([2000.0, 2000.5, 1999.5])
    assert breakout_trade(quiet, row(3), 0.2, 2.0, COSTS, Sizing()) is None
