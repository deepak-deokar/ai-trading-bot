"""Lean backtester for XAUUSD 30-minute session-window strategies.

Every trade opens and closes inside one fixed daily 30-minute window (no overnight).
Fills are deliberately conservative:

* decisions use only completed 1-minute bars; entry is at the NEXT bar's open,
  buying at the ask and selling at the bid recorded in the data;
* every fill is further worsened by half the configured extra spread plus slippage;
* if a bar touches both the stop and the target, the stop is assumed to fill first;
* commission is charged per lot round trip.

Bars come from ``~/TradingData/xauusd/bars_1m/XAUUSD_YYYYMM.npz`` (see
``trading_bot.data.histdata_bulk``). Months from ``HOLDOUT_START_MONTH`` on are the
untouched final test and are refused unless explicitly allowed.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import numpy as np
import yaml

HOLDOUT_START_MONTH = 202601  # 2026 stays untouched until the final test
PRE_WINDOW_MINUTES = 60
WINDOW_MINUTES = 30
MIN_PRE_BARS = 45
TRAILING_DAYS = 20
BAR_FIELDS = (
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
)

Array = np.ndarray[Any, np.dtype[Any]]


# --------------------------------------------------------------------------- costs
@dataclass(frozen=True)
class CostModel:
    extra_spread_per_oz: float
    commission_per_lot: float
    slippage_per_oz: float
    contract_size_oz: float = 100.0
    min_lot: float = 0.01
    lot_step: float = 0.01
    max_lot: float = 50.0

    @classmethod
    def from_yaml(cls, path: Path, multiplier: float = 1.0) -> CostModel:
        cfg = yaml.safe_load(path.read_text())
        c = cfg["contract"]
        return cls(
            extra_spread_per_oz=cfg["spread"]["extra_usd_per_oz"] * multiplier,
            commission_per_lot=cfg["commission"]["usd_per_lot_round_trip"] * multiplier,
            slippage_per_oz=cfg["slippage"]["usd_per_oz_per_fill"] * multiplier,
            contract_size_oz=c["contract_size_oz"],
            min_lot=c["min_lot"],
            lot_step=c["lot_step"],
            max_lot=c["max_lot"],
        )

    @property
    def per_fill(self) -> float:
        """Price worsening per fill on top of the recorded bid/ask, USD per oz."""
        return self.extra_spread_per_oz / 2 + self.slippage_per_oz

    def round_trip_per_oz(self, spread: float) -> float:
        """Full cost of one round trip per ounce at a given recorded spread."""
        return (
            spread + 2 * self.per_fill + self.commission_per_lot / self.contract_size_oz
        )


# -------------------------------------------------------------------------- windows
@dataclass(frozen=True)
class Window:
    name: str
    tz: str
    start: time
    label: str

    def start_utc(self, day: date) -> int:
        local = datetime.combine(day, self.start, tzinfo=ZoneInfo(self.tz))
        return int(local.astimezone(UTC).timestamp())


WINDOWS: tuple[Window, ...] = (
    Window("asia_open", "Asia/Tokyo", time(9, 0), "Tokyo 09:00"),
    Window("london_open", "Europe/London", time(8, 0), "London 08:00"),
    Window("us_data", "America/New_York", time(8, 30), "New York 08:30"),
    Window("ny_open", "America/New_York", time(9, 30), "New York 09:30"),
    Window("london_fix", "Europe/London", time(15, 0), "London 15:00"),
)


@dataclass
class WindowDay:
    day: date
    pre_high: float  # highest mid in the 60 minutes before the window
    pre_low: float
    bars: dict[str, Array]  # 30 window bars, keys = BAR_FIELDS
    trailing_pre_range: float | None = None  # median pre-range of prior 20 days

    @property
    def pre_range(self) -> float:
        return self.pre_high - self.pre_low

    @property
    def entry_spread(self) -> float:
        return float(self.bars["ask_open"][0] - self.bars["bid_open"][0])

    def mid(self, part: str) -> Array:
        return (self.bars[f"bid_{part}"] + self.bars[f"ask_{part}"]) / 2


def month_keys(first: int, last: int) -> list[int]:
    out, y, m = [], first // 100, first % 100
    while y * 100 + m <= last:
        out.append(y * 100 + m)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def load_bars(
    bars_dir: Path, first: int, last: int, allow_holdout: bool = False
) -> dict[str, Array]:
    """Concatenate monthly bar files [first, last] (YYYYMM, inclusive)."""
    if last >= HOLDOUT_START_MONTH and not allow_holdout:
        raise ValueError(f"months from {HOLDOUT_START_MONTH} are the untouched holdout")
    parts = [np.load(bars_dir / f"XAUUSD_{k}.npz") for k in month_keys(first, last)]
    return {
        f: np.concatenate([p[f] for p in parts]) for f in ("minute_utc", *BAR_FIELDS)
    }


def extract_window_days(
    bars: dict[str, Array], window: Window
) -> tuple[list[WindowDay], int]:
    """Weekday windows with complete data, plus the count skipped for gaps."""
    minutes = bars["minute_utc"]
    if len(minutes) == 0:
        return [], 0
    first = datetime.fromtimestamp(int(minutes[0]), UTC).date() - timedelta(days=1)
    last = datetime.fromtimestamp(int(minutes[-1]), UTC).date() + timedelta(days=1)
    days: list[WindowDay] = []
    skipped = 0
    d = first
    while d <= last:
        if d.weekday() < 5:
            start = window.start_utc(d)
            i0, i1, i2 = np.searchsorted(
                minutes,
                [start - PRE_WINDOW_MINUTES * 60, start, start + WINDOW_MINUTES * 60],
            )
            complete = i2 - i1 == WINDOW_MINUTES and i1 - i0 >= MIN_PRE_BARS
            if complete:
                pre_mid_h = (bars["bid_high"][i0:i1] + bars["ask_high"][i0:i1]) / 2
                pre_mid_l = (bars["bid_low"][i0:i1] + bars["ask_low"][i0:i1]) / 2
                days.append(
                    WindowDay(
                        day=d,
                        pre_high=float(pre_mid_h.max()),
                        pre_low=float(pre_mid_l.min()),
                        bars={f: bars[f][i1:i2] for f in BAR_FIELDS},
                    )
                )
            elif i2 > i0 or i1 - i0 > 0:
                skipped += 1  # market open but minutes missing (feed hole/holiday)
        d += timedelta(days=1)
    for k, wd in enumerate(days):
        prior = [x.pre_range for x in days[max(0, k - TRAILING_DAYS) : k]]
        wd.trailing_pre_range = (
            statistics.median(prior) if len(prior) == TRAILING_DAYS else None
        )
    return days, skipped


# -------------------------------------------------------------------------- rules
@dataclass(frozen=True)
class Rule:
    """A pre-declared session-window rule.

    * ``orb``: opening-range breakout. A 1-minute mid close above the high (below the
      low) of the 60 minutes before the window buys (sells); stop at the middle of
      that range.
    * ``momentum``: trade in the direction of the window's first 5 minutes; stop
      beyond the extreme of those 5 minutes.

    ``target_r``: take profit at that multiple of the initial risk; None means hold
    until the stop or the end of the window. ``use_filter`` skips quiet or chaotic
    days (see ``condition_ok``).
    """

    strategy: Literal["orb", "momentum"]
    target_r: float | None
    use_filter: bool

    @property
    def name(self) -> str:
        tgt = "time-exit" if self.target_r is None else f"{self.target_r:g}R"
        return f"{self.strategy}/{tgt}/{'filter' if self.use_filter else 'all-days'}"


QUIET_RATIO = 0.5  # pre-window range below half its 20-day median → too quiet
WILD_RATIO = 3.0  # above three times its 20-day median → too chaotic
MIN_RANGE_COSTS = 2.0  # pre-window range must cover two round-trip costs


def condition_ok(day: WindowDay, costs: CostModel) -> bool:
    """Rule-based 'skip bad conditions' check, known before the window opens."""
    if day.trailing_pre_range is None or day.trailing_pre_range <= 0:
        return False
    ratio = day.pre_range / day.trailing_pre_range
    if ratio < QUIET_RATIO or ratio > WILD_RATIO:
        return False
    return day.pre_range >= MIN_RANGE_COSTS * costs.round_trip_per_oz(day.entry_spread)


@dataclass(frozen=True)
class Trade:
    day: date
    direction: int  # +1 long, -1 short
    entry_minute: int
    entry: float
    stop: float
    exit: float
    lots: float
    pnl_usd: float
    exit_reason: str


@dataclass(frozen=True)
class Sizing:
    account_usd: float = 3000.0
    risk_fraction: float = 0.01
    leverage: float = 100.0

    @property
    def risk_usd(self) -> float:
        return self.account_usd * self.risk_fraction


def lots_for(entry: float, stop: float, costs: CostModel, sizing: Sizing) -> float:
    risk_per_oz = abs(entry - stop) + costs.per_fill
    raw = sizing.risk_usd / (risk_per_oz * costs.contract_size_oz)
    margin_cap = sizing.account_usd * sizing.leverage / (entry * costs.contract_size_oz)
    lots = min(raw, margin_cap, costs.max_lot)
    lots = math.floor(round(lots / costs.lot_step, 6)) * costs.lot_step
    return round(lots, 2) if lots >= costs.min_lot else 0.0


def _signal(day: WindowDay, rule: Rule) -> tuple[int, int, float] | None:
    """(direction, entry bar index, stop level) or None."""
    mid_close = day.mid("close")
    if rule.strategy == "orb":
        stop = (day.pre_high + day.pre_low) / 2
        for i in range(WINDOW_MINUTES - 2):
            if mid_close[i] > day.pre_high:
                return 1, i + 1, stop
            if mid_close[i] < day.pre_low:
                return -1, i + 1, stop
        return None
    first = 5
    move = mid_close[first - 1] - day.mid("open")[0]
    if move == 0:
        return None
    if move > 0:
        return 1, first, float(day.mid("low")[:first].min())
    return -1, first, float(day.mid("high")[:first].max())


def simulate_day(
    day: WindowDay, rule: Rule, costs: CostModel, sizing: Sizing
) -> Trade | None:
    if rule.use_filter and not condition_ok(day, costs):
        return None
    sig = _signal(day, rule)
    if sig is None:
        return None
    direction, j, stop = sig
    b = day.bars
    if direction == 1:
        entry = float(b["ask_open"][j]) + costs.per_fill
        if stop >= float(b["bid_open"][j]):
            return None  # already through the stop at entry
    else:
        entry = float(b["bid_open"][j]) - costs.per_fill
        if stop <= float(b["ask_open"][j]):
            return None
    lots = lots_for(entry, stop, costs, sizing)
    if lots == 0.0:
        return None
    risk = abs(entry - stop)
    target = None if rule.target_r is None else entry + direction * rule.target_r * risk

    exit_px, reason = 0.0, "window_end"
    for k in range(j, WINDOW_MINUTES):
        if direction == 1:
            o, lo, hi = b["bid_open"][k], b["bid_low"][k], b["bid_high"][k]
            if lo <= stop:
                exit_px, reason = min(stop, o) - costs.per_fill, "stop"
                break
            if target is not None and hi >= target:
                exit_px, reason = max(target, o) - costs.per_fill, "target"
                break
        else:
            o, lo, hi = b["ask_open"][k], b["ask_low"][k], b["ask_high"][k]
            if hi >= stop:
                exit_px, reason = max(stop, o) + costs.per_fill, "stop"
                break
            if target is not None and lo <= target:
                exit_px, reason = min(target, o) + costs.per_fill, "target"
                break
    else:
        last = WINDOW_MINUTES - 1
        exit_px = (
            float(b["bid_close"][last]) - costs.per_fill
            if direction == 1
            else float(b["ask_close"][last]) + costs.per_fill
        )
    pnl = (
        float(exit_px) - entry
    ) * direction * costs.contract_size_oz * lots - costs.commission_per_lot * lots
    return Trade(day.day, direction, j, entry, stop, float(exit_px), lots, pnl, reason)


def run_rule(
    days: Iterable[WindowDay], rule: Rule, costs: CostModel, sizing: Sizing
) -> list[Trade]:
    return [t for d in days if (t := simulate_day(d, rule, costs, sizing))]


# ------------------------------------------------------------------------ metrics
@dataclass
class Summary:
    window_days: int
    trades: int
    win_rate: float
    net_usd: float
    avg_per_trade: float
    avg_per_window_day: float
    worst_day: float
    best_day: float
    max_drawdown_usd: float
    profit_factor: float | None
    by_year: dict[int, float] = field(default_factory=dict)


def summarize(trades: Sequence[Trade], window_days: int) -> Summary:
    pnl = np.array([t.pnl_usd for t in trades], dtype=float)
    equity = np.concatenate([[0.0], np.cumsum(pnl)])
    drawdown = float((np.maximum.accumulate(equity) - equity).max())
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    by_year: dict[int, float] = {}
    for t in trades:
        by_year[t.day.year] = by_year.get(t.day.year, 0.0) + t.pnl_usd
    n = len(trades)
    return Summary(
        window_days=window_days,
        trades=n,
        win_rate=float((pnl > 0).mean()) if n else 0.0,
        net_usd=float(pnl.sum()),
        avg_per_trade=float(pnl.mean()) if n else 0.0,
        avg_per_window_day=float(pnl.sum()) / window_days if window_days else 0.0,
        worst_day=float(pnl.min()) if n else 0.0,
        best_day=float(pnl.max()) if n else 0.0,
        max_drawdown_usd=drawdown,
        profit_factor=float(gains / losses) if losses > 0 else None,
        by_year={y: round(v, 2) for y, v in sorted(by_year.items())},
    )


def survey(days: Sequence[WindowDay], costs: CostModel) -> dict[str, float]:
    """How far gold typically moves in the window versus the cost of a trade."""
    if not days:
        return {}
    ranges = [float(d.mid("high").max() - d.mid("low").min()) for d in days]
    moves = [abs(float(d.mid("close")[-1] - d.mid("open")[0])) for d in days]
    spreads = [d.entry_spread for d in days]
    rt = [costs.round_trip_per_oz(s) for s in spreads]
    med_range, med_cost = statistics.median(ranges), statistics.median(rt)
    return {
        "days": len(days),
        "median_range": round(med_range, 3),
        "median_abs_move": round(statistics.median(moves), 3),
        "median_entry_spread": round(statistics.median(spreads), 3),
        "median_round_trip_cost": round(med_cost, 3),
        "range_to_cost": round(med_range / med_cost, 2),
    }
