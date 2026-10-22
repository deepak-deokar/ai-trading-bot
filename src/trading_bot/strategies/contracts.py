"""Immutable, current-symbol observations and strategy request contracts."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from trading_bot.backtesting.orders import BacktestError, TradeIntent
from trading_bot.domain.models import Bar


class StrategyError(BacktestError):
    """Invalid strategy configuration, observation or evaluation."""


class IntentValidationError(StrategyError):
    """A strategy request violates its current observation boundary."""


@dataclass(frozen=True)
class StrategyContext:
    current_time: datetime
    bar: Bar
    available_at: datetime
    features: Mapping[str, float | None]
    unavailable: Mapping[str, str]
    position_quantity: int
    average_entry_price: Decimal
    cash: Decimal
    equity: Decimal
    session_open: datetime
    session_close: datetime
    strategy_identity: str
    parameters: Mapping[str, str | int | float | bool | None]

    def validate(self) -> None:
        if not (
            self.bar.timestamp < self.available_at <= self.current_time
            and self.session_open <= self.bar.timestamp < self.session_close
            and self.current_time <= self.session_close
        ):
            raise StrategyError("unavailable or out-of-session strategy context")


@runtime_checkable
class Strategy(Protocol):
    def evaluate(self, context: StrategyContext) -> Sequence[TradeIntent]:
        """Return requests, or an empty sequence for normal no-action."""
        ...
