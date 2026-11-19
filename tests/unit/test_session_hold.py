from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from trading_bot.backtesting.session_hold import (
    PLANS,
    HoldRule,
    SessionDay,
    condition_ok,
    extract_session_days,
    mid_only,
    simulate_session,
)
from trading_bot.backtesting.session_window import BAR_FIELDS, CostModel, Sizing

COSTS = CostModel(
    extra_spread_per_oz=0.20, commission_per_lot=8.0, slippage_per_oz=0.10
)
SPREAD = 0.30
NO_FILTER = HoldRule(None, False, False)


def make_day(
    mids: list[float],
    high: float = 2005.0,
    low: float = 1995.0,
    entry_bars: int = 120,
    trend: float | None = 5.0,
) -> SessionDay:
    m = np.array(mids, dtype=float)
    half = SPREAD / 2
    bars = {
        "bid_open": m - half,
        "bid_close": m - half,
        "bid_high": m - half + 0.05,
        "bid_low": m - half - 0.05,
        "ask_open": m + half,
        "ask_close": m + half,
        "ask_high": m + half + 0.05,
        "ask_low": m + half - 0.05,
    }
    minutes = np.arange(len(m), dtype=np.int64) * 60
    return SessionDay(
        date(2024, 3, 5),
        high,
        low,
        2000.0,
        minutes,
        bars,
        entry_bars,
        trailing_range=10.0,
        trend=trend,
    )


def test_plans_follow_local_time_and_daylight_saving() -> None:
    ny = next(p for p in PLANS if p.name == "ny_opening_drive")
    winter = datetime.fromtimestamp(ny.utc(date(2024, 1, 10), ny.range_start), UTC)
    summer = datetime.fromtimestamp(ny.utc(date(2024, 7, 10), ny.range_start), UTC)
    assert (winter.hour, winter.minute, summer.hour) == (14, 30, 13)


def test_breakout_long_held_to_time_exit() -> None:
    mids = [2000.0] * 10 + [2006.0] + [2010.0] * 200
    trade = simulate_session(make_day(mids), NO_FILTER, COSTS, Sizing())
    assert trade is not None and trade.direction == 1
    assert trade.entry_minute == 11
    assert trade.stop == pytest.approx(2000.0)
    assert trade.entry == pytest.approx(2010.0 + 0.15 + 0.20)
    assert trade.exit_reason == "time_exit"
    assert trade.exit == pytest.approx(2010.0 - 0.15 - 0.20)
    assert trade.hold_minutes == len(mids) - 11


def test_short_target_and_stop_first_rule() -> None:
    mids = [2000.0] * 5 + [1994.0] + [1990.0] * 5 + [1960.0] * 50
    win = simulate_session(make_day(mids), HoldRule(2.0, False, False), COSTS, Sizing())
    assert win is not None and win.direction == -1 and win.exit_reason == "target"
    assert win.pnl_usd > 0
    both = make_day([2000.0] * 5 + [1994.0] + [1990.0] * 50)
    both.bars["ask_high"][8] = 2010.0
    both.bars["ask_low"][8] = 1900.0
    loss = simulate_session(both, HoldRule(2.0, False, False), COSTS, Sizing())
    assert loss is not None and loss.exit_reason == "stop" and loss.pnl_usd < 0


def test_no_entry_after_deadline() -> None:
    mids = [2000.0] * 130 + [2006.0] * 50
    assert simulate_session(make_day(mids), NO_FILTER, COSTS, Sizing()) is None


def test_trend_filter_blocks_counter_trend_breakouts() -> None:
    up_break = [2000.0] * 3 + [2006.0] * 50
    rule = HoldRule(None, True, False)
    assert simulate_session(make_day(up_break, trend=5.0), rule, COSTS, Sizing())
    assert (
        simulate_session(make_day(up_break, trend=-5.0), rule, COSTS, Sizing()) is None
    )
    assert (
        simulate_session(make_day(up_break, trend=None), rule, COSTS, Sizing()) is None
    )


def test_condition_filter() -> None:
    assert condition_ok(make_day([2000.0] * 10), COSTS)
    assert not condition_ok(make_day([2000.0] * 10, high=2001.0, low=1999.0), COSTS)
    assert not condition_ok(make_day([2000.0] * 10, high=2020.0, low=1980.0), COSTS)


def test_extract_requires_coverage_and_builds_trend() -> None:
    ny = next(p for p in PLANS if p.name == "ny_opening_drive")
    all_minutes = []
    for k in range(35):
        d = date(2024, 1, 1) + timedelta(days=k)
        if d.weekday() < 5:
            s = ny.utc(d, ny.range_start)
            all_minutes.append(np.arange(s, ny.utc(d, ny.exit_at), 60))
    minutes = np.concatenate(all_minutes).astype(np.int64)
    price = 2000.0 + np.arange(len(minutes)) * 0.001
    bars = {"minute_utc": minutes} | {f: price for f in BAR_FIELDS}
    days, skipped = extract_session_days(bars, ny)
    assert len(days) == len(all_minutes) and skipped == 0
    assert days[0].entry_bars == 120
    assert len(days) > 21 and days[19].trend is None and days[-1].trend is not None
    assert days[-1].trend > 0
    holed = {k: np.delete(v, np.arange(40, 80)) for k, v in bars.items()}
    days, skipped = extract_session_days(holed, ny)
    assert skipped == 1


def test_mid_only_removes_spread() -> None:
    bars = {f: np.array([2000.0]) for f in BAR_FIELDS}
    bars["ask_open"] = np.array([2000.4])
    out = mid_only(bars)
    assert out["bid_open"][0] == out["ask_open"][0] == pytest.approx(2000.2)


def test_trade_anatomy_reconciles_and_measures_excursions() -> None:
    from trading_bot.backtesting.trade_anatomy import explain

    mids = [2000.0] * 10 + [2006.0] + [2010.0] * 20 + [2016.0] * 5 + [2008.0] * 30
    day = make_day(mids)
    trade = simulate_session(day, NO_FILTER, COSTS, Sizing())
    assert trade is not None
    a = explain(day, trade, COSTS)
    assert a.direction == "BUY" and a.entry_mid == pytest.approx(2010.0)
    assert a.exit_mid == pytest.approx(2008.0)
    assert a.gross_per_oz == pytest.approx(-2.0)
    total = a.gross_usd - a.spread_usd - a.extra_spread_slippage_usd - a.commission_usd
    assert total == pytest.approx(a.net_usd, abs=0.02)
    assert a.mfe_per_oz == pytest.approx(6.05)  # mid high 2016.05
    assert a.mfe_r == pytest.approx(6.05 / 10.0)
