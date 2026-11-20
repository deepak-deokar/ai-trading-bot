"""A small machine-learning model that reads gold's reaction to US news.

Design, fixed before any result was seen:

* Events: jobs report, CPI (08:30 New York) and scheduled Fed statements (14:00),
  at most one per day (config/us_news_events.csv). Data 2014-2024 only.
* Decision time: the end of the 15-minute news candle (08:45 / 14:15). Every
  input is known at that moment.
* Trade: buy or sell at the next minute's open with a symmetric stop and target
  of R = half the average daily range of the last 20 trading days (1:1, normal
  touch stop), closed at the time limit (12:00, or 16:45 for the Fed) if neither
  is hit. At most one trade per event.
* Label (what the model learns): 1 if a buy would win, 0 if a sell would win,
  judged on mid prices: which of entry +R / entry -R is touched first (a minute
  touching both counts as a loss for the buy); if neither, the sign of the move
  at the time limit.
* Model: logistic regression with L2 regularisation on standardised inputs
  (numpy, no external ML library). It outputs P(a buy wins). Buy if P >= 0.5 +
  margin, sell if P <= 0.5 - margin, otherwise skip.
* Validation: walk-forward by year inside 2014-2024. To trade year Y the model is
  trained only on years before Y. 2025 and 2026 are never used.

Inputs (all scaled by the 20-day average daily range, "ADR", unless noted):
event type; the news candle's move, size and where it closed inside its range;
today's move before the news; the 5- and 20-day trend; where price sits inside
yesterday's range; room to the first support/resistance level above and below;
today's range before the news; whether the news candle broke yesterday's or
today's high/low.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from trading_bot.backtesting.levels import key_levels, room
from trading_bot.backtesting.news_day import (
    CANDLE,
    MAX_ENTRY_DELAY_MIN,
    MIN_CANDLE_MINUTES,
    NewsEvent,
    _until,
    execute,
)
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, Sizing
from trading_bot.backtesting.sweep_strategy import TradingDay

ADR_DAYS = 20
RISK_ADR_FRACTION = 0.5
ROOM_CAP = 3.0  # room to a level, in ADR, capped (no level ahead = the cap)

FEATURES = (
    "is_jobs",
    "is_cpi",
    "news_move",
    "news_range",
    "news_close_pos",
    "pre_news_move",
    "trend_5d",
    "trend_20d",
    "pos_in_yday_range",
    "room_up",
    "room_down",
    "pre_news_range",
    "broke_level",
)


@dataclass(frozen=True)
class EventRow:
    event: NewsEvent
    entry_minute: int
    last_minute: int
    entry_mid: float
    risk: float  # R in $/oz
    features: tuple[float, ...]
    label: int  # 1 = a buy wins, 0 = a sell wins


def _mid(bars: dict[str, Array], part: str, sl: slice | int) -> Array:
    return (bars[f"bid_{part}"][sl] + bars[f"ask_{part}"][sl]) / 2


def label_for(
    mid_high: Array, mid_low: Array, mid_close_last: float, entry: float, risk: float
) -> int:
    """1 if +R is touched before -R (or, if neither, the close is above entry)."""
    up = np.flatnonzero(mid_high >= entry + risk)
    down = np.flatnonzero(mid_low <= entry - risk)
    first_up = int(up[0]) if len(up) else None
    first_down = int(down[0]) if len(down) else None
    if first_up is None and first_down is None:
        return int(mid_close_last > entry)
    if first_down is None:
        return 1
    if first_up is None:
        return 0
    return int(first_up < first_down)  # same minute counts against the buy


def build_row(
    bars: dict[str, Array],
    days: Sequence[TradingDay],
    k: int,
    ev: NewsEvent,
) -> EventRow | None:
    """Inputs and label for one event on trading day k (None if data is missing)."""
    if k < ADR_DAYS + 1:
        return None
    m = bars["minute_utc"]
    t0, t1 = ev.utc(), ev.utc(CANDLE)
    a, b = int(np.searchsorted(m, t0)), int(np.searchsorted(m, t1))
    if (
        b - a < MIN_CANDLE_MINUTES
        or b >= len(m)
        or m[b] - t1 > MAX_ENTRY_DELAY_MIN * 60
    ):
        return None
    last = int(np.searchsorted(m, ev.utc(_until(ev)))) - 1
    if last <= b:
        return None
    adr = float(np.mean([d.high - d.low for d in days[k - ADR_DAYS : k]]))
    if adr <= 0:
        return None
    today, prev = days[k], days[k - 1]
    n_open = float(_mid(bars, "open", a))
    n_close = float(_mid(bars, "close", b - 1))
    n_hi = float(_mid(bars, "high", slice(a, b)).max())
    n_lo = float(_mid(bars, "low", slice(a, b)).min())
    entry_mid = float(_mid(bars, "open", b))
    if a > today.i0:
        pre_hi = float(_mid(bars, "high", slice(today.i0, a)).max())
        pre_lo = float(_mid(bars, "low", slice(today.i0, a)).min())
    else:
        pre_hi = pre_lo = n_open
    levels = key_levels(bars, days, k, a)
    up = room(levels, entry_mid, 1)
    down = room(levels, entry_mid, -1)
    prev_range = prev.high - prev.low
    top, bottom = max(prev.high, pre_hi), min(prev.low, pre_lo)
    broke = 1.0 if n_close > top else -1.0 if n_close < bottom else 0.0
    features = (
        float(ev.kind == "nfp"),
        float(ev.kind == "cpi"),
        (n_close - n_open) / adr,
        (n_hi - n_lo) / adr,
        ((n_close - n_lo) / (n_hi - n_lo) - 0.5) if n_hi > n_lo else 0.0,
        (n_open - prev.close) / adr,
        (n_open - days[k - 5].close) / adr,
        (n_open - days[k - ADR_DAYS].close) / adr,
        (
            float(np.clip((entry_mid - prev.low) / prev_range - 0.5, -2, 2))
            if prev_range > 0
            else 0.0
        ),
        min(ROOM_CAP, up / adr) if up is not None else ROOM_CAP,
        min(ROOM_CAP, down / adr) if down is not None else ROOM_CAP,
        (pre_hi - pre_lo) / adr,
        broke,
    )
    risk = RISK_ADR_FRACTION * adr
    label = label_for(
        _mid(bars, "high", slice(b, last + 1)),
        _mid(bars, "low", slice(b, last + 1)),
        float(_mid(bars, "close", last)),
        entry_mid,
        risk,
    )
    return EventRow(ev, b, last, entry_mid, risk, features, label)


def build_rows(
    bars: dict[str, Array],
    days: Sequence[TradingDay],
    events: Sequence[NewsEvent],
    years: range,
) -> list[EventRow]:
    index = {d.day: k for k, d in enumerate(days)}
    rows = []
    for ev in events:
        if ev.day.year not in years or ev.day not in index:
            continue
        row = build_row(bars, days, index[ev.day], ev)
        if row is not None:
            rows.append(row)
    return rows


@dataclass(frozen=True)
class LogisticModel:
    mean: Array
    scale: Array
    weights: Array  # one per feature, on standardised inputs
    bias: float

    def proba(self, x: Array) -> Array:
        z = ((x - self.mean) / self.scale) @ self.weights + self.bias
        return 1.0 / (1.0 + np.exp(-z))


def fit_logistic(
    x: Array, y: Array, l2: float = 1.0, iterations: int = 50
) -> LogisticModel:
    """L2-regularised logistic regression by Newton's method (bias not penalised)."""
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    z = (x - mean) / scale
    a = np.hstack([z, np.ones((len(z), 1))])
    w = np.zeros(a.shape[1])
    penalty = np.full(a.shape[1], l2)
    penalty[-1] = 0.0
    for _ in range(iterations):
        p = 1.0 / (1.0 + np.exp(-(a @ w)))
        grad = a.T @ (p - y) + penalty * w
        hess = (a * (p * (1 - p))[:, None]).T @ a + np.diag(penalty)
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return LogisticModel(mean, scale, w[:-1], float(w[-1]))


def walk_forward(
    rows: Sequence[EventRow], first_test_year: int, l2: float = 1.0
) -> dict[int, tuple[float, LogisticModel]]:
    """P(buy wins) per row index, each from a model trained on earlier years."""
    out: dict[int, tuple[float, LogisticModel]] = {}
    years = sorted({r.event.day.year for r in rows})
    x = np.array([r.features for r in rows])
    y = np.array([r.label for r in rows], dtype=float)
    yr = np.array([r.event.day.year for r in rows])
    for year in years:
        if year < first_test_year:
            continue
        train = yr < year
        if train.sum() < 30 or len(set(y[train])) < 2:
            continue
        model = fit_logistic(x[train], y[train], l2)
        p = model.proba(x[yr == year])
        for i, prob in zip(np.flatnonzero(yr == year), p, strict=True):
            out[int(i)] = (float(prob), model)
    return out


def trade_row(
    bars: dict[str, Array],
    row: EventRow,
    direction: int,
    costs: CostModel,
    sizing: Sizing,
) -> HoldTrade | None:
    """Execute the 1:1 trade for one event in the given direction."""
    return execute(
        bars,
        row.event.day,
        row.entry_minute,
        row.last_minute,
        direction,
        costs,
        sizing,
        risk=row.risk,
        target_r=1.0,
    )
