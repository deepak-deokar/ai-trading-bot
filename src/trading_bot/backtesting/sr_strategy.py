"""Support and resistance setups for intraday gold.

Levels known at the start of each trading day (17:00-17:00 New York):

* yesterday's high and low, last week's high and low;
* swing levels: hourly turning points (a high above the 3 hourly candles on each
  side, or a low below them) over the last 10 trading days, grouped when they sit
  within 0.1 x ADR of each other; a group needs at least 2 turns to count;
* round numbers: every $50;
* from 02:00 New York, today's Asian range high and low (18:00-02:00).

A level is a zone of +/- z around its price, z = 0.05 x ADR (20-day average daily
range). Levels closer than z to each other are merged.

Setups, read on finished 15-minute mid-price candles closing 03:00-13:00 New York:

* bounce: price comes down into support (the candle before closed above the zone),
  the candle dips into the zone without closing more than 3z below the level, then
  closes back above the zone in the top 40% of its range -> buy. Mirror at
  resistance -> sell.
* retest: a candle closes above the zone of a level it opened below (a break). Within
  the next 8 candles price comes back into the zone and a candle closes above the
  zone in the top half of its range -> buy. A close below the zone first cancels it.
  Mirror for breaks down.

Entry at the next minute's open. Stop beyond the zone and the setup candle's wick
plus a buffer of 0.05 or 0.15 x ADR (both tried). Stops under $5 or over $30 are
skipped ($30 risk at the 0.01-lot minimum allows about $30). Targets: 1R, 1.5R, or
the next level ahead (at least 1.5R, at most 3R). The first major level ahead (any
level except swing levels with fewer than 3 turns, plus today's high and low so
far) must leave room for the target. Exits on touch, out by 16:45 New York.

``candidates`` lists every setup with its trade simulated on its own (overlaps
allowed); ``take`` then walks them in time order keeping one trade at a time and at
most ``max_per_day`` per day, with an optional filter (the AI model).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time
from math import cos, pi, sin

import numpy as np

from trading_bot.backtesting.news_day import NY, execute
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, Sizing
from trading_bot.backtesting.sweep_strategy import TradingDay

ADR_DAYS = 20
ZONE = 0.05  # x ADR
STOP_BUFFERS = (0.05, 0.15)  # x ADR beyond the zone and the wick
SWING_SIDE = 3  # hourly candles each side
SWING_DAYS = 10
SWING_MERGE = 0.1  # x ADR
MIN_TOUCHES = 2
BLOCK_TOUCHES = 3  # a swing level blocks the way to the target only from 3 turns
ROUND_STEP = 50.0
FIRST_CLOSE, LAST_CLOSE = time(3, 0), time(13, 0)
ASIA_END = time(2, 0)
LAST_EXIT = time(16, 45)
RETEST_CANDLES = 8
MIN_STOP, MAX_STOP = 5.0, 30.0
NO_LEVEL_TARGET_R = 3.0
NEXT_LEVEL_MIN_R = 1.5


@dataclass
class Level:
    price: float
    kinds: set[str] = field(default_factory=set)
    touches: int = 1


@dataclass(frozen=True)
class Setup:
    day: date
    kind: str  # bounce | retest
    direction: int
    level: float
    level_kinds: frozenset[str]
    touches: int
    entry_minute: int
    stop_base: float  # beyond the zone and the wick, before the buffer
    candle_close_minute: int  # last 1-minute index of the setup candle
    adr: float
    features: dict[str, float]


def adr_at(days: Sequence[TradingDay], k: int) -> float | None:
    if k < ADR_DAYS:
        return None
    return float(np.mean([d.high - d.low for d in days[k - ADR_DAYS : k]]))


def merge_levels(levels: list[Level], z: float) -> list[Level]:
    out: list[Level] = []
    for lv in sorted(levels, key=lambda x: x.price):
        if out and lv.price - out[-1].price <= z:
            last = out[-1]
            w = last.touches + lv.touches
            last.price = (last.price * last.touches + lv.price * lv.touches) / w
            last.kinds |= lv.kinds
            last.touches = w
        else:
            out.append(Level(lv.price, set(lv.kinds), lv.touches))
    return out


def swing_levels(hi: Array, lo: Array, merge: float) -> list[Level]:
    """Grouped hourly turning points with at least MIN_TOUCHES turns."""
    n = SWING_SIDE
    pts: list[float] = []
    for i in range(n, len(hi) - n):
        if hi[i] > hi[i - n : i].max() and hi[i] > hi[i + 1 : i + n + 1].max():
            pts.append(float(hi[i]))
        if lo[i] < lo[i - n : i].min() and lo[i] < lo[i + 1 : i + n + 1].min():
            pts.append(float(lo[i]))
    groups = merge_levels([Level(p, {"swing"}) for p in pts], merge)
    return [g for g in groups if g.touches >= MIN_TOUCHES]


def _ny_epoch(d: date, t: time) -> int:
    return int(datetime.combine(d, t, tzinfo=NY).timestamp())


@dataclass(frozen=True)
class Mids:
    o: Array
    h: Array
    lo: Array
    c: Array

    @classmethod
    def of(cls, bars: dict[str, Array]) -> Mids:
        return cls(
            (bars["bid_open"] + bars["ask_open"]) / 2,
            (bars["bid_high"] + bars["ask_high"]) / 2,
            (bars["bid_low"] + bars["ask_low"]) / 2,
            (bars["bid_close"] + bars["ask_close"]) / 2,
        )


def _hourly(m: Array, mid: Mids, i0: int, i1: int) -> tuple[Array, Array]:
    key = m[i0:i1] // 3600
    _, start = np.unique(key, return_index=True)
    return (
        np.maximum.reduceat(mid.h[i0:i1], start),
        np.minimum.reduceat(mid.lo[i0:i1], start),
    )


def day_levels(
    bars: dict[str, Array], mid: Mids, days: Sequence[TradingDay], k: int, adr: float
) -> list[Level]:
    """Levels known at the start of trading day k (Asian range not included)."""
    prev = days[k - 1]
    lv = [Level(prev.high, {"prev_day"}), Level(prev.low, {"prev_day"})]
    # last week = trading days in the previous Monday-Friday week
    wk = days[k].day.isocalendar()[:2]
    last_week = [
        d
        for d in days[max(0, k - 10) : k]
        if d.day.isocalendar()[:2] != wk and d.day < days[k].day
    ]
    if last_week:
        lw = last_week[-1].day.isocalendar()[:2]
        same = [d for d in last_week if d.day.isocalendar()[:2] == lw]
        lv += [
            Level(max(d.high for d in same), {"prev_week"}),
            Level(min(d.low for d in same), {"prev_week"}),
        ]
    first = days[max(0, k - SWING_DAYS)].i0
    hi, lo = _hourly(bars["minute_utc"], mid, first, days[k].i0)
    lv += swing_levels(hi, lo, SWING_MERGE * adr)
    o = days[k].open
    r = ROUND_STEP
    for x in np.arange(np.floor((o - 2 * adr) / r) * r, o + 2 * adr + r, r):
        lv.append(Level(float(x), {"round"}))
    return lv


def _candles15(m: Array, i0: int, i1: int) -> tuple[Array, Array]:
    """Start and end (exclusive) 1-minute indices of each 15-minute bucket."""
    key = m[i0:i1] // 900
    _, start = np.unique(key, return_index=True)
    start = start + i0
    end = np.concatenate([start[1:], [i1]])
    return start, end


def find_setups(
    bars: dict[str, Array], days: Sequence[TradingDay], k: int, mid: Mids
) -> list[Setup]:
    d = days[k]
    adr = adr_at(days, k)
    if adr is None or adr <= 0 or k < 1:
        return []
    m = bars["minute_utc"]
    z = ZONE * adr
    base = day_levels(bars, mid, days, k, adr)
    asia_end = _ny_epoch(d.day, ASIA_END)
    a1 = int(np.searchsorted(m, asia_end))
    asia: list[Level] = []
    if a1 > d.i0:
        asia = [
            Level(float(mid.h[d.i0 : a1].max()), {"asia"}),
            Level(float(mid.lo[d.i0 : a1].min()), {"asia"}),
        ]
    levels = merge_levels(base + asia, z)
    early = merge_levels(base, z)
    t_first = _ny_epoch(d.day, FIRST_CLOSE)
    t_last = _ny_epoch(d.day, LAST_CLOSE)
    starts, ends = _candles15(m, d.i0, d.i1)
    co = mid.o[starts]
    ch = np.maximum.reduceat(mid.h[d.i0 : d.i1], starts - d.i0)
    cl = np.minimum.reduceat(mid.lo[d.i0 : d.i1], starts - d.i0)
    cc = mid.c[ends - 1]
    close_t = (m[starts] // 900 + 1) * 900
    vol5 = float(np.mean([x.high - x.low for x in days[k - 5 : k]])) / adr
    out: list[Setup] = []
    used: set[tuple[str, float, int]] = set()
    breaks: dict[tuple[float, int], int] = {}  # (level, direction) -> candle idx
    t_scan = t_first - RETEST_CANDLES * 900
    for j in range(1, len(starts)):
        t = int(close_t[j])
        if t < t_scan:
            continue
        for lv in levels if t > asia_end else early:
            L = lv.price
            li = round(L, 2)
            for direction in (1, -1):
                s_ = direction
                # work in "buy" orientation: support below, price above
                o, h, lo_, c, pc = (
                    s_ * co[j],
                    s_ * ch[j] if s_ == 1 else -cl[j],
                    s_ * cl[j] if s_ == 1 else -ch[j],
                    s_ * cc[j],
                    s_ * cc[j - 1],
                )
                lvl = s_ * L
                rng = h - lo_
                if rng <= 0:
                    continue
                # break: opened at/below the level, closed above the zone
                if o <= lvl and c > lvl + z:
                    breaks[(li, direction)] = j
                setup = None
                if (
                    pc > lvl + z
                    and lvl - 3 * z <= lo_ <= lvl + z
                    and c > lvl + z
                    and c >= lo_ + 0.6 * rng
                ):
                    setup = "bounce"
                b = breaks.get((li, direction))
                if setup is None and b is not None and b < j <= b + RETEST_CANDLES:
                    if c < lvl - z:
                        breaks.pop((li, direction))
                    elif lo_ <= lvl + z and c > lvl + z and c >= lo_ + 0.5 * rng:
                        setup = "retest"
                        breaks.pop((li, direction))
                if setup is None or not (t_first <= t <= t_last):
                    continue
                key = (setup, li, direction)
                if key in used:
                    continue
                used.add(key)
                e = int(ends[j])  # first minute after the candle
                if e >= d.i1 or m[e] - t > 120:
                    continue
                stop_base = s_ * min(lo_, lvl - z)
                out.append(
                    Setup(
                        day=d.day,
                        kind=setup,
                        direction=direction,
                        level=L,
                        level_kinds=frozenset(lv.kinds),
                        touches=lv.touches,
                        entry_minute=e,
                        stop_base=stop_base,
                        candle_close_minute=e - 1,
                        adr=adr,
                        features=_features(
                            bars,
                            mid,
                            d,
                            j,
                            starts,
                            cc,
                            direction,
                            lv,
                            setup,
                            adr,
                            vol5,
                            rng,
                            c - o,
                            t,
                        ),
                    )
                )
    return out


FEATURES = (
    "retest",
    "buy",
    "prev_day",
    "prev_week",
    "swing",
    "round",
    "asia",
    "touches",
    "hour_sin",
    "hour_cos",
    "weekday",
    "vol_ratio",
    "candle_range",
    "candle_body",
    "approach_1h",
    "day_move",
    "day_range",
    "trend_20h",
)


def _features(
    bars: dict[str, Array],
    mid: Mids,
    d: TradingDay,
    j: int,
    starts: Array,
    cc: Array,
    direction: int,
    lv: Level,
    setup: str,
    adr: float,
    vol5: float,
    rng: float,
    body: float,
    t: int,
) -> dict[str, float]:
    e = int(starts[j + 1]) if j + 1 < len(starts) else d.i1
    price = float(cc[j])
    prev4 = float(cc[max(0, j - 4)])
    i20 = max(0, e - 20 * 60)
    local = datetime.fromtimestamp(t, NY)
    hour = local.hour + local.minute / 60
    return {
        "retest": float(setup == "retest"),
        "buy": float(direction == 1),
        "prev_day": float("prev_day" in lv.kinds),
        "prev_week": float("prev_week" in lv.kinds),
        "swing": float("swing" in lv.kinds),
        "round": float("round" in lv.kinds),
        "asia": float("asia" in lv.kinds),
        "touches": float(lv.touches),
        "hour_sin": sin(2 * pi * hour / 24),
        "hour_cos": cos(2 * pi * hour / 24),
        "weekday": float(local.weekday()),
        "vol_ratio": vol5,
        "candle_range": rng / adr,
        "candle_body": body / adr,
        "approach_1h": direction * (price - prev4) / adr,
        "day_move": direction * (price - d.open) / adr,
        "day_range": float(mid.h[d.i0 : e].max() - mid.lo[d.i0 : e].min()) / adr,
        "trend_20h": direction * (price - float(mid.c[i20:e].mean())) / adr,
    }


@dataclass(frozen=True)
class TargetRule:
    name: str  # "1R", "1.5R", "next"
    r: float | None  # fixed multiple; None = next level


TARGETS = (TargetRule("1R", 1.0), TargetRule("1.5R", 1.5), TargetRule("next", None))


@dataclass(frozen=True)
class Candidate:
    setup: Setup
    target: str
    buffer: float
    trade: HoldTrade

    @property
    def win(self) -> bool:
        return self.trade.pnl_usd > 0


def simulate(
    bars: dict[str, Array],
    mid: Mids,
    days: Sequence[TradingDay],
    k: int,
    s: Setup,
    rule: TargetRule,
    costs: CostModel,
    all_levels: Sequence[float],
    buffer: float,
) -> HoldTrade | None:
    d = days[k]
    m = bars["minute_utc"]
    e = s.entry_minute
    stop = s.stop_base - s.direction * buffer * s.adr
    entry_mid = float(mid.o[e])
    risk_mid = (entry_mid - stop) * s.direction
    if not (MIN_STOP <= risk_mid <= MAX_STOP):
        return None
    z = ZONE * s.adr
    # today's high/low so far also block the way
    hi = float(mid.h[d.i0 : e].max())
    lo = float(mid.lo[d.i0 : e].min())
    ahead = sorted(
        (p - entry_mid) * s.direction
        for p in (*all_levels, hi, lo)
        if (p - entry_mid) * s.direction > z and abs(p - s.level) > z
    )
    room = ahead[0] - z if ahead else None
    if rule.r is None:
        if room is None:
            target_r = NO_LEVEL_TARGET_R
        else:
            target_r = room / risk_mid
            if target_r < NEXT_LEVEL_MIN_R:
                return None
            target_r = min(target_r, NO_LEVEL_TARGET_R)
    else:
        target_r = rule.r
        if room is not None and room < target_r * risk_mid:
            return None
    cap = _ny_epoch(d.day, LAST_EXIT)
    last = int(np.searchsorted(m, cap, side="right")) - 1
    last = min(last, d.i1 - 1)
    return execute(
        bars,
        d.day,
        e,
        last,
        s.direction,
        costs,
        Sizing(),
        stop=stop,
        target_r=target_r,
    )


def candidates(
    bars: dict[str, Array],
    days: Sequence[TradingDay],
    years: range,
    costs: CostModel,
) -> dict[tuple[str, float], list[Candidate]]:
    """Every setup, with its trade under each (target rule, stop buffer), for days
    in `years`."""
    mid = Mids.of(bars)
    out: dict[tuple[str, float], list[Candidate]] = {
        (r.name, b): [] for r in TARGETS for b in STOP_BUFFERS
    }
    for k, d in enumerate(days):
        if d.day.year not in years or k < ADR_DAYS:
            continue
        setups = find_setups(bars, days, k, mid)
        if not setups:
            continue
        adr = setups[0].adr
        lv = [
            x.price
            for x in day_levels(bars, mid, days, k, adr)
            if x.kinds != {"swing"} or x.touches >= BLOCK_TOUCHES
        ]
        a1 = int(np.searchsorted(bars["minute_utc"], _ny_epoch(d.day, ASIA_END)))
        if a1 > d.i0:
            lv += [float(mid.h[d.i0 : a1].max()), float(mid.lo[d.i0 : a1].min())]
        for s in setups:
            for rule in TARGETS:
                for b in STOP_BUFFERS:
                    t = simulate(bars, mid, days, k, s, rule, costs, lv, b)
                    if t is not None:
                        out[(rule.name, b)].append(Candidate(s, rule.name, b, t))
    return out


def take(
    cands: Sequence[Candidate],
    *,
    kinds: frozenset[str] = frozenset({"bounce", "retest"}),
    keep: Callable[[Candidate], bool] | None = None,
    max_per_day: int = 2,
) -> list[HoldTrade]:
    """One trade at a time, at most max_per_day a day, optional filter."""
    out: list[HoldTrade] = []
    busy_until = -1
    per_day: dict[date, int] = {}
    for c in sorted(cands, key=lambda c: c.setup.entry_minute):
        s = c.setup
        if s.kind not in kinds or s.entry_minute <= busy_until:
            continue
        if per_day.get(s.day, 0) >= max_per_day:
            continue
        if keep is not None and not keep(c):
            continue
        out.append(c.trade)
        busy_until = c.trade.exit_bar
        per_day[s.day] = per_day.get(s.day, 0) + 1
    return out


def feature_matrix(cands: Sequence[Candidate]) -> Array:
    rows = [[c.setup.features[f] for f in FEATURES] for c in cands]
    for row, c in zip(rows, cands, strict=True):
        risk = abs(c.trade.entry - c.trade.stop)
        row.append(risk / c.setup.adr)
        tgt = c.trade.target
        row.append(abs(tgt - c.trade.entry) / risk if tgt is not None else 0.0)
    return np.array(rows, dtype=float)


FEATURE_NAMES = (*FEATURES, "stop_adr", "target_r")
