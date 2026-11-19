from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pytest

from trading_bot.backtesting.session_window import (
    BAR_FIELDS,
    WINDOW_MINUTES,
    WINDOWS,
    CostModel,
    Rule,
    Sizing,
    WindowDay,
    condition_ok,
    extract_window_days,
    load_bars,
    lots_for,
    simulate_day,
    summarize,
)

COSTS = CostModel(
    extra_spread_per_oz=0.20, commission_per_lot=8.0, slippage_per_oz=0.10
)
SPREAD = 0.30


def make_day(
    mids: list[float], pre_high: float = 2001.0, pre_low: float = 1999.0
) -> WindowDay:
    """30 flat-ish bars: each bar opens/closes at the given mid, high/low ±0.05."""
    assert len(mids) == WINDOW_MINUTES
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
    return WindowDay(date(2024, 3, 5), pre_high, pre_low, bars, trailing_pre_range=2.0)


def test_cost_model_reads_expensive_profile_and_doubles() -> None:
    path = Path("config/xauusd_costs_expensive.yaml")
    base = CostModel.from_yaml(path)
    double = CostModel.from_yaml(path, multiplier=2.0)
    assert base.per_fill == pytest.approx(0.20)
    assert base.round_trip_per_oz(0.30) == pytest.approx(0.30 + 0.40 + 0.08)
    assert double.round_trip_per_oz(0.30) == pytest.approx(0.30 + 0.80 + 0.16)


def test_window_start_follows_daylight_saving() -> None:
    london = next(w for w in WINDOWS if w.name == "london_open")
    winter = datetime.fromtimestamp(london.start_utc(date(2024, 1, 10)), UTC)
    summer = datetime.fromtimestamp(london.start_utc(date(2024, 7, 10)), UTC)
    assert (winter.hour, summer.hour) == (8, 7)


def test_holdout_months_are_refused() -> None:
    with pytest.raises(ValueError, match="holdout"):
        load_bars(Path("/nonexistent"), 202512, 202601)


def test_orb_long_hits_target_with_conservative_fills() -> None:
    mids = [2000.0, 2001.5] + [2002.0] * 2 + [2010.0] * 26
    day = make_day(mids)
    trade = simulate_day(day, Rule("orb", 1.0, False), COSTS, Sizing())
    assert trade is not None
    assert trade.direction == 1 and trade.entry_minute == 2  # signal on bar 1 close
    assert trade.entry == pytest.approx(2002.0 + 0.15 + 0.20)  # ask + per-fill
    assert trade.stop == pytest.approx(2000.0)
    assert trade.exit_reason == "target"
    risk = trade.entry - trade.stop
    # bar 4 opens above the target, so it fills at that open (bid) less costs
    assert trade.exit == pytest.approx(2010.0 - 0.15 - 0.20)
    expected = (trade.exit - trade.entry) * 100 * trade.lots - 8.0 * trade.lots
    assert trade.pnl_usd == pytest.approx(expected)
    assert trade.exit > trade.entry + risk


def test_stop_wins_when_bar_touches_both() -> None:
    mids = [2000.0, 2001.5, 2002.0] + [2002.0] * 27
    day = make_day(mids)
    day.bars["bid_low"][3] = 1990.0
    day.bars["bid_high"][3] = 2020.0
    trade = simulate_day(day, Rule("orb", 1.0, False), COSTS, Sizing())
    assert trade is not None and trade.exit_reason == "stop"
    assert trade.exit == pytest.approx(2000.0 - 0.20)
    assert trade.pnl_usd < 0


def test_short_momentum_time_exit() -> None:
    mids = [2000.0, 1999.8, 1999.6, 1999.4, 1999.2] + [1999.0] * 25
    day = make_day(mids, pre_high=2005.0, pre_low=1995.0)
    trade = simulate_day(day, Rule("momentum", None, False), COSTS, Sizing())
    assert trade is not None and trade.direction == -1
    assert trade.entry_minute == 5
    assert trade.exit_reason == "window_end"
    assert trade.exit == pytest.approx(1999.0 + 0.15 + 0.20)  # ask close + costs


def test_no_breakout_means_no_trade() -> None:
    day = make_day([2000.0] * WINDOW_MINUTES)
    assert simulate_day(day, Rule("orb", None, False), COSTS, Sizing()) is None


def test_filter_skips_quiet_and_wild_days() -> None:
    normal = make_day([2000.0] * 30)
    assert condition_ok(normal, COSTS)
    quiet = make_day([2000.0] * 30, pre_high=2000.4, pre_low=2000.0)
    wild = make_day([2000.0] * 30, pre_high=2004.0, pre_low=1997.0)
    assert not condition_ok(quiet, COSTS)
    assert not condition_ok(wild, COSTS)
    normal.trailing_pre_range = None
    assert not condition_ok(normal, COSTS)


def test_lot_size_risks_one_percent_and_respects_minimum() -> None:
    lots = lots_for(2000.0, 1998.0, COSTS, Sizing())
    assert lots == pytest.approx(0.13)  # $30 / ((2 + 0.2) * 100) = 0.136
    assert lots_for(2000.0, 1900.0, COSTS, Sizing()) == 0.0  # below 0.01


def test_extract_window_days_requires_complete_window() -> None:
    london = next(w for w in WINDOWS if w.name == "london_open")
    start = london.start_utc(date(2024, 1, 10))
    minutes = np.arange(start - 3600, start + 1800, 60, dtype=np.int64)
    bars = {"minute_utc": minutes}
    for f in BAR_FIELDS:
        bars[f] = np.full(len(minutes), 2000.0)
    days, skipped = extract_window_days(bars, london)
    assert [d.day for d in days] == [date(2024, 1, 10)] and skipped == 0
    holed = {k: np.delete(v, 70) for k, v in bars.items()}
    days, skipped = extract_window_days(holed, london)
    assert days == [] and skipped == 1


def test_summary_drawdown_and_win_rate() -> None:
    mids = [2000.0, 2001.5] + [2002.0] * 2 + [2010.0] * 26
    win = simulate_day(make_day(mids), Rule("orb", 1.0, False), COSTS, Sizing())
    assert win is not None
    s = summarize([win], window_days=4)
    assert s.trades == 1 and s.win_rate == 1.0
    assert s.max_drawdown_usd == 0.0
    assert s.avg_per_window_day == pytest.approx(win.pnl_usd / 4)
