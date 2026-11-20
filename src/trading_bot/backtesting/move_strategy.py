"""Breakout trade for mornings the model expects to be busy.

At 08:00 New York two stop orders wait: buy if the mid price rises k x ADR above
the 08:00 price, sell if it falls k x ADR below (ADR = 20-day average daily
range). The first one hit is the trade; its stop is the other level, its target
``target_r`` times the risk; anything open closes at 12:00. If both levels are
hit inside the same minute the day is skipped (order unknown).

Fills: a triggered buy fills at the trigger level or the minute's open if price
jumped past it, plus half the recorded spread and the cost model's extra spread
and slippage (sells mirror). Stops are checked from the entry minute, targets
from the next minute (conservative); a minute touching both counts as a stop.
"""

from __future__ import annotations

import numpy as np

from trading_bot.backtesting.daily_model import DayRow
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, Sizing, lots_for


def _first(mask: Array) -> int:
    hits = np.flatnonzero(mask)
    return int(hits[0]) if len(hits) else -1


def breakout_trade(
    bars: dict[str, Array],
    row: DayRow,
    k: float,
    target_r: float,
    costs: CostModel,
    sizing: Sizing,
) -> HoldTrade | None:
    s, last = row.entry_minute, row.last_minute
    adr = 2 * row.risk  # DayRow.risk is half the ADR
    up, dn = row.entry_mid + k * adr, row.entry_mid - k * adr
    sl = slice(s, last + 1)
    mid_h = (bars["bid_high"][sl] + bars["ask_high"][sl]) / 2
    mid_l = (bars["bid_low"][sl] + bars["ask_low"][sl]) / 2
    i_up, i_dn = _first(mid_h >= up), _first(mid_l <= dn)
    if i_up < 0 and i_dn < 0:
        return None
    if i_up >= 0 and (i_dn < 0 or i_up < i_dn):
        direction, j, stop = 1, s + i_up, dn
    elif i_dn >= 0 and (i_up < 0 or i_dn < i_up):
        direction, j, stop = -1, s + i_dn, up
    else:
        return None  # both in the same minute
    pf = costs.per_fill
    half = float(bars["ask_open"][j] - bars["bid_open"][j]) / 2
    mid_open = float(bars["ask_open"][j] + bars["bid_open"][j]) / 2
    if direction == 1:
        entry = max(up, mid_open) + half + pf
    else:
        entry = min(dn, mid_open) - half - pf
    lots = lots_for(entry, stop, costs, sizing)
    if lots == 0.0:
        return None
    target = entry + direction * target_r * abs(entry - stop)
    sl2 = slice(j, last + 1)
    if direction == 1:
        hit_stop = _first(bars["bid_low"][sl2] <= stop)
        tgt = bars["bid_high"][sl2] >= target
    else:
        hit_stop = _first(bars["ask_high"][sl2] >= stop)
        tgt = bars["ask_low"][sl2] <= target
    tgt[0] = False  # targets only from the minute after entry
    hit_target = _first(tgt)
    candidates = [
        (x, r) for x, r in ((hit_stop, "stop"), (hit_target, "target")) if x >= 0
    ]
    if candidates:
        k_rel, reason = min(candidates, key=lambda c: (c[0], c[1] != "stop"))
    else:
        k_rel, reason = last - j, "time_exit"
    e = j + k_rel
    side_open = bars["bid_open"][e] if direction == 1 else bars["ask_open"][e]
    if reason == "stop":
        level = min(stop, side_open) if direction == 1 else max(stop, side_open)
        if k_rel == 0:  # stopped in the entry minute: assume the stop level
            level = stop
    elif reason == "target":
        level = max(target, side_open) if direction == 1 else min(target, side_open)
    else:
        level = bars["bid_close"][e] if direction == 1 else bars["ask_close"][e]
    exit_px = float(level) - direction * pf
    pnl = (exit_px - entry) * direction * costs.contract_size_oz * lots
    pnl -= costs.commission_per_lot * lots
    m = bars["minute_utc"]
    hold = int((m[e] - m[j]) // 60) + 1
    return HoldTrade(
        row.day, direction, j, entry, stop, exit_px, lots, pnl, reason, hold, e, target
    )
