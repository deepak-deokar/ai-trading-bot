from datetime import UTC, date, datetime

import numpy as np
import pytest

from trading_bot.backtesting.session_window import BAR_FIELDS, CostModel, Sizing
from trading_bot.backtesting.sweep_strategy import (
    HourlyTrend,
    SweepRule,
    TradingDay,
    Zones,
    hourly_trend,
    simulate_day,
    to_15m,
    trading_day_ordinals,
    zones_for,
)

COSTS = CostModel(
    extra_spread_per_oz=0.20, commission_per_lot=8.0, slippage_per_oz=0.10
)
HALF = 0.15
ZONES = Zones(
    supply_bottom=2010.0, supply_top=2015.0, demand_bottom=1985.0, demand_top=1990.0
)
DAY_START = int(datetime(2024, 1, 9, 23, 0, tzinfo=UTC).timestamp())  # 18:00 New York


def epoch(*a: int) -> int:
    return int(datetime(*a, tzinfo=UTC).timestamp())


def candles_to_bars(
    candles: list[tuple[float, float, float, float]],
) -> dict[str, np.ndarray]:
    """Each 15-minute candle = 15 flat minutes: open, high, low, then close x12."""
    mids: list[float] = []
    for o, h, lo, c in candles:
        mids += [o, h, lo] + [c] * 12
    m = np.array(mids)
    bars = {"minute_utc": DAY_START + np.arange(len(m), dtype=np.int64) * 60}
    for side, sign in (("bid", -1), ("ask", 1)):
        for part in ("open", "high", "low", "close"):
            bars[f"{side}_{part}"] = m + sign * HALF
    return bars


def run(
    candles: list[tuple[float, float, float, float]],
    rule: SweepRule,
    trend: HourlyTrend | None = None,
) -> list:
    bars = candles_to_bars(candles)
    day = TradingDay(date(2024, 1, 10), 0, len(bars["minute_utc"]), 0, 0, 0, 0)
    return simulate_day(bars, day, ZONES, rule, COSTS, Sizing(), trend)


SETUP = [
    (2005.0, 2008.0, 2004.0, 2007.0),
    (2007.0, 2011.0, 2006.0, 2010.0),
    (2010.0, 2013.0, 2008.0, 2009.0),  # sweeps 2011 into supply, closes back below
    (2009.0, 2010.0, 2006.0, 2007.0),  # closes below sweep low 2008 -> sell
]


def test_trading_day_rolls_at_five_pm_new_york() -> None:
    ords = trading_day_ordinals(
        np.array([epoch(2024, 1, 10, 21, 59), epoch(2024, 1, 10, 22, 0)])
    )
    assert [date.fromordinal(int(o)) for o in ords] == [
        date(2024, 1, 10),
        date(2024, 1, 11),
    ]


def test_zones_use_mother_candle_for_inside_day() -> None:
    mother = TradingDay(date(2024, 1, 8), 0, 0, 2000.0, 2020.0, 1980.0, 2010.0)
    inside = TradingDay(date(2024, 1, 9), 0, 0, 2005.0, 2015.0, 1990.0, 2001.0)
    today = TradingDay(date(2024, 1, 10), 0, 0, 0, 0, 0, 0)
    z = zones_for([mother, inside, today], 2)
    assert z == Zones(2010.0, 2020.0, 1980.0, 2000.0)


def test_15_minute_candles() -> None:
    c = to_15m(candles_to_bars(SETUP), 0, 60)
    assert list(c.high) == [2008.0, 2011.0, 2013.0, 2010.0]
    assert list(c.close) == [2007.0, 2010.0, 2009.0, 2007.0]


def test_sweep_sell_reaches_target() -> None:
    candles = SETUP + [(2007.0, 2007.0, 1990.0, 1992.0)] + [(1992.0,) * 4] * 4
    (t,) = run(candles, SweepRule(2.0, "close"))
    assert t.direction == -1 and t.stop == 2013.0
    assert t.entry == pytest.approx(2007.0 - HALF - 0.20)
    assert t.exit_reason == "target"
    assert t.target == pytest.approx(t.entry - 2 * (2013.0 - t.entry))
    assert t.exit == pytest.approx(1990.0 + HALF + 0.20)  # gapped through the target
    assert t.pnl_usd > 0


def test_close_stop_survives_a_wick_that_touch_stop_does_not() -> None:
    candles = SETUP + [
        (2007.0, 2016.0, 2006.0, 2012.0),
        (2012.0, 2012.0, 2012.0, 2014.0),
    ]
    candles += [(2014.0,) * 4] * 2
    (touch,) = run(candles, SweepRule(2.0, "touch"))
    assert touch.exit_reason == "stop" and touch.exit_bar == 61
    assert touch.exit == pytest.approx(2016.0 + HALF + 0.20)  # gapped past the stop
    (close,) = run(candles, SweepRule(2.0, "close"))
    assert close.exit_reason == "stop" and close.exit_bar == 89  # end of next candle
    assert close.exit == pytest.approx(2014.0 + HALF + 0.20)


def test_no_trade_when_sweep_outside_zone() -> None:
    low_setup = [(o - 20, h - 20, lo - 20, c - 20) for o, h, lo, c in SETUP]
    assert run(low_setup + [(1980.0,) * 4] * 3, SweepRule(2.0, "close")) == []


def test_setup_expires_without_confirmation() -> None:
    candles = (
        SETUP[:3]
        + [(2009.0, 2010.0, 2008.5, 2009.0)] * 5
        + [(2009.0, 2010.0, 2006.0, 2007.0)]
    )
    assert run(candles + [(2007.0,) * 4] * 2, SweepRule(2.0, "close")) == []


def test_time_exit_closes_same_day() -> None:
    candles = SETUP + [(2007.0,) * 4] * 2
    (t,) = run(candles, SweepRule(2.0, "close"))
    assert t.exit_reason == "time_exit"
    assert BAR_FIELDS  # bars carry every field the simulator reads


# sell entry 2006.65 (bid 2006.85 - 0.20), stop 2013 -> risk 6.35, 1R at 2000.30
DIP_THEN_RALLY = (
    SETUP
    + [
        (2007.0, 2007.0, 1999.0, 1999.0),  # best ask 1999.15 -> 1R reached
        (1999.0, 2008.0, 1999.0, 2008.0),  # rallies through the trail at 2005.50
    ]
    + [(2008.0,) * 4] * 2
)


def test_trail_locks_profit_after_one_r() -> None:
    (plain,) = run(DIP_THEN_RALLY, SweepRule(2.0, "close"))
    assert plain.exit_reason == "time_exit"
    (trailed,) = run(DIP_THEN_RALLY, SweepRule(2.0, "close", trail=True))
    assert trailed.exit_reason == "trail"
    assert trailed.exit_bar == 76  # the minute that opens at 2008 (gap past 2005.50)
    assert trailed.exit == pytest.approx(2008.0 + HALF + 0.20)


def test_trail_waits_until_one_r() -> None:
    candles = SETUP + [(2007.0, 2007.0, 2003.0, 2003.0)] + [(2003.0,) * 4] * 2
    (plain,) = run(candles, SweepRule(2.0, "close"))
    (trailed,) = run(candles, SweepRule(2.0, "close", trail=True))
    assert trailed.exit_reason == plain.exit_reason == "time_exit"
    assert trailed.pnl_usd == pytest.approx(plain.pnl_usd)


def test_trend_filter_blocks_sells_above_the_average() -> None:
    candles = SETUP + [(2007.0,) * 4] * 2
    rule = SweepRule(2.0, "close", trend_filter=True)
    above = HourlyTrend(np.array([0]), np.array([1000.0]))  # price above average
    below = HourlyTrend(np.array([0]), np.array([3000.0]))
    assert run(candles, rule, above) == []
    (t,) = run(candles, rule, below)
    assert t.direction == -1
    no_history = HourlyTrend(np.array([0]), np.array([np.nan]))
    assert run(candles, rule, no_history) == []


def test_hourly_trend_uses_only_finished_hours() -> None:
    hours = 25
    mid = np.repeat(np.arange(hours, dtype=float), 60)  # each hour closes at its index
    bars = {"minute_utc": DAY_START + np.arange(len(mid), dtype=np.int64) * 60}
    for side in ("bid", "ask"):
        for part in ("open", "high", "low", "close"):
            bars[f"{side}_{part}"] = mid
    trend = hourly_trend(bars)
    start_22 = 22 * 60
    assert trend.at(start_22) == pytest.approx(np.mean(np.arange(2, 22)))
    assert trend.at(start_22 + 30) == trend.at(start_22)  # hour 22 not finished yet
    assert np.isnan(trend.at(10 * 60))  # fewer than 20 finished hours
