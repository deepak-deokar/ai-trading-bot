"""Support and resistance, round 2: one level type at a time, ADR-scaled, against a
random-entry baseline. Rules: docs/xauusd-sr-v2-plan.md (written before running).

Level types (each scanned on its own; "all" merges them, for reference):

* prev_day: yesterday's high and low;
* prev_week: last week's high and low;
* swing: hourly turning points over the last 10 days with 2+ turns (round 1 rules);
* round: multiples of the step in ROUND_STEPS closest to one ADR, within 2 ADR of
  the day's open;
* asia: 18:00-02:00 New York high and low, used from 02:00.

Setups on finished 15-minute mid candles closing 03:00-13:00 New York: bounce and
retest as in round 1, plus breakout (candle opens at/below the level, closes beyond
the zone in the top half of its range; stop behind the level's zone). Stop buffer
0.1 x ADR; stop distance 0.15-0.6 x ADR and at most $30; targets 1R and 1.5R; exits
on touch, out by 16:45.

``twins`` gives the random-entry baseline: same day, direction, stop distance and
target, entry at a random 15-minute mark between 03:00 and 13:00.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from trading_bot.backtesting.news_day import execute
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, Sizing
from trading_bot.backtesting.sr_strategy import (
    ASIA_END,
    FIRST_CLOSE,
    LAST_CLOSE,
    LAST_EXIT,
    RETEST_CANDLES,
    SWING_DAYS,
    SWING_MERGE,
    ZONE,
    Level,
    Mids,
    _candles15,
    _hourly,
    _ny_epoch,
    adr_at,
    merge_levels,
    swing_levels,
)
from trading_bot.backtesting.sweep_strategy import TradingDay

TYPES = ("prev_day", "prev_week", "swing", "round", "asia")
SETUPS = ("bounce", "retest", "breakout")
TARGETS = (1.0, 1.5)
BUFFER = 0.10  # x ADR
MIN_STOP_ADR, MAX_STOP_ADR = 0.15, 0.6
MAX_STOP_USD = 30.0
ROUND_STEPS = (10.0, 25.0, 50.0, 100.0)
MAX_ENTRY_GAP = 120  # seconds between the candle close and the entry minute


def round_step(adr: float) -> float:
    return min(ROUND_STEPS, key=lambda s: abs(s - adr))


@dataclass(frozen=True)
class Signal:
    day: date
    kind: str  # bounce | retest | breakout
    ltype: str  # a TYPES entry or "all"
    direction: int
    level: float
    entry_minute: int
    stop: float  # buffer included
    adr: float


@dataclass(frozen=True)
class Result:
    signal: Signal
    target_r: float
    risk_mid: float  # stop distance from the entry minute's mid open
    trade: HoldTrade


def type_levels(
    bars: dict[str, Array], mid: Mids, days: Sequence[TradingDay], k: int, adr: float
) -> dict[str, list[Level]]:
    """Levels known at the start of day k, by type (Asian range not included)."""
    prev = days[k - 1]
    out: dict[str, list[Level]] = {
        "prev_day": [Level(prev.high, {"prev_day"}), Level(prev.low, {"prev_day"})]
    }
    wk = days[k].day.isocalendar()[:2]
    earlier = [d for d in days[max(0, k - 10) : k] if d.day.isocalendar()[:2] != wk]
    out["prev_week"] = []
    if earlier:
        lw = earlier[-1].day.isocalendar()[:2]
        same = [d for d in earlier if d.day.isocalendar()[:2] == lw]
        out["prev_week"] = [
            Level(max(d.high for d in same), {"prev_week"}),
            Level(min(d.low for d in same), {"prev_week"}),
        ]
    first = days[max(0, k - SWING_DAYS)].i0
    hi, lo = _hourly(bars["minute_utc"], mid, first, days[k].i0)
    out["swing"] = swing_levels(hi, lo, SWING_MERGE * adr)
    o, r = days[k].open, round_step(adr)
    out["round"] = [
        Level(float(x), {"round"})
        for x in np.arange(np.floor((o - 2 * adr) / r) * r, o + 2 * adr + r, r)
    ]
    return out


def _scan(
    levels: list[Level],
    early: list[Level],
    ltype: str,
    d: TradingDay,
    m: Array,
    mid: Mids,
    adr: float,
    asia_end: int,
) -> list[Signal]:
    z = ZONE * adr
    t_first = _ny_epoch(d.day, FIRST_CLOSE)
    t_last = _ny_epoch(d.day, LAST_CLOSE)
    starts, ends = _candles15(m, d.i0, d.i1)
    co = mid.o[starts]
    ch = np.maximum.reduceat(mid.h[d.i0 : d.i1], starts - d.i0)
    cl = np.minimum.reduceat(mid.lo[d.i0 : d.i1], starts - d.i0)
    cc = mid.c[ends - 1]
    close_t = (m[starts] // 900 + 1) * 900
    out: list[Signal] = []
    used: set[tuple[str, float, int]] = set()
    breaks: dict[tuple[float, int], int] = {}
    t_scan = t_first - RETEST_CANDLES * 900
    for j in range(1, len(starts)):
        t = int(close_t[j])
        if t < t_scan:
            continue
        for lv in levels if t > asia_end else early:
            L = lv.price
            li = round(L, 2)
            for s_ in (1, -1):
                # "buy" orientation: the level below, price above
                o, c, pc = s_ * co[j], s_ * cc[j], s_ * cc[j - 1]
                h = ch[j] if s_ == 1 else -cl[j]
                lo_ = cl[j] if s_ == 1 else -ch[j]
                lvl = s_ * L
                rng = h - lo_
                if rng <= 0:
                    continue
                found: list[tuple[str, float]] = []  # (setup, stop base)
                if o <= lvl and c > lvl + z:
                    if c >= lo_ + 0.5 * rng:
                        found.append(("breakout", lvl - z))
                    breaks[(li, s_)] = j  # a fresh break restarts the retest window
                elif (
                    pc > lvl + z
                    and lvl - 3 * z <= lo_ <= lvl + z
                    and c > lvl + z
                    and c >= lo_ + 0.6 * rng
                ):
                    found.append(("bounce", min(lo_, lvl - z)))
                b = breaks.get((li, s_))
                if b is not None and b < j <= b + RETEST_CANDLES:
                    if c < lvl - z:
                        breaks.pop((li, s_))
                    elif lo_ <= lvl + z and c > lvl + z and c >= lo_ + 0.5 * rng:
                        found.append(("retest", min(lo_, lvl - z)))
                        breaks.pop((li, s_))
                if not (t_first <= t <= t_last):
                    continue
                for kind, base in found:
                    key = (kind, li, s_)
                    if key in used:
                        continue
                    used.add(key)
                    e = int(ends[j])
                    if e >= d.i1 or m[e] - t > MAX_ENTRY_GAP:
                        continue
                    out.append(
                        Signal(
                            day=d.day,
                            kind=kind,
                            ltype=ltype,
                            direction=s_,
                            level=L,
                            entry_minute=e,
                            stop=s_ * base - s_ * BUFFER * adr,
                            adr=adr,
                        )
                    )
    return out


def find_signals(
    bars: dict[str, Array],
    days: Sequence[TradingDay],
    k: int,
    mid: Mids,
    ltypes: Sequence[str] = (*TYPES, "all"),
) -> list[Signal]:
    d = days[k]
    adr = adr_at(days, k)
    if adr is None or adr <= 0 or k < 1:
        return []
    m = bars["minute_utc"]
    z = ZONE * adr
    by_type = type_levels(bars, mid, days, k, adr)
    asia_end = _ny_epoch(d.day, ASIA_END)
    a1 = int(np.searchsorted(m, asia_end))
    by_type["asia"] = []
    if a1 > d.i0:
        by_type["asia"] = [
            Level(float(mid.h[d.i0 : a1].max()), {"asia"}),
            Level(float(mid.lo[d.i0 : a1].min()), {"asia"}),
        ]
    out: list[Signal] = []
    for lt in ltypes:
        if lt == "all":
            late = [x for t in TYPES for x in by_type[t]]
            early_raw = [x for t in TYPES if t != "asia" for x in by_type[t]]
        else:
            late = list(by_type[lt])
            early_raw = [] if lt == "asia" else late
        levels = merge_levels(late, z)
        early = merge_levels(early_raw, z)
        out += _scan(levels, early, lt, d, m, mid, adr, asia_end)
    return out


def last_minute(bars: dict[str, Array], d: TradingDay) -> int:
    cap = _ny_epoch(d.day, LAST_EXIT)
    last = int(np.searchsorted(bars["minute_utc"], cap, side="right")) - 1
    return min(last, d.i1 - 1)


def risk_ok(risk_mid: float, adr: float) -> bool:
    return (
        MIN_STOP_ADR * adr <= risk_mid <= MAX_STOP_ADR * adr
        and risk_mid <= MAX_STOP_USD
    )


def simulate(
    bars: dict[str, Array],
    mid: Mids,
    d: TradingDay,
    s: Signal,
    target_r: float,
    costs: CostModel,
) -> Result | None:
    e = s.entry_minute
    risk_mid = (float(mid.o[e]) - s.stop) * s.direction
    if not risk_ok(risk_mid, s.adr):
        return None
    t = execute(
        bars,
        d.day,
        e,
        last_minute(bars, d),
        s.direction,
        costs,
        Sizing(),
        stop=s.stop,
        target_r=target_r,
    )
    return None if t is None else Result(s, target_r, risk_mid, t)


def entry_marks(bars: dict[str, Array], d: TradingDay) -> Array:
    """1-minute indices of the first minute at each 15-minute mark 03:00-13:00."""
    m = bars["minute_utc"]
    t0, t1 = _ny_epoch(d.day, FIRST_CLOSE), _ny_epoch(d.day, LAST_CLOSE)
    marks = np.arange(t0, t1 + 1, 900)
    idx = np.searchsorted(m, marks)
    ok = idx < d.i1
    idx, marks = idx[ok], marks[ok]
    ok = m[idx] - marks <= MAX_ENTRY_GAP
    return idx[ok]


def twin(
    bars: dict[str, Array],
    mid: Mids,
    d: TradingDay,
    r: Result,
    entry: int,
    costs: CostModel,
) -> HoldTrade | None:
    s = r.signal
    stop = float(mid.o[entry]) - s.direction * r.risk_mid
    return execute(
        bars,
        d.day,
        entry,
        last_minute(bars, d),
        s.direction,
        costs,
        Sizing(),
        stop=stop,
        target_r=r.target_r,
    )


def take(results: Sequence[Result], max_per_day: int = 2) -> list[HoldTrade]:
    """One trade at a time, at most max_per_day a day."""
    out: list[HoldTrade] = []
    busy_until = -1
    per_day: dict[date, int] = {}
    for r in sorted(results, key=lambda r: r.signal.entry_minute):
        s = r.signal
        if s.entry_minute <= busy_until or per_day.get(s.day, 0) >= max_per_day:
            continue
        out.append(r.trade)
        busy_until = r.trade.exit_bar
        per_day[s.day] = per_day.get(s.day, 0) + 1
    return out
