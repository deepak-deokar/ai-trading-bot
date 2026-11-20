"""Trade gold only on big scheduled US news, at most once a day.

Events (config/us_news_events.csv): the jobs report (NFP) and inflation (CPI) at
08:30 New York, and scheduled Fed (FOMC) statements at 14:00 New York. Where two
events fall on one day only the first is traded.

Rules, fixed before any test was run:

1. The release candle is the 15-minute candle that starts at the release time
   (mid prices). If it closes up the "move" is up, if down the move is down; a
   candle that closes where it opened gives no trade.
2. Entry at the open of the next 15-minute candle (08:45 or 14:15):
   - momentum: trade in the direction of the move, stop just past the release
     candle's other end (low for a buy, high for a sell);
   - fade: trade against the move, stop just past the release candle's extreme
     (high for a sell, low for a buy).
3. Exit: either only at the time limit, or at a 2R target (whichever comes first,
   also the stop). Time limit 12:00 New York for 08:30 events, 16:45 for FOMC.
4. Stops and targets fill on touch, minute by minute; if one minute touches both,
   the stop wins. Fills use the recorded bid/ask plus the cost model.

A control run applies the same rule at 08:30 on days with no event, to see
whether news days behave differently from ordinary days at the same time.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np

from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, Sizing, lots_for

NY = ZoneInfo("America/New_York")
EVENTS_CSV = Path("config/us_news_events.csv")
CANDLE = timedelta(minutes=15)
MIN_CANDLE_MINUTES = 12  # release candle needs most of its minutes in the data
MAX_ENTRY_DELAY_MIN = 2  # entry minute must exist within 2 minutes of 08:45 / 14:15
EXIT_AT = {time(8, 30): time(12, 0), time(14, 0): time(16, 45)}


@dataclass(frozen=True)
class NewsEvent:
    day: date
    kind: str  # nfp | cpi | fomc | control
    at: time  # New York

    def utc(self, extra: timedelta = timedelta(0)) -> int:
        local = datetime.combine(self.day, self.at, tzinfo=NY) + extra
        return int(local.astimezone(UTC).timestamp())

    @property
    def exit_time(self) -> time:
        return EXIT_AT[self.at]


@dataclass(frozen=True)
class NewsRule:
    side: Literal["momentum", "fade"]
    target_r: float | None  # None = exit only at the time limit

    @property
    def name(self) -> str:
        exit_ = "time-exit" if self.target_r is None else f"{self.target_r:g}R"
        return f"{self.side}/{exit_}"


def load_events(path: Path = EVENTS_CSV) -> list[NewsEvent]:
    """Events from the CSV, one per day (the earliest when two share a day)."""
    rows = [r for r in path.read_text().splitlines() if r and not r.startswith("#")]
    out: dict[date, NewsEvent] = {}
    for r in csv.DictReader(rows):
        ev = NewsEvent(
            date.fromisoformat(r["date"]),
            r["event"],
            time.fromisoformat(r["time_ny"]),
        )
        if ev.day not in out or ev.at < out[ev.day].at:
            out[ev.day] = ev
    return sorted(out.values(), key=lambda e: e.day)


def control_days(
    bars: dict[str, Array], events: Iterable[NewsEvent], years: range
) -> list[NewsEvent]:
    """08:30 'events' on weekdays in `years` with data and no real event."""
    busy = {e.day for e in events}
    days = sorted(
        {
            datetime.fromtimestamp(int(m), UTC).astimezone(NY).date()
            for m in bars["minute_utc"][::60]
        }
    )
    return [
        NewsEvent(d, "control", time(8, 30))
        for d in days
        if d.year in years and d.weekday() < 5 and d not in busy
    ]


def _first(mask: Array) -> int:
    hits = np.flatnonzero(mask)
    return int(hits[0]) if len(hits) else -1


def simulate_event(
    bars: dict[str, Array],
    ev: NewsEvent,
    rule: NewsRule,
    costs: CostModel,
    sizing: Sizing,
) -> HoldTrade | None:
    m = bars["minute_utc"]
    t0, t1 = ev.utc(), ev.utc(CANDLE)
    a, b = int(np.searchsorted(m, t0)), int(np.searchsorted(m, t1))
    if b - a < MIN_CANDLE_MINUTES or b >= len(m):
        return None
    if m[b] - t1 > MAX_ENTRY_DELAY_MIN * 60:
        return None
    mid_open = (bars["bid_open"][a] + bars["ask_open"][a]) / 2
    mid_close = (bars["bid_close"][b - 1] + bars["ask_close"][b - 1]) / 2
    hi = float(((bars["bid_high"][a:b] + bars["ask_high"][a:b]) / 2).max())
    lo = float(((bars["bid_low"][a:b] + bars["ask_low"][a:b]) / 2).min())
    move = int(np.sign(mid_close - mid_open))
    if move == 0:
        return None
    direction = move if rule.side == "momentum" else -move
    stop = lo if direction == 1 else hi
    s = b
    last = int(np.searchsorted(m, ev.utc(_until(ev)))) - 1
    return execute(
        bars,
        ev.day,
        s,
        last,
        direction,
        costs,
        sizing,
        stop=stop,
        target_r=rule.target_r,
    )


def execute(
    bars: dict[str, Array],
    day: date,
    s: int,
    last: int,
    direction: int,
    costs: CostModel,
    sizing: Sizing,
    *,
    stop: float | None = None,
    risk: float | None = None,
    target_r: float | None = None,
) -> HoldTrade | None:
    """Open at minute s and manage minute by minute until minute `last` inclusive.

    Give either an absolute ``stop`` level or a ``risk`` distance from the entry
    fill. ``target_r`` sets a target at that many times the risk (None: no target).
    """
    if last <= s:
        return None
    m = bars["minute_utc"]
    pf = costs.per_fill
    if direction == 1:
        entry = float(bars["ask_open"][s]) + pf
    else:
        entry = float(bars["bid_open"][s]) - pf
    if stop is None:
        if risk is None or risk <= 0:
            raise ValueError("give a stop level or a positive risk distance")
        stop = entry - direction * risk
    if direction == 1 and stop >= float(bars["bid_open"][s]):
        return None  # price already through the stop at entry
    if direction == -1 and stop <= float(bars["ask_open"][s]):
        return None
    lots = lots_for(entry, stop, costs, sizing)
    if lots == 0.0:
        return None
    target = (
        None if target_r is None else entry + direction * target_r * abs(entry - stop)
    )
    sl = slice(s, last + 1)
    if direction == 1:
        hit_stop = _first(bars["bid_low"][sl] <= stop)
        hit_target = -1 if target is None else _first(bars["bid_high"][sl] >= target)
    else:
        hit_stop = _first(bars["ask_high"][sl] >= stop)
        hit_target = -1 if target is None else _first(bars["ask_low"][sl] <= target)
    candidates = [
        (k, r) for k, r in ((hit_stop, "stop"), (hit_target, "target")) if k >= 0
    ]
    if candidates:
        k_rel, reason = min(candidates, key=lambda x: (x[0], x[1] != "stop"))
    else:
        k_rel, reason = last - s, "time_exit"
    k = s + k_rel
    side_open = bars["bid_open"][k] if direction == 1 else bars["ask_open"][k]
    if reason == "stop":
        level = min(stop, side_open) if direction == 1 else max(stop, side_open)
    elif reason == "target":
        assert target is not None
        level = max(target, side_open) if direction == 1 else min(target, side_open)
    else:
        level = bars["bid_close"][k] if direction == 1 else bars["ask_close"][k]
    exit_px = float(level) - direction * pf
    pnl = (exit_px - entry) * direction * costs.contract_size_oz * lots
    pnl -= costs.commission_per_lot * lots
    hold = int((m[k] - m[s]) // 60) + 1
    return HoldTrade(
        day, direction, s, entry, stop, exit_px, lots, pnl, reason, hold, k, target
    )


def _until(ev: NewsEvent) -> timedelta:
    start = datetime.combine(ev.day, ev.at)
    return datetime.combine(ev.day, ev.exit_time) - start


def run_news(
    bars: dict[str, Array],
    events: Sequence[NewsEvent],
    rule: NewsRule,
    costs: CostModel,
    sizing: Sizing,
    years: range,
) -> tuple[list[HoldTrade], int]:
    """Trades for events whose year is in `years`, plus how many events had data."""
    trades: list[HoldTrade] = []
    usable = 0
    m = bars["minute_utc"]
    for ev in events:
        if ev.day.year not in years:
            continue
        a = int(np.searchsorted(m, ev.utc()))
        if a >= len(m) or m[a] - ev.utc() > 60:
            continue  # no data at the release time
        usable += 1
        t = simulate_event(bars, ev, rule, costs, sizing)
        if t is not None:
            trades.append(t)
    return trades, usable
