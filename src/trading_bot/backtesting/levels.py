"""Simple, objective support and resistance levels for intraday gold.

For a moment inside trading day ``k`` (17:00-17:00 New York, see sweep_strategy):

* yesterday's high and low (previous trading day, mid prices);
* today's high and low so far (from 17:00 New York up to, not including, the
  given minute).

These are the levels most intraday traders watch. ``room`` measures how far price
can travel in the trade's direction before reaching the first level, and
``protected`` says whether a level sits between the entry and the stop (the stop
is "behind" support or resistance).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from trading_bot.backtesting.session_window import Array
from trading_bot.backtesting.sweep_strategy import TradingDay


@dataclass(frozen=True)
class Level:
    price: float
    name: str


def key_levels(
    bars: dict[str, Array], days: Sequence[TradingDay], k: int, until: int
) -> list[Level]:
    """Levels known at 1-minute index `until` on trading day k (k >= 1)."""
    if k < 1:
        raise ValueError("need a previous trading day")
    prev, today = days[k - 1], days[k]
    out = [
        Level(prev.high, "Yesterday's high"),
        Level(prev.low, "Yesterday's low"),
    ]
    if until > today.i0:
        sl = slice(today.i0, until)
        hi = float(((bars["bid_high"][sl] + bars["ask_high"][sl]) / 2).max())
        lo = float(((bars["bid_low"][sl] + bars["ask_low"][sl]) / 2).min())
        out += [Level(hi, "Today's high so far"), Level(lo, "Today's low so far")]
    return out


def room(levels: Sequence[Level], entry: float, direction: int) -> float | None:
    """Distance from entry to the first level ahead (None if none ahead)."""
    ahead = [
        (lv.price - entry) * direction
        for lv in levels
        if (lv.price - entry) * direction > 0
    ]
    return min(ahead) if ahead else None


def protected(levels: Sequence[Level], entry: float, stop: float) -> bool:
    """True if a level lies strictly between the entry and the stop."""
    lo, hi = sorted((entry, stop))
    return any(lo < lv.price < hi for lv in levels)
