"""Adverse-only pluggable execution price adjustments."""

from decimal import Decimal
from typing import Protocol

from trading_bot.backtesting.orders import Side


class SlippageModel(Protocol):
    def apply(self, price: Decimal, side: Side) -> Decimal: ...
    def manifest(self) -> dict[str, str]: ...


class BasisPointsSlippageModel:
    def __init__(self, bps: Decimal) -> None:
        if not bps.is_finite() or not 0 <= bps < 10000:
            raise ValueError("slippage bps must lie in [0,10000)")
        self.bps = bps

    def apply(self, price: Decimal, side: Side) -> Decimal:
        return price * (1 + (self.bps if side == Side.BUY else -self.bps) / 10000)

    def manifest(self) -> dict[str, str]:
        return {"name": "basis_points", "version": "1", "bps": str(self.bps)}


class ZeroSlippageModel(BasisPointsSlippageModel):
    def __init__(self) -> None:
        super().__init__(Decimal(0))
