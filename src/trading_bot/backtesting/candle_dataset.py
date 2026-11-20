"""Candle-pattern inputs at every hour of the trading day.

Decision times: every full hour of the 17:00-17:00 New York trading day from
18:00 to 15:00 (gold is closed 17:00-18:00). Everything is known at the decision
time: only finished candles are used.

Inputs (all prices in units of the 20-day average daily range, ADR):

* the last 24 five-minute candles (2 hours): body (close - open), upper wick,
  lower wick, and the candle's close relative to the current price;
* the last 24 hourly candles: the same four, plus what happened inside each
  hour - the share of its twelve 5-minute candles that closed green, and how
  choppy it was (root-mean-square of its 1-minute moves);
* time: hour of day (as a circle), weekday, and 5-day vs 20-day volatility.

The candles are the last 24 that actually traded, so the daily 17:00-18:00
break, nights without ticks and weekends are skipped rather than left empty.

Labels, one per holding time h (30, 60, 120, 240 minutes): would a 1:1 buy win?
Stop and target R = 0.5 x ADR x sqrt(h / 240) (so a 4-hour hold uses half the
ADR, as before). On mid prices: +R touched before -R wins, a minute touching
both loses, and if neither, the close at the end of the hold decides. A hold
must end by 16:45 New York the same trading day, otherwise that label is
missing (nothing is held across the 17:00 close).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from math import cos, pi, sin, sqrt

import numpy as np

from trading_bot.backtesting.news_day import NY
from trading_bot.backtesting.news_model import label_for
from trading_bot.backtesting.session_window import Array
from trading_bot.backtesting.sweep_strategy import TradingDay

N5, NH = 24, 24
ADR_DAYS = 20
HOLDS = (30, 60, 120, 240)
DECISION_HOURS = (
    18,
    19,
    20,
    21,
    22,
    23,
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
)
LAST_EXIT = time(16, 45)
MAX_ENTRY_GAP_SECONDS = 120


def feature_names() -> list[str]:
    names = []
    for i in range(N5, 0, -1):
        names += [f"m5_{i}_body", f"m5_{i}_upper", f"m5_{i}_lower", f"m5_{i}_dist"]
    for i in range(NH, 0, -1):
        names += [
            f"h1_{i}_body",
            f"h1_{i}_upper",
            f"h1_{i}_lower",
            f"h1_{i}_dist",
            f"h1_{i}_green_share",
            f"h1_{i}_chop",
        ]
    names += ["hour_sin", "hour_cos", "mon", "tue", "wed", "thu", "fri", "vol_ratio"]
    return names


@dataclass(frozen=True)
class Buckets:
    ids: Array  # bucket number (epoch // seconds), ascending
    open: Array
    high: Array
    low: Array
    close: Array
    extra: dict[str, Array]


def _buckets(bars: dict[str, Array], seconds: int) -> Buckets:
    m = bars["minute_utc"]
    key = m // seconds
    ids, start = np.unique(key, return_index=True)
    end = np.concatenate([start[1:], [len(m)]])
    mo = (bars["bid_open"] + bars["ask_open"]) / 2
    mh = (bars["bid_high"] + bars["ask_high"]) / 2
    ml = (bars["bid_low"] + bars["ask_low"]) / 2
    mc = (bars["bid_close"] + bars["ask_close"]) / 2
    return Buckets(
        ids,
        mo[start],
        np.maximum.reduceat(mh, start),
        np.minimum.reduceat(ml, start),
        mc[end - 1],
        {"start": start, "end": end},
    )


def build_buckets(bars: dict[str, Array]) -> tuple[Buckets, Buckets]:
    """5-minute and hourly mid candles; hourly ones carry green share and chop."""
    b5 = _buckets(bars, 300)
    bh = _buckets(bars, 3600)
    # green share of the 5-minute candles inside each hour
    hour_of_5 = b5.ids * 300 // 3600
    green = (b5.close > b5.open).astype(float)
    pos = np.searchsorted(bh.ids, hour_of_5)
    count = np.bincount(pos, minlength=len(bh.ids)).astype(float)
    greens = np.bincount(pos, weights=green, minlength=len(bh.ids))
    share = np.divide(greens, count, out=np.full(len(bh.ids), 0.5), where=count > 0)
    # chop: root-mean-square of 1-minute mid close changes inside the hour
    mc = (bars["bid_close"] + bars["ask_close"]) / 2
    d2 = np.concatenate([[0.0], np.diff(mc) ** 2])
    d2[bh.extra["start"]] = 0.0  # no change across hour boundaries
    sums = np.add.reduceat(d2, bh.extra["start"])
    n = np.maximum(bh.extra["end"] - bh.extra["start"] - 1, 1)
    bh.extra["green_share"] = share
    bh.extra["chop"] = np.sqrt(sums / n)
    return b5, bh


def _window(b: Buckets, last_id: int, n: int) -> Array | None:
    """Indices of the last n traded buckets ending at or before last_id
    (closed hours such as nights, the daily 17:00 break and weekends skip)."""
    end = int(np.searchsorted(b.ids, last_id, side="right")) - 1
    if end - n + 1 < 0:
        return None
    return np.arange(end - n + 1, end + 1)


def _candles(
    b: Buckets, idx: Array, price: float, adr: float, extra: Sequence[str]
) -> list[float]:
    out: list[float] = []
    prev_close = None
    for i in idx:
        if i < 0:
            c = prev_close if prev_close is not None else price
            vals = [0.0, 0.0, 0.0, (c - price) / adr] + [
                0.5 if e == "green_share" else 0.0 for e in extra
            ]
        else:
            o, h, lo, c = b.open[i], b.high[i], b.low[i], b.close[i]
            vals = [
                (c - o) / adr,
                (h - max(o, c)) / adr,
                (min(o, c) - lo) / adr,
                (c - price) / adr,
            ] + [float(b.extra[e][i]) / (adr if e == "chop" else 1.0) for e in extra]
        prev_close = c
        out += [float(v) for v in vals]
    return out


@dataclass(frozen=True)
class CandleRows:
    day: list[date]  # trading day
    hour: Array  # New York decision hour
    entry_minute: Array
    adr: Array
    x: Array
    last_minute: dict[int, Array]  # hold -> last minute index (-1 = not allowed)
    risk: dict[int, Array]
    label: dict[int, Array]  # hold -> 1/0, or -1 if not allowed

    @property
    def year(self) -> Array:
        return np.array([d.year for d in self.day])


def build(
    bars: dict[str, Array], days: Sequence[TradingDay], years: range
) -> CandleRows:
    b5, bh = build_buckets(bars)
    m = bars["minute_utc"]
    mh = (bars["bid_high"] + bars["ask_high"]) / 2
    ml = (bars["bid_low"] + bars["ask_low"]) / 2
    mc = (bars["bid_close"] + bars["ask_close"]) / 2
    mo = (bars["bid_open"] + bars["ask_open"]) / 2
    xs, out_day, out_hour, out_s, out_adr = [], [], [], [], []
    lasts: dict[int, list[int]] = {h: [] for h in HOLDS}
    risks: dict[int, list[float]] = {h: [] for h in HOLDS}
    labels: dict[int, list[int]] = {h: [] for h in HOLDS}
    for k, d in enumerate(days):
        if d.day.year not in years or k < ADR_DAYS + 1:
            continue
        ranges = [x.high - x.low for x in days[k - ADR_DAYS : k]]
        adr = float(np.mean(ranges))
        if adr <= 0:
            continue
        vol_ratio = float(np.mean(ranges[-5:])) / adr
        exit_cap = int(datetime.combine(d.day, LAST_EXIT, tzinfo=NY).timestamp())
        for hour in DECISION_HOURS:
            local_day = d.day - timedelta(days=1) if hour >= 18 else d.day
            dt = datetime.combine(local_day, time(hour, 0), tzinfo=NY)
            if dt.weekday() == 5:  # Saturday never trades
                continue
            t = int(dt.timestamp())
            s = int(np.searchsorted(m, t))
            if s >= d.i1 or s < d.i0 or m[s] - t > MAX_ENTRY_GAP_SECONDS:
                continue
            idx5 = _window(b5, t // 300 - 1, N5)
            idxh = _window(bh, t // 3600 - 1, NH)
            if idx5 is None or idxh is None:
                continue
            price = float(mo[s])
            wd = dt.astimezone(NY).weekday()
            # a Sunday-evening decision belongs to Monday's trading day
            weekday = (wd + 1) % 7 if hour >= 18 else wd
            row = (
                _candles(b5, idx5, price, adr, ())
                + _candles(bh, idxh, price, adr, ("green_share", "chop"))
                + [
                    sin(2 * pi * hour / 24),
                    cos(2 * pi * hour / 24),
                    *[float(weekday == i) for i in range(5)],
                    vol_ratio,
                ]
            )
            xs.append(row)
            out_day.append(d.day)
            out_hour.append(hour)
            out_s.append(s)
            out_adr.append(adr)
            for h in HOLDS:
                end_t = t + h * 60
                last = int(np.searchsorted(m, end_t)) - 1
                risk = 0.5 * adr * sqrt(h / 240)
                if end_t > exit_cap or last <= s or last >= d.i1:
                    lasts[h].append(-1)
                    risks[h].append(risk)
                    labels[h].append(-1)
                    continue
                sl = slice(s, last + 1)
                lab = label_for(mh[sl], ml[sl], float(mc[last]), price, risk)
                lasts[h].append(last)
                risks[h].append(risk)
                labels[h].append(lab)
    return CandleRows(
        day=out_day,
        hour=np.array(out_hour),
        entry_minute=np.array(out_s),
        adr=np.array(out_adr),
        x=np.array(xs),
        last_minute={h: np.array(v) for h, v in lasts.items()},
        risk={h: np.array(v) for h, v in risks.items()},
        label={h: np.array(v) for h, v in labels.items()},
    )


def epoch_to_ny(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, UTC).astimezone(NY)
