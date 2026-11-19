"""Explain each session-hold trade: prices, gross result, every cost, and excursions.

For a trade from ``session_hold`` this recovers:

* entry/exit times and mid prices (the price before any spread or cost);
* the gross result at mid price, then the recorded spread, the extra spread plus
  slippage, and commission, which together give the net result exactly;
* MFE / MAE: the furthest the mid price moved in our favour / against us between
  entry and exit, in $/oz and in R (R = distance from mid entry to the stop).

MFE tells whether entries were good (price did go our way) and exits gave it back;
a small MFE means the entry itself was poor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from trading_bot.backtesting.session_hold import HoldTrade, SessionDay
from trading_bot.backtesting.session_window import CostModel


@dataclass(frozen=True)
class TradeAnatomy:
    day: str
    direction: str
    entry_time_utc: str
    exit_time_utc: str
    hold_minutes: int
    exit_reason: str
    lots: float
    entry_mid: float
    entry_fill: float
    stop: float
    target: float | None
    exit_mid: float
    exit_fill: float
    risk_per_oz: float
    gross_per_oz: float
    gross_usd: float
    spread_usd: float
    extra_spread_slippage_usd: float
    commission_usd: float
    net_usd: float
    mfe_per_oz: float
    mae_per_oz: float
    mfe_r: float
    mae_r: float
    move_5m_per_oz: float  # mid move in our favour 5 minutes after entry
    move_15m_per_oz: float


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%d %H:%M")


def explain(day: SessionDay, t: HoldTrade, costs: CostModel) -> TradeAnatomy:
    b, j, k, d = day.bars, t.entry_minute, t.exit_bar, t.direction
    half_in = float(b["ask_open"][j] - b["bid_open"][j]) / 2
    entry_mid = float(b["bid_open"][j]) + half_in
    if t.exit_reason == "time_exit":
        half_out = float(b["ask_close"][k] - b["bid_close"][k]) / 2
    else:
        half_out = float(b["ask_open"][k] - b["bid_open"][k]) / 2
    # exit fill = bid level - per_fill (long) or ask level + per_fill (short)
    if d == 1:
        exit_mid = t.exit + costs.per_fill + half_out
    else:
        exit_mid = t.exit - costs.per_fill - half_out
    oz = costs.contract_size_oz * t.lots
    gross_per_oz = (exit_mid - entry_mid) * d
    hi = day.mid("high")[j : k + 1]
    lo = day.mid("low")[j : k + 1]
    mfe = float((hi.max() - entry_mid) if d == 1 else (entry_mid - lo.min()))
    mae = float((entry_mid - lo.min()) if d == 1 else (hi.max() - entry_mid))
    risk = abs(entry_mid - t.stop) or 1e-9
    close = day.mid("close")

    def move_after(minutes: int) -> float:
        i = min(j + minutes - 1, len(close) - 1)
        return float((close[i] - entry_mid) * d)

    return TradeAnatomy(
        day=t.day.isoformat(),
        direction="BUY" if d == 1 else "SELL",
        entry_time_utc=_iso(int(day.minutes[j])),
        exit_time_utc=_iso(int(day.minutes[k])),
        hold_minutes=t.hold_minutes,
        exit_reason=t.exit_reason,
        lots=t.lots,
        entry_mid=round(entry_mid, 3),
        entry_fill=round(t.entry, 3),
        stop=round(t.stop, 3),
        target=None if t.target is None else round(t.target, 3),
        exit_mid=round(exit_mid, 3),
        exit_fill=round(t.exit, 3),
        risk_per_oz=round(risk, 3),
        gross_per_oz=round(gross_per_oz, 3),
        gross_usd=round(gross_per_oz * oz, 2),
        spread_usd=round((half_in + half_out) * oz, 2),
        extra_spread_slippage_usd=round(2 * costs.per_fill * oz, 2),
        commission_usd=round(costs.commission_per_lot * t.lots, 2),
        net_usd=round(t.pnl_usd, 2),
        mfe_per_oz=round(mfe, 3),
        mae_per_oz=round(mae, 3),
        mfe_r=round(mfe / risk, 3),
        mae_r=round(mae / risk, 3),
        move_5m_per_oz=round(move_after(5), 3),
        move_15m_per_oz=round(move_after(15), 3),
    )
