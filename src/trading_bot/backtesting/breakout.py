"""Level breakouts with wider stops, measured with and without costs.

Rules: docs/xauusd-breakout-plan.md (written before running). Breakout signals come
from ``sr_compare.find_signals`` (kind "breakout"). This module adds the stop
variants, a mid-price "no costs" world, and R-multiple helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

from trading_bot.backtesting.news_day import execute
from trading_bot.backtesting.session_window import Array, CostModel, Sizing
from trading_bot.backtesting.sr_compare import (
    MAX_STOP_USD,
    Result,
    Signal,
    last_minute,
    risk_ok,
)
from trading_bot.backtesting.sr_strategy import Mids
from trading_bot.backtesting.sweep_strategy import TradingDay

LEVELS = ("prev_day", "swing", "prev_day+swing")
STOPS: tuple[float | None, ...] = (None, 0.25, 0.4, 0.6, 0.8)  # None = behind level
TARGETS: tuple[float | None, ...] = (1.0, 1.5, 2.0, None)  # None = hold to 16:45
NO_COSTS = CostModel(
    extra_spread_per_oz=0.0, commission_per_lot=0.0, slippage_per_oz=0.0
)


@dataclass(frozen=True)
class Variant:
    levels: str
    stop_adr: float | None
    target_r: float | None

    @property
    def name(self) -> str:
        stop = "level" if self.stop_adr is None else f"{self.stop_adr}ADR"
        tgt = "close" if self.target_r is None else f"{self.target_r}R"
        return f"{self.levels} / stop {stop} / target {tgt}"


VARIANTS = tuple(Variant(lv, s, t) for lv in LEVELS for s in STOPS for t in TARGETS)


def mid_bars(bars: dict[str, Array]) -> dict[str, Array]:
    """The same minutes with bid = ask = mid: fills at the mid price, no spread."""
    out = {"minute_utc": bars["minute_utc"]}
    for part in ("open", "high", "low", "close"):
        m = (bars[f"bid_{part}"] + bars[f"ask_{part}"]) / 2
        out[f"bid_{part}"] = m
        out[f"ask_{part}"] = m
    return out


def stop_for(s: Signal, mid: Mids, stop_adr: float | None) -> float | None:
    """Stop level for the variant, or None when the stop distance is not allowed."""
    entry_mid = float(mid.o[s.entry_minute])
    if stop_adr is None:
        risk = (entry_mid - s.stop) * s.direction
        return s.stop if risk_ok(risk, s.adr) else None
    risk = stop_adr * s.adr
    if risk > MAX_STOP_USD:
        return None
    return entry_mid - s.direction * risk


def simulate(
    bars: dict[str, Array],
    mid: Mids,
    d: TradingDay,
    s: Signal,
    v: Variant,
    costs: CostModel,
) -> Result | None:
    stop = stop_for(s, mid, v.stop_adr)
    if stop is None:
        return None
    risk_mid = (float(mid.o[s.entry_minute]) - stop) * s.direction
    t = execute(
        bars,
        d.day,
        s.entry_minute,
        last_minute(bars, d),
        s.direction,
        costs,
        Sizing(),
        stop=stop,
        target_r=v.target_r,
    )
    return None if t is None else Result(s, v.target_r, risk_mid, t)


def r_of(r: Result, contract_oz: float = 100.0) -> float:
    """Profit after costs over the money lost if the stop is hit (entry fill to
    stop). Without costs the fill is the mid price, so this is the plain price move
    over the stop distance."""
    t = r.trade
    risk = t.lots * contract_oz * abs(t.entry - t.stop)
    return t.pnl_usd / risk if risk > 0 else 0.0
