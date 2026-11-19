"""Per-trade logs and entry/exit diagnosis for the step-2b session-hold rules.

For four rules (each plan's plain version and its best filtered version), every
2014-2024 trade is written to docs/trade-logs/<plan>__<rule>.csv with entry/exit
times and prices, gross result before costs, each cost, and how far price moved
for (MFE) and against (MAE) the trade. A summary goes to
docs/xauusd-trade-anatomy.{md,json}. 2025 and 2026 are not used.

Usage: PYTHONPATH=src .venv/bin/python scripts/explain_xauusd_trades.py
"""

import csv
import json
import statistics
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from trading_bot.backtesting.session_hold import (
    PLANS,
    HoldRule,
    extract_session_days,
    simulate_session,
)
from trading_bot.backtesting.session_window import CostModel, Sizing, load_bars
from trading_bot.backtesting.trade_anatomy import TradeAnatomy, explain
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
LOG_DIR = Path("docs/trade-logs")
OUT = Path("docs/xauusd-trade-anatomy")
DEV_YEARS = range(2014, 2025)
SELECTED = {
    "london_asia_break": [HoldRule(None, False, False), HoldRule(None, True, False)],
    "ny_opening_drive": [HoldRule(None, False, False), HoldRule(2.0, True, True)],
}


def share(values: list[bool]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def summarize(rows: list[TradeAnatomy]) -> dict[str, Any]:
    losers = [r for r in rows if r.net_usd <= 0]
    by_exit: dict[str, dict[str, float]] = {}
    for reason in ("stop", "target", "time_exit"):
        sub = [r for r in rows if r.exit_reason == reason]
        if sub:
            by_exit[reason] = {
                "trades": len(sub),
                "avg_gross_per_oz": round(
                    statistics.mean(r.gross_per_oz for r in sub), 3
                ),
                "avg_net_usd": round(statistics.mean(r.net_usd for r in sub), 2),
            }
    cost_per_oz = [
        (r.spread_usd + r.extra_spread_slippage_usd + r.commission_usd) / (100 * r.lots)
        for r in rows
    ]
    return {
        "trades": len(rows),
        "gross_usd": round(sum(r.gross_usd for r in rows), 2),
        "spread_usd": round(sum(r.spread_usd for r in rows), 2),
        "extra_spread_slippage_usd": round(
            sum(r.extra_spread_slippage_usd for r in rows), 2
        ),
        "commission_usd": round(sum(r.commission_usd for r in rows), 2),
        "net_usd": round(sum(r.net_usd for r in rows), 2),
        "gross_win_rate": share([r.gross_usd > 0 for r in rows]),
        "net_win_rate": share([r.net_usd > 0 for r in rows]),
        "avg_gross_per_oz": round(statistics.mean(r.gross_per_oz for r in rows), 3),
        "avg_cost_per_oz": round(statistics.mean(cost_per_oz), 3),
        "avg_risk_per_oz": round(statistics.mean(r.risk_per_oz for r in rows), 3),
        "avg_mfe_r": round(statistics.mean(r.mfe_r for r in rows), 3),
        "avg_mae_r": round(statistics.mean(r.mae_r for r in rows), 3),
        "reached_0_5r": share([r.mfe_r >= 0.5 for r in rows]),
        "reached_1r": share([r.mfe_r >= 1.0 for r in rows]),
        "reached_2r": share([r.mfe_r >= 2.0 for r in rows]),
        "losers_that_were_up_1r": share([r.mfe_r >= 1.0 for r in losers]),
        "losers_never_up_0_25r": share([r.mfe_r < 0.25 for r in losers]),
        "avg_move_5m_per_oz": round(statistics.mean(r.move_5m_per_oz for r in rows), 3),
        "avg_move_15m_per_oz": round(
            statistics.mean(r.move_15m_per_oz for r in rows), 3
        ),
        "pct_up_after_5m": share([r.move_5m_per_oz > 0 for r in rows]),
        "pct_up_after_15m": share([r.move_15m_per_oz > 0 for r in rows]),
        "by_exit": by_exit,
    }


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    sizing = Sizing()
    bars = load_bars(BARS_DIR, 201401, 202412)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {}
    for plan in PLANS:
        days = [
            d for d in extract_session_days(bars, plan)[0] if d.day.year in DEV_YEARS
        ]
        for rule in SELECTED[plan.name]:
            rows = []
            for d in days:
                t = simulate_session(d, rule, costs, sizing)
                if t is not None:
                    a = explain(d, t, costs)
                    rows.append(a)
            key = f"{plan.name}__{rule.name.replace('/', '_')}"
            path = LOG_DIR / f"{key}.csv"
            with path.open("w", newline="") as fh:
                w = csv.DictWriter(
                    fh, fieldnames=[f.name for f in fields(TradeAnatomy)]
                )
                w.writeheader()
                w.writerows(asdict(r) for r in rows)
            report[key] = {
                "plan": plan.name,
                "rule": rule.name,
                "csv": str(path),
            } | summarize(rows)
            print(key, report[key]["net_usd"], flush=True)
    OUT.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(report))


def render_md(rep: dict[str, Any]) -> str:
    keys = list(rep)
    head = (
        "| | "
        + " | ".join(f"{rep[k]['plan']}<br>{rep[k]['rule']}" for k in keys)
        + " |"
    )
    sep = "| --- |" + " ---: |" * len(keys)

    def line(label: str, fmt: str, field: str) -> str:
        return (
            f"| {label} | " + " | ".join(fmt.format(rep[k][field]) for k in keys) + " |"
        )

    L = [
        "# XAUUSD trade anatomy: where do the losses come from? (2014-2024)",
        "",
        "Every trade of four step-2b rules, split into the price move before costs "
        "and each cost. MFE/MAE = furthest the mid price went in our favour / "
        "against us between entry and exit; R = distance from entry to the stop. "
        "Full per-trade logs (entry/exit time, prices, costs) are in "
        "`docs/trade-logs/*.csv`.",
        "",
        "## Money: before and after costs ($3,000 account, $30 risk per trade)",
        "",
        head,
        sep,
        line("Trades", "{:,}", "trades"),
        line("Gross result before costs $", "{:,.0f}", "gross_usd"),
        line("Recorded spread $", "{:,.0f}", "spread_usd"),
        line("Extra spread + slippage $", "{:,.0f}", "extra_spread_slippage_usd"),
        line("Commission $", "{:,.0f}", "commission_usd"),
        line("Net result $", "{:,.0f}", "net_usd"),
        line("Win rate before costs", "{:.0%}", "gross_win_rate"),
        line("Win rate after costs", "{:.0%}", "net_win_rate"),
        line("Avg gross move per trade $/oz", "{:+.2f}", "avg_gross_per_oz"),
        line("Avg total cost per trade $/oz", "{:.2f}", "avg_cost_per_oz"),
        line("Avg risk (entry to stop) $/oz", "{:.2f}", "avg_risk_per_oz"),
        "",
        "## Entry quality: did price go our way after we got in?",
        "",
        head,
        sep,
        line("Avg mid move 5 min after entry $/oz", "{:+.2f}", "avg_move_5m_per_oz"),
        line("Trades in profit after 5 min", "{:.0%}", "pct_up_after_5m"),
        line("Avg mid move 15 min after entry $/oz", "{:+.2f}", "avg_move_15m_per_oz"),
        line("Trades in profit after 15 min", "{:.0%}", "pct_up_after_15m"),
        line(
            "Losers never more than 0.25R in profit", "{:.0%}", "losers_never_up_0_25r"
        ),
        "",
        "## Exit quality: did we give profits back?",
        "",
        head,
        sep,
        line("Avg best point reached (MFE) R", "{:.2f}", "avg_mfe_r"),
        line("Avg worst point reached (MAE) R", "{:.2f}", "avg_mae_r"),
        line("Trades that reached +0.5R", "{:.0%}", "reached_0_5r"),
        line("Trades that reached +1R", "{:.0%}", "reached_1r"),
        line("Trades that reached +2R", "{:.0%}", "reached_2r"),
        line("Losers that had been +1R in profit", "{:.0%}", "losers_that_were_up_1r"),
        "",
        "## By exit type (avg gross move $/oz, avg net $)",
        "",
        "| Rule | Exit | Trades | Avg gross $/oz | Avg net $ |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for k in keys:
        for reason, v in rep[k]["by_exit"].items():
            L.append(
                f"| {rep[k]['plan']} {rep[k]['rule']} | {reason} | {v['trades']} | "
                f"{v['avg_gross_per_oz']:+.2f} | {v['avg_net_usd']:+.2f} |"
            )
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
