"""Candle-by-candle trade replays rendered as a self-contained HTML page.

For each trade this collects the mid-price candles around it (default 5-minute),
where the entry, stop, target and exit sit, and what the result was made of:
the price move at mid price, then the recorded spread, the extra spread plus
slippage, and commission. These add up to the trade's net result exactly.

A strategy can add context to show while replaying: a price zone (a shaded band)
and highlighted candle ranges with a label and a one-line explanation (for the
sweep strategy: the sweep candle and the confirmation candle).

Trades must index the same 1-minute ``bars`` arrays passed in here
(``entry_minute`` and ``exit_bar`` are positions in those arrays).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel
from trading_bot.backtesting.sweep_strategy import (
    TradingDay,
    to_15m,
    zones_for,
)

NY = ZoneInfo("America/New_York")
TEMPLATE = Path(__file__).with_name("trade_replay.html")
DATA_MARKER = "__REPLAY_DATA__"


@dataclass(frozen=True)
class Highlight:
    first_minute: int  # 1-minute index, inclusive
    last_minute: int  # 1-minute index, inclusive
    label: str  # short tag drawn on the chart, e.g. "SWEEP"
    explain: str  # one sentence shown when the replay reaches the end of it


@dataclass(frozen=True)
class ReplayContext:
    zone: tuple[float, float] | None = None
    zone_label: str = ""
    highlights: tuple[Highlight, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CostSplit:
    entry_mid: float
    exit_mid: float
    gross_usd: float
    spread_usd: float
    extra_usd: float  # extra spread + slippage, both fills
    commission_usd: float


def cost_split(
    bars: dict[str, Array], t: HoldTrade, costs: CostModel, exit_at_close: bool
) -> CostSplit:
    """Split a trade's net result into mid-price move and each cost.

    ``exit_at_close``: whether the exit filled at that minute's close (time exits,
    candle-close stops) rather than at a level touched inside the minute.
    """
    j, k, d = t.entry_minute, t.exit_bar, t.direction
    half_in = float(bars["ask_open"][j] - bars["bid_open"][j]) / 2
    entry_mid = float(bars["bid_open"][j]) + half_in
    part = "close" if exit_at_close else "open"
    half_out = float(bars[f"ask_{part}"][k] - bars[f"bid_{part}"][k]) / 2
    exit_mid = t.exit + d * (costs.per_fill + half_out)
    oz = costs.contract_size_oz * t.lots
    return CostSplit(
        entry_mid=entry_mid,
        exit_mid=exit_mid,
        gross_usd=(exit_mid - entry_mid) * d * oz,
        spread_usd=(half_in + half_out) * oz,
        extra_usd=2 * costs.per_fill * oz,
        commission_usd=costs.commission_per_lot * t.lots,
    )


def _local(epoch: int, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(epoch, UTC).astimezone(tz).strftime("%Y-%m-%d %H:%M")


def candles(
    bars: dict[str, Array], first: int, last: int, minutes: int, tz: ZoneInfo
) -> tuple[list[list[Any]], Array]:
    """Mid candles of `minutes` length over 1-minute indices [first, last).

    Returns rows [HH:MM, open, high, low, close] and each candle's first index.
    """
    m = bars["minute_utc"][first:last]
    rel = np.flatnonzero(np.diff(m // (minutes * 60), prepend=-1))
    starts = rel + first
    ends = np.concatenate([starts[1:], [last]])
    mh = (bars["bid_high"] + bars["ask_high"]) / 2
    ml = (bars["bid_low"] + bars["ask_low"]) / 2
    mo = (bars["bid_open"] + bars["ask_open"]) / 2
    mc = (bars["bid_close"] + bars["ask_close"]) / 2
    rows = [
        [
            _local(int(bars["minute_utc"][s]), tz)[11:],
            round(float(mo[s]), 2),
            round(float(mh[s:e].max()), 2),
            round(float(ml[s:e].min()), 2),
            round(float(mc[e - 1]), 2),
        ]
        for s, e in zip(starts, ends, strict=True)
    ]
    return rows, starts


def replay_record(
    bars: dict[str, Array],
    t: HoldTrade,
    costs: CostModel,
    *,
    exit_at_close: bool,
    window: tuple[int, int],
    context: ReplayContext | None = None,
    candle_minutes: int = 5,
    tz: ZoneInfo = NY,
) -> dict[str, Any]:
    """Everything the replay page needs for one trade, as plain JSON values.

    ``window`` is the 1-minute index range [first, last) to draw; it must contain
    the entry and exit minutes.
    """
    first, last = window
    if not first <= t.entry_minute <= t.exit_bar < last:
        raise ValueError("window must contain the whole trade")
    ctx = context or ReplayContext()
    rows, starts = candles(bars, first, last, candle_minutes, tz)

    def at(i: int) -> int:
        return int(np.searchsorted(starts, i, side="right") - 1)

    c = cost_split(bars, t, costs, exit_at_close)
    m = bars["minute_utc"]
    return {
        "day": t.day.isoformat(),
        "dir": "BUY" if t.direction == 1 else "SELL",
        "reason": t.exit_reason,
        "entry_time": _local(int(m[t.entry_minute]), tz),
        "exit_time": _local(int(m[t.exit_bar]), tz),
        "lots": t.lots,
        "entry_mid": round(c.entry_mid, 2),
        "entry_fill": round(t.entry, 2),
        "stop": round(t.stop, 2),
        "target": None if t.target is None else round(t.target, 2),
        "exit_mid": round(c.exit_mid, 2),
        "exit_fill": round(t.exit, 2),
        "gross": round(c.gross_usd, 2),
        "spread": round(c.spread_usd, 2),
        "extra": round(c.extra_usd, 2),
        "comm": round(c.commission_usd, 2),
        "net": round(t.pnl_usd, 2),
        "hold": t.hold_minutes,
        "zone": None if ctx.zone is None else [round(z, 2) for z in ctx.zone],
        "zone_label": ctx.zone_label,
        "highlights": [
            {
                "from": at(h.first_minute),
                "to": at(h.last_minute),
                "label": h.label,
                "explain": h.explain,
            }
            for h in ctx.highlights
            if first <= h.first_minute and h.last_minute < last
        ],
        "entry_i": at(t.entry_minute),
        "exit_i": at(t.exit_bar),
        "candles": rows,
    }


def sweep_context(
    bars: dict[str, Array], days: Sequence[TradingDay], k: int, t: HoldTrade
) -> ReplayContext:
    """Zone, sweep candle and confirmation candle for a sweep-strategy trade."""
    zones = zones_for(days, k)
    c = to_15m(bars, days[k].i0, days[k].i1)
    q_entry = int(np.searchsorted(c.start, t.entry_minute))
    conf = q_entry - 1
    sell = t.direction == -1
    highlights: list[Highlight] = []
    for q in range(conf - 1, max(conf - 6, 0) - 1, -1):
        extreme = c.high[q] if sell else c.low[q]
        if abs(float(extreme) - t.stop) < 1e-9:
            highlights.append(
                Highlight(
                    int(c.start[q]),
                    int(c.end[q]) - 1,
                    "SWEEP",
                    "Sweep: price poked "
                    + (
                        "above the previous candle's high inside the sell zone, "
                        "then closed back below it."
                        if sell
                        else "below the previous candle's low inside the buy zone, "
                        "then closed back above it."
                    ),
                )
            )
            break
    if conf >= 0:
        highlights.append(
            Highlight(
                int(c.start[conf]),
                int(c.end[conf]) - 1,
                "CONFIRM",
                "Confirmation: the candle closed "
                + ("below the sweep candle's low" if sell else "above its high")
                + ". Entry comes at the next candle's open.",
            )
        )
    if zones is None:
        return ReplayContext(highlights=tuple(highlights))
    zone = (
        (zones.supply_bottom, zones.supply_top)
        if sell
        else (zones.demand_bottom, zones.demand_top)
    )
    label = (
        "SELL ZONE (yesterday's upper wick)"
        if sell
        else ("BUY ZONE (yesterday's lower wick)")
    )
    return ReplayContext(zone, label, tuple(highlights))


def equity_points(trades: Sequence[HoldTrade]) -> list[list[Any]]:
    total = 0.0
    out: list[list[Any]] = []
    for t in trades:
        total += t.pnl_usd
        out.append([t.day.isoformat(), round(total, 2)])
    return out


def render_page(
    *,
    title: str,
    subtitle: str,
    rules: Sequence[str],
    records: Sequence[dict[str, Any]],
    all_trades: Sequence[HoldTrade],
    note: str = "",
) -> str:
    mix = {
        r: sum(t.exit_reason == r for t in all_trades)
        for r in ("stop", "trail", "target", "time_exit")
    }
    payload = {
        "title": title,
        "subtitle": subtitle,
        "rules": list(rules),
        "note": note,
        "trades": list(records),
        "summary": {
            "n": len(all_trades),
            "net": round(sum(t.pnl_usd for t in all_trades), 2),
            "mix": mix,
            "equity": equity_points(all_trades),
        },
    }
    data = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text()
    return html.replace("__TITLE__", _escape(title)).replace(DATA_MARKER, data)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
