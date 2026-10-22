"""Machine-readable simulated fills, trades, equity and reproducibility metadata."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import field_validator

from trading_bot.backtesting.costs import CostBreakdown
from trading_bot.backtesting.events import Event
from trading_bot.backtesting.orders import Side, SimOrder
from trading_bot.domain.models import DomainModel


class Fill(DomainModel):
    fill_id: str
    order_id: str
    symbol: str
    side: Side
    quantity: int
    timestamp: datetime
    bar_open: datetime
    base_price: Decimal
    price: Decimal
    costs: CostBreakdown
    slippage_cost: Decimal
    reason: str


class Trade(DomainModel):
    trade_id: str
    symbol: str
    side: str = "LONG"
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    entry_quantity: int
    gross_pnl: Decimal
    execution_pnl: Decimal
    costs: CostBreakdown
    slippage_cost: Decimal
    net_pnl: Decimal
    holding_seconds: Decimal
    exit_reason: str


class EquityPoint(DomainModel):
    timestamp: datetime
    cash: Decimal
    reserved_cash: Decimal = Decimal(0)
    market_value: Decimal
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    peak: Decimal
    drawdown: Decimal
    drawdown_pct: Decimal


class BacktestResult(DomainModel):
    run_id: UUID
    config_key: str
    manifest: dict[str, Any]
    status: str
    orders: tuple[SimOrder, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    equity: tuple[EquityPoint, ...]
    events: tuple[Event, ...]
    metrics: dict[str, Any]
    warnings: tuple[str, ...]

    @field_validator("metrics", mode="before")
    @classmethod
    def financial_metrics(cls, value: dict[str, Any]) -> dict[str, Any]:
        # JSON stores exact financial quantities as strings; restore them on reads.
        result = dict(value)
        keys = (
            "starting_capital",
            "ending_equity",
            "gross_pnl",
            "execution_pnl",
            "net_pnl",
            "total_costs",
            "brokerage",
            "taxes_fees",
            "estimated_slippage_cost",
            "total_return",
            "win_rate",
            "gross_profit",
            "gross_loss",
            "profit_factor",
            "average_winner",
            "average_loser",
            "expectancy",
            "largest_winner",
            "largest_loser",
            "max_drawdown",
            "max_drawdown_pct",
            "turnover",
            "average_holding_seconds",
        )
        for key in keys:
            if result.get(key) is not None:
                result[key] = Decimal(str(result[key]))
                if not result[key].is_finite():
                    raise ValueError("non-finite financial metric")
        for key in ("cost_breakdown", "daily_pnl"):
            if key in result:
                result[key] = {k: Decimal(str(v)) for k, v in result[key].items()}
        return result

    def deterministic_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"run_id"})
