"""Human-readable report makes gross, execution costs and net results explicit."""

from trading_bot.backtesting.results import BacktestResult


def render(result: BacktestResult) -> str:
    metrics = result.metrics
    lines = [
        "SIMULATED TEST OUTPUT — NOT STRATEGY PERFORMANCE EVIDENCE",
        f"Run: {result.run_id}",
        f"Status: {result.status}",
        f"Configuration: {result.config_key}",
        "Market: NSE CASH / INTRADAY",
    ]
    for label, key in (
        ("Starting capital", "starting_capital"),
        ("Ending equity", "ending_equity"),
        ("Gross P&L before slippage/costs", "gross_pnl"),
        ("Slippage estimate", "estimated_slippage_cost"),
        ("Brokerage", "brokerage"),
        ("Taxes and fees", "taxes_fees"),
        ("Net P&L", "net_pnl"),
        ("Trades", "number_of_trades"),
        ("Win rate", "win_rate"),
        ("Profit factor", "profit_factor"),
        ("Max drawdown", "max_drawdown"),
        ("Max drawdown fraction", "max_drawdown_pct"),
    ):
        lines.append(f"{label}: {metrics[key]}")
    if result.warnings:
        lines.append("Warnings: " + ", ".join(result.warnings))
    return "\n".join(lines)
