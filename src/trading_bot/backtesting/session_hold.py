"""Same-day XAUUSD range-breakout strategies held for hours, closed by a fixed time.

Each ``SessionPlan`` defines, in local exchange time (daylight saving handled):

* a reference range (e.g. the Asian session before London opens);
* an entry period after it, in which the first 1-minute mid close beyond the range
  triggers one trade in that direction (entry at the next bar's open);
* a fixed exit time by which any open trade is closed (never overnight).

The stop sits at the middle of the reference range. Fills, costs, sizing and the
stop-first rule are the conservative ones from ``session_window``.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from trading_bot.backtesting.session_window import (
    BAR_FIELDS,
    QUIET_RATIO,
    WILD_RATIO,
    Array,
    CostModel,
    Sizing,
    Trade,
    lots_for,
)

TRAILING_DAYS = 20
MIN_COVERAGE = 0.9  # share of expected 1-minute bars that must be present
MIN_RANGE_COSTS = 2.0  # reference range must cover two round-trip costs


@dataclass(frozen=True)
class SessionPlan:
    name: str
    label: str
    tz: str
    range_start: time
    range_end: time
    entry_end: time
    exit_at: time

    def utc(self, day: date, at: time) -> int:
        local = datetime.combine(day, at, tzinfo=ZoneInfo(self.tz))
        return int(local.astimezone(UTC).timestamp())


PLANS: tuple[SessionPlan, ...] = (
    SessionPlan(
        "london_asia_break",
        "Asian range (00:00-07:00 London) broken 07:00-10:00, out by 16:00 London",
        "Europe/London",
        time(0, 0),
        time(7, 0),
        time(10, 0),
        time(16, 0),
    ),
    SessionPlan(
        "ny_opening_drive",
        "NY first 30 min (09:30-10:00) broken 10:00-12:00, out by 14:00 New York",
        "America/New_York",
        time(9, 30),
        time(10, 0),
        time(12, 0),
        time(14, 0),
    ),
)


@dataclass
class SessionDay:
    day: date
    range_high: float
    range_low: float
    ref_price: float  # mid close of the last reference-range bar
    minutes: Array  # minute_utc of the bars after the range, up to the exit time
    bars: dict[str, Array]
    entry_bars: int  # how many of those bars open before the entry deadline
    trailing_range: float | None = None  # median range of the prior 20 days
    trend: float | None = None  # ref_price minus ref_price 20 session days earlier

    @property
    def range_size(self) -> float:
        return self.range_high - self.range_low

    @property
    def entry_spread(self) -> float:
        return float(self.bars["ask_open"][0] - self.bars["bid_open"][0])

    def mid(self, part: str) -> Array:
        return (self.bars[f"bid_{part}"] + self.bars[f"ask_{part}"]) / 2


def mid_only(bars: dict[str, Array]) -> dict[str, Array]:
    """Bars with bid = ask = mid, to measure an edge before spread and costs."""
    out = dict(bars)
    for part in ("open", "high", "low", "close"):
        mid = (bars[f"bid_{part}"] + bars[f"ask_{part}"]) / 2
        out[f"bid_{part}"], out[f"ask_{part}"] = mid, mid
    return out


def extract_session_days(
    bars: dict[str, Array], plan: SessionPlan
) -> tuple[list[SessionDay], int]:
    """Weekdays with at least 90% of the expected bars, plus the count skipped."""
    minutes = bars["minute_utc"]
    if len(minutes) == 0:
        return [], 0
    first = datetime.fromtimestamp(int(minutes[0]), UTC).date() - timedelta(days=1)
    last = datetime.fromtimestamp(int(minutes[-1]), UTC).date() + timedelta(days=1)
    days: list[SessionDay] = []
    skipped = 0
    d = first
    while d <= last:
        if d.weekday() < 5:
            rs, re, ee, ex = (
                plan.utc(d, t)
                for t in (
                    plan.range_start,
                    plan.range_end,
                    plan.entry_end,
                    plan.exit_at,
                )
            )
            i0, i1, ie, i2 = np.searchsorted(minutes, [rs, re, ee, ex])
            want_range, want_trade = (re - rs) // 60, (ex - re) // 60
            ok = (
                i1 - i0 >= MIN_COVERAGE * want_range
                and i2 - i1 >= MIN_COVERAGE * want_trade
            )
            if ok:
                hi = (bars["bid_high"][i0:i1] + bars["ask_high"][i0:i1]) / 2
                lo = (bars["bid_low"][i0:i1] + bars["ask_low"][i0:i1]) / 2
                ref = (bars["bid_close"][i1 - 1] + bars["ask_close"][i1 - 1]) / 2
                days.append(
                    SessionDay(
                        day=d,
                        range_high=float(hi.max()),
                        range_low=float(lo.min()),
                        ref_price=float(ref),
                        minutes=minutes[i1:i2],
                        bars={f: bars[f][i1:i2] for f in BAR_FIELDS},
                        entry_bars=int(ie - i1),
                    )
                )
            elif i2 > i0:
                skipped += 1
        d += timedelta(days=1)
    for k, sd in enumerate(days):
        if k >= TRAILING_DAYS:
            prior = days[k - TRAILING_DAYS : k]
            sd.trailing_range = statistics.median(x.range_size for x in prior)
            sd.trend = sd.ref_price - days[k - TRAILING_DAYS].ref_price
    return days, skipped


@dataclass(frozen=True)
class HoldRule:
    """Range breakout held to a target, the stop, or the plan's exit time.

    ``trend_filter``: only trade in the direction of the last 20 session days.
    ``condition_filter``: skip days whose range is under half or over three times
    its 20-day median, or too small to cover two round-trip costs.
    """

    target_r: float | None
    trend_filter: bool
    condition_filter: bool

    @property
    def name(self) -> str:
        tgt = "time-exit" if self.target_r is None else f"{self.target_r:g}R"
        flt = "+".join(
            f
            for f, on in (("trend", self.trend_filter), ("cond", self.condition_filter))
            if on
        )
        return f"{tgt}/{flt or 'no-filter'}"


@dataclass(frozen=True)
class HoldTrade(Trade):
    hold_minutes: int = 0
    exit_bar: int = -1  # index into the day's post-range bars where the trade closed
    target: float | None = None


def condition_ok(day: SessionDay, costs: CostModel) -> bool:
    if day.trailing_range is None or day.trailing_range <= 0:
        return False
    ratio = day.range_size / day.trailing_range
    if ratio < QUIET_RATIO or ratio > WILD_RATIO:
        return False
    return day.range_size >= MIN_RANGE_COSTS * costs.round_trip_per_oz(day.entry_spread)


def simulate_session(
    day: SessionDay, rule: HoldRule, costs: CostModel, sizing: Sizing
) -> HoldTrade | None:
    if rule.condition_filter and not condition_ok(day, costs):
        return None
    mid_close = day.mid("close")
    n = len(mid_close)
    signal = None
    for i in range(min(day.entry_bars, n - 1)):
        if mid_close[i] > day.range_high:
            signal = (1, i + 1)
            break
        if mid_close[i] < day.range_low:
            signal = (-1, i + 1)
            break
    if signal is None:
        return None
    direction, j = signal
    if rule.trend_filter and (day.trend is None or day.trend * direction <= 0):
        return None
    stop = (day.range_high + day.range_low) / 2
    b = day.bars
    if direction == 1:
        entry = float(b["ask_open"][j]) + costs.per_fill
        if stop >= float(b["bid_open"][j]):
            return None
    else:
        entry = float(b["bid_open"][j]) - costs.per_fill
        if stop <= float(b["ask_open"][j]):
            return None
    lots = lots_for(entry, stop, costs, sizing)
    if lots == 0.0:
        return None
    risk = abs(entry - stop)
    target = None if rule.target_r is None else entry + direction * rule.target_r * risk

    exit_px, reason, k_exit = 0.0, "time_exit", n - 1
    for k in range(j, n):
        if direction == 1:
            o, lo, hi = b["bid_open"][k], b["bid_low"][k], b["bid_high"][k]
            if lo <= stop:
                exit_px, reason, k_exit = min(stop, o) - costs.per_fill, "stop", k
                break
            if target is not None and hi >= target:
                exit_px, reason, k_exit = max(target, o) - costs.per_fill, "target", k
                break
        else:
            o, lo, hi = b["ask_open"][k], b["ask_low"][k], b["ask_high"][k]
            if hi >= stop:
                exit_px, reason, k_exit = max(stop, o) + costs.per_fill, "stop", k
                break
            if target is not None and lo <= target:
                exit_px, reason, k_exit = min(target, o) + costs.per_fill, "target", k
                break
    else:
        exit_px = (
            float(b["bid_close"][-1]) - costs.per_fill
            if direction == 1
            else float(b["ask_close"][-1]) + costs.per_fill
        )
    pnl = (
        float(exit_px) - entry
    ) * direction * costs.contract_size_oz * lots - costs.commission_per_lot * lots
    hold = int((day.minutes[k_exit] - day.minutes[j]) // 60) + 1
    return HoldTrade(
        day.day,
        direction,
        j,
        entry,
        stop,
        float(exit_px),
        lots,
        pnl,
        reason,
        hold,
        k_exit,
        target,
    )


def run_hold_rule(
    days: Iterable[SessionDay], rule: HoldRule, costs: CostModel, sizing: Sizing
) -> list[HoldTrade]:
    return [t for d in days if (t := simulate_session(d, rule, costs, sizing))]
