"""Decimal long inventory and flat-to-flat trade accounting, no leverage."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from trading_bot.backtesting.costs import ZERO, CostBreakdown
from trading_bot.backtesting.orders import BacktestError, Side
from trading_bot.backtesting.results import EquityPoint, Fill, Trade


@dataclass
class Position:
    quantity: int = 0
    basis: Decimal = ZERO
    entered_at: datetime | None = None
    bought: int = 0
    buy_value: Decimal = ZERO
    sell_value: Decimal = ZERO
    realized: Decimal = ZERO
    costs: CostBreakdown = field(default_factory=CostBreakdown)
    slippage: Decimal = ZERO

    @property
    def average_price(self) -> Decimal:
        return self.basis / self.quantity if self.quantity else ZERO


class Portfolio:
    def __init__(self, starting_cash: Decimal) -> None:
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.positions: dict[str, Position] = {}
        self.realized = ZERO
        self.fees = ZERO
        self.cash_spent = ZERO
        self.cash_received = ZERO
        self.peak = starting_cash
        self.trades: list[Trade] = []

    def quantity(self, symbol: str) -> int:
        return self.positions.get(symbol, Position()).quantity

    def apply(self, fill: Fill) -> None:
        position = self.positions.setdefault(fill.symbol, Position())
        turnover = fill.quantity * fill.price
        if fill.side == Side.BUY:
            if turnover + fill.costs.total > self.cash:
                raise BacktestError("insufficient cash")
            self.cash -= turnover + fill.costs.total
            self.cash_spent += turnover
            if position.quantity == 0:
                position.entered_at = fill.timestamp
            position.quantity += fill.quantity
            position.basis += turnover
            position.bought += fill.quantity
            position.buy_value += turnover
        else:
            if fill.quantity > position.quantity:
                raise BacktestError("short selling is not implemented")
            basis = (
                position.basis
                if fill.quantity == position.quantity
                else position.basis * fill.quantity / position.quantity
            )
            pnl = turnover - basis
            self.cash += turnover - fill.costs.total
            self.cash_received += turnover
            self.realized += pnl
            position.realized += pnl
            position.basis -= basis
            position.quantity -= fill.quantity
            position.sell_value += turnover
        self.fees += fill.costs.total
        position.costs = position.costs.plus(fill.costs)
        position.slippage += fill.slippage_cost
        if position.quantity == 0:
            assert position.entered_at is not None
            self.trades.append(
                Trade(
                    trade_id=f"trade-{len(self.trades)+1:06}",
                    symbol=fill.symbol,
                    entry_time=position.entered_at,
                    exit_time=fill.timestamp,
                    entry_price=position.buy_value / position.bought,
                    exit_price=position.sell_value / position.bought,
                    entry_quantity=position.bought,
                    gross_pnl=position.realized + position.slippage,
                    execution_pnl=position.realized,
                    costs=position.costs,
                    slippage_cost=position.slippage,
                    net_pnl=position.realized - position.costs.total,
                    holding_seconds=Decimal(
                        str((fill.timestamp - position.entered_at).total_seconds())
                    ),
                    exit_reason=fill.reason,
                )
            )
            self.positions[fill.symbol] = Position()

    def mark(self, timestamp: datetime, prices: dict[str, Decimal]) -> EquityPoint:
        value = sum(
            (p.quantity * prices[s] for s, p in self.positions.items() if p.quantity),
            ZERO,
        )
        basis = sum((p.basis for p in self.positions.values()), ZERO)
        equity = self.cash + value
        self.peak = max(self.peak, equity)
        return EquityPoint(
            timestamp=timestamp,
            cash=self.cash,
            market_value=value,
            equity=equity,
            realized_pnl=self.realized,
            unrealized_pnl=value - basis,
            gross_exposure=value,
            net_exposure=value,
            peak=self.peak,
            drawdown=self.peak - equity,
            drawdown_pct=(self.peak - equity) / self.peak,
        )
