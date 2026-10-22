"""Equity metrics; daily ratios require sufficient nondegenerate samples."""

import math
from decimal import Decimal
from statistics import mean, stdev
from typing import Any

from trading_bot.backtesting.costs import ZERO, CostBreakdown
from trading_bot.backtesting.results import EquityPoint, Fill, Trade
from trading_bot.data.calendar import IST


def performance(
    equity: list[EquityPoint], fills: list[Fill], trades: list[Trade]
) -> dict[str, Any]:
    initial, ending = equity[0].equity, equity[-1].equity
    costs = CostBreakdown()
    for fill in fills:
        costs = costs.plus(fill.costs)
    slip = sum((f.slippage_cost for f in fills), ZERO)
    winners = [t.net_pnl for t in trades if t.net_pnl > 0]
    losers = [t.net_pnl for t in trades if t.net_pnl < 0]
    profit, loss = sum(winners, ZERO), sum(losers, ZERO)
    daily: dict[str, Decimal] = {}
    for point in equity[1:]:
        daily[point.timestamp.astimezone(IST).date().isoformat()] = point.equity
    returns = []
    daily_pnl = {}
    previous = initial
    for date, value in sorted(daily.items()):
        daily_pnl[date] = value - previous
        returns.append(float(value / previous - 1))
        previous = value
    sharpe = sortino = None
    if len(returns) >= 20 and stdev(returns) > 0:
        sharpe = mean(returns) / stdev(returns) * math.sqrt(252)
        downside = math.sqrt(sum(min(r, 0) ** 2 for r in returns) / len(returns))
        if downside > 0:
            sortino = mean(returns) / downside * math.sqrt(252)
    exposed = total = 0.0
    for left, right in zip(equity, equity[1:], strict=False):
        if (
            left.timestamp.astimezone(IST).date()
            == right.timestamp.astimezone(IST).date()
        ):
            duration = (right.timestamp - left.timestamp).total_seconds()
            total += duration
            exposed += duration if left.gross_exposure > 0 else 0
    return dict(
        starting_capital=initial,
        ending_equity=ending,
        gross_pnl=ending - initial + costs.total + slip,
        execution_pnl=ending - initial + costs.total,
        net_pnl=ending - initial,
        total_costs=costs.total,
        cost_breakdown=costs.model_dump(),
        brokerage=costs.brokerage,
        taxes_fees=costs.total - costs.brokerage,
        estimated_slippage_cost=slip,
        total_return=(ending - initial) / initial,
        number_of_trades=len(trades),
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=Decimal(len(winners)) / len(trades) if trades else None,
        gross_profit=profit,
        gross_loss=-loss,
        profit_factor=profit / (-loss) if loss else None,
        average_winner=profit / len(winners) if winners else None,
        average_loser=loss / len(losers) if losers else None,
        expectancy=(
            sum((t.net_pnl for t in trades), ZERO) / len(trades) if trades else None
        ),
        largest_winner=max(winners) if winners else None,
        largest_loser=min(losers) if losers else None,
        max_drawdown=max(p.drawdown for p in equity),
        max_drawdown_pct=max(p.drawdown_pct for p in equity),
        turnover=sum((f.price * f.quantity for f in fills), ZERO),
        average_holding_seconds=(
            sum((t.holding_seconds for t in trades), ZERO) / len(trades)
            if trades
            else None
        ),
        exposure_percentage=100 * exposed / total if total else 0,
        sharpe=sharpe,
        sortino=sortino,
        ratio_policy=(
            "daily closes; 252 sessions/year; zero risk-free; " "minimum 20 sessions"
        ),
        daily_pnl=daily_pnl,
    )
