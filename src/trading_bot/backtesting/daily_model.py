"""Every-day model: gold's direction from 08:00 to 12:00 New York.

Design, fixed before any result was seen:

* Every trading day 2014-2024 with data at 08:00 New York (2025 and 2026 are not
  used). Decision with everything known before 08:00; entry at the 08:00 minute's
  open.
* Trade: buy or sell with a symmetric stop and target of R = half the 20-day
  average daily range (1:1, normal touch stop), closed at 12:00 New York if
  neither is hit.
* Label: 1 if a buy would win (on mid prices: entry +R touched before entry -R;
  same minute counts against the buy; if neither, the close at 12:00 above the
  entry), else 0.
* Inputs:
  - gold: the overnight move since yesterday's close and the overnight range,
    where 08:00 sits inside the overnight range, yesterday's candle, 5- and
    20-day trend, where price sits inside yesterday's range, room to the first
    support/resistance level above and below, short- vs long-term volatility
    (all in units of the 20-day average daily range, ADR);
  - other markets, previous US close (known before 08:00): US dollar index 1-
    and 5-day % change, US 10-year yield 1- and 5-day change, 10-year minus
    3-month yield, S&P 500 1-day % change, VIX level and 1-day change;
  - calendar (known in advance): jobs report, CPI or Fed decision today.
* Model: the same L2 logistic regression and year-by-year walk-forward as
  ``news_model`` (train on earlier years only).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from math import log

import numpy as np

from trading_bot.backtesting.levels import key_levels, room
from trading_bot.backtesting.news_day import NY, NewsEvent, execute
from trading_bot.backtesting.news_model import label_for
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, Sizing
from trading_bot.backtesting.sweep_strategy import TradingDay
from trading_bot.data.macro_daily import MacroHistory

DECIDE_AT = time(8, 0)
EXIT_AT = time(12, 0)
ADR_DAYS = 20
RISK_ADR_FRACTION = 0.5
ROOM_CAP = 3.0
MAX_ENTRY_GAP_SECONDS = 120

FEATURES = (
    "overnight_move",
    "overnight_range",
    "pos_in_overnight",
    "yday_candle",
    "trend_5d",
    "trend_20d",
    "pos_in_yday_range",
    "room_up",
    "room_down",
    "vol_ratio",
    "usd_1d",
    "usd_5d",
    "us10y_1d",
    "us10y_5d",
    "curve_10y_3m",
    "spx_1d",
    "vix_level",
    "vix_1d",
    "jobs_today",
    "cpi_today",
    "fed_today",
)


@dataclass(frozen=True)
class DayRow:
    day: date
    entry_minute: int
    last_minute: int
    entry_mid: float
    risk: float
    features: tuple[float, ...]
    label: int

    @property
    def year(self) -> int:
        return self.day.year


def _utc(day: date, at: time) -> int:
    return int(datetime.combine(day, at, tzinfo=NY).timestamp())


def _mid(bars: dict[str, Array], part: str, sl: slice | int) -> Array:
    return (bars[f"bid_{part}"][sl] + bars[f"ask_{part}"][sl]) / 2


def _pct(series: list[float], back: int) -> float | None:
    if len(series) <= back or series[-1 - back] == 0:
        return None
    return 100.0 * (series[-1] / series[-1 - back] - 1.0)


def build_row(
    bars: dict[str, Array],
    days: Sequence[TradingDay],
    k: int,
    macro: MacroHistory,
    events_today: set[str],
) -> DayRow | None:
    if k < ADR_DAYS + 1:
        return None
    today, prev = days[k], days[k - 1]
    m = bars["minute_utc"]
    t_entry, t_exit = _utc(today.day, DECIDE_AT), _utc(today.day, EXIT_AT)
    s = int(np.searchsorted(m, t_entry))
    last = int(np.searchsorted(m, t_exit)) - 1
    if s >= len(m) or m[s] - t_entry > MAX_ENTRY_GAP_SECONDS or last <= s:
        return None
    if s <= today.i0 or last >= today.i1:
        return None
    ranges = [d.high - d.low for d in days[k - ADR_DAYS : k]]
    adr = float(np.mean(ranges))
    if adr <= 0:
        return None
    adr5 = float(np.mean(ranges[-5:]))
    entry_mid = float(_mid(bars, "open", s))
    on_hi = float(_mid(bars, "high", slice(today.i0, s)).max())
    on_lo = float(_mid(bars, "low", slice(today.i0, s)).min())
    levels = key_levels(bars, days, k, s)
    up, down = room(levels, entry_mid, 1), room(levels, entry_mid, -1)
    prev_range = prev.high - prev.low

    usd = macro.closes_before(today.day, "usd", 6)
    y10 = macro.closes_before(today.day, "us10y", 6)
    y3m = macro.closes_before(today.day, "us3m", 1)
    spx = macro.closes_before(today.day, "spx", 2)
    vix = macro.closes_before(today.day, "vix", 2)
    usd_1d, usd_5d, spx_1d = _pct(usd, 1), _pct(usd, 5), _pct(spx, 1)
    if (
        usd_1d is None
        or usd_5d is None
        or spx_1d is None
        or len(y10) < 6
        or not y3m
        or len(vix) < 2
    ):
        return None

    features = (
        (entry_mid - prev.close) / adr,
        (on_hi - on_lo) / adr,
        ((entry_mid - on_lo) / (on_hi - on_lo) - 0.5) if on_hi > on_lo else 0.0,
        (prev.close - prev.open) / adr,
        (entry_mid - days[k - 5].close) / adr,
        (entry_mid - days[k - ADR_DAYS].close) / adr,
        (
            float(np.clip((entry_mid - prev.low) / prev_range - 0.5, -2, 2))
            if prev_range > 0
            else 0.0
        ),
        min(ROOM_CAP, up / adr) if up is not None else ROOM_CAP,
        min(ROOM_CAP, down / adr) if down is not None else ROOM_CAP,
        adr5 / adr,
        usd_1d,
        usd_5d,
        y10[-1] - y10[-2],
        y10[-1] - y10[0],
        y10[-1] - y3m[-1],
        spx_1d,
        log(vix[-1]),
        vix[-1] - vix[-2],
        float("nfp" in events_today),
        float("cpi" in events_today),
        float("fomc" in events_today),
    )
    risk = RISK_ADR_FRACTION * adr
    label = label_for(
        _mid(bars, "high", slice(s, last + 1)),
        _mid(bars, "low", slice(s, last + 1)),
        float(_mid(bars, "close", last)),
        entry_mid,
        risk,
    )
    return DayRow(today.day, s, last, entry_mid, risk, features, label)


def build_rows(
    bars: dict[str, Array],
    days: Sequence[TradingDay],
    macro: MacroHistory,
    events: Sequence[NewsEvent],
    years: range,
) -> list[DayRow]:
    """One row per trading day (weekday) in `years`. All events of a day count,
    so pass the raw calendar (not de-duplicated)."""
    by_day: dict[date, set[str]] = {}
    for e in events:
        by_day.setdefault(e.day, set()).add(e.kind)
    rows = []
    for k, d in enumerate(days):
        if d.day.year not in years or d.day.weekday() >= 5:
            continue
        row = build_row(bars, days, k, macro, by_day.get(d.day, set()))
        if row is not None:
            rows.append(row)
    return rows


def trade_row(
    bars: dict[str, Array],
    row: DayRow,
    direction: int,
    costs: CostModel,
    sizing: Sizing,
) -> HoldTrade | None:
    return execute(
        bars,
        row.day,
        row.entry_minute,
        row.last_minute,
        direction,
        costs,
        sizing,
        risk=row.risk,
        target_r=1.0,
    )
