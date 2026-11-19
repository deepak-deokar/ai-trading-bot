"""Step 2b: same-day XAUUSD range breakouts held for hours (never overnight).

Two pre-declared plans (Asian range broken at the London open; New York opening
drive) x 3 exits (time exit, 2R, 3R) x 4 filter sets (none, 20-day trend,
quiet/wild condition check, both) = 24 rules. Development 2014-2024 with expensive
and doubled costs on a $3,000 account risking 1% per trade; rules positive at 2x
are shown once on 2025. 2026 is never loaded.

Writes docs/xauusd-session-hold.{json,md}.
Usage: PYTHONPATH=src .venv/bin/python scripts/study_xauusd_session_hold.py
"""

import json
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Any

from trading_bot.backtesting.session_hold import (
    PLANS,
    HoldRule,
    HoldTrade,
    SessionDay,
    extract_session_days,
    mid_only,
    run_hold_rule,
)
from trading_bot.backtesting.session_window import (
    CostModel,
    Sizing,
    Summary,
    load_bars,
    summarize,
)
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-session-hold")
DEV_YEARS = range(2014, 2025)
CHECK_YEAR = 2025
TOP_N = 5
ZERO = CostModel(0.0, 0.0, 0.0)

RULES = [
    HoldRule(target, trend, cond)
    for target in (None, 2.0, 3.0)
    for trend in (False, True)
    for cond in (False, True)
]


def fmt(x: float) -> str:
    return f"{x:,.0f}"


def raw_edge(trades: list[HoldTrade]) -> dict[str, float]:
    moves = [(t.exit - t.entry) * t.direction for t in trades]
    if len(moves) < 2:
        return {"trades": len(moves), "usd_per_oz": 0.0, "t_stat": 0.0}
    mean, sd = statistics.mean(moves), statistics.stdev(moves)
    return {
        "trades": len(moves),
        "usd_per_oz": round(mean, 3),
        "t_stat": round(mean / sd * len(moves) ** 0.5, 2),
    }


def row(s: Summary) -> dict[str, Any]:
    d = asdict(s)
    for k, v in d.items():
        if isinstance(v, float):
            d[k] = round(v, 4 if k == "win_rate" else 2)
    return d


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    sizing = Sizing()
    bars = load_bars(BARS_DIR, 201401, 202512)
    mids = mid_only(bars)

    results: list[dict[str, Any]] = []
    plan_info: dict[str, dict[str, Any]] = {}
    check_days: dict[str, list[SessionDay]] = {}
    for plan in PLANS:
        days, skipped = extract_session_days(bars, plan)
        mid_days = extract_session_days(mids, plan)[0]
        dev = [d for d in days if d.day.year in DEV_YEARS]
        mid_dev = [d for d in mid_days if d.day.year in DEV_YEARS]
        check_days[plan.name] = [d for d in days if d.day.year == CHECK_YEAR]
        cost_rt = statistics.median(
            costs.round_trip_per_oz(d.entry_spread) for d in dev
        )
        plan_info[plan.name] = {
            "label": plan.label,
            "dev_days": len(dev),
            "skipped_incomplete": skipped,
            "median_range": round(statistics.median(d.range_size for d in dev), 2),
            "median_round_trip_cost": round(cost_rt, 2),
        }
        for rule in RULES:
            base_trades = run_hold_rule(dev, rule, costs, sizing)
            results.append(
                {
                    "plan": plan.name,
                    "rule": rule,
                    "base": summarize(base_trades, len(dev)),
                    "double": summarize(
                        run_hold_rule(dev, rule, stress, sizing), len(dev)
                    ),
                    "raw_edge": raw_edge(run_hold_rule(mid_dev, rule, ZERO, sizing)),
                    "median_hold_min": (
                        statistics.median(t.hold_minutes for t in base_trades)
                        if base_trades
                        else 0
                    ),
                    "exit_mix": {
                        r: sum(t.exit_reason == r for t in base_trades)
                        for r in ("stop", "target", "time_exit")
                    },
                }
            )
        print(plan.name, plan_info[plan.name], flush=True)

    results.sort(key=lambda r: -r["base"].net_usd)
    picks = [r for r in results if r["double"].net_usd > 0][:TOP_N]
    check = []
    for r in picks:
        days = check_days[r["plan"]]
        check.append(
            {
                "plan": r["plan"],
                "rule": r["rule"].name,
                "base": summarize(
                    run_hold_rule(days, r["rule"], costs, sizing), len(days)
                ),
                "double": summarize(
                    run_hold_rule(days, r["rule"], stress, sizing), len(days)
                ),
            }
        )
    profitable = sum(r["base"].net_usd > 0 for r in results)
    payload = {
        "account_usd": sizing.account_usd,
        "risk_per_trade_usd": sizing.risk_usd,
        "cost_profile": str(COSTS_YAML),
        "dev_years": [DEV_YEARS.start, DEV_YEARS.stop - 1],
        "check_year": CHECK_YEAR,
        "holdout": "2026 not loaded",
        "plans": plan_info,
        "rules_tested": len(results),
        "rules_profitable_dev": profitable,
        "dev_results": [
            {
                "plan": r["plan"],
                "rule": r["rule"].name,
                "base": row(r["base"]),
                "double": row(r["double"]),
                "raw_edge": r["raw_edge"],
                "median_hold_min": r["median_hold_min"],
                "exit_mix": r["exit_mix"],
            }
            for r in results
        ],
        "check_2025": [
            {
                "plan": c["plan"],
                "rule": c["rule"],
                "base": row(c["base"]),
                "double": row(c["double"]),
            }
            for c in check
        ],
    }
    OUT.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n"
    )
    OUT.with_suffix(".md").write_text(render_md(payload, results, check))
    print(f"wrote {OUT}.json/.md; {profitable}/{len(results)} rules profitable")


def render_md(
    p: dict[str, Any], results: list[dict[str, Any]], check: list[dict[str, Any]]
) -> str:
    L = [
        "# XAUUSD same-day session breakouts held for hours (step 2b)",
        "",
        "$3,000 account, $30 risk (1%) per trade, at most one trade per plan per day, "
        "always closed the same day. Expensive costs: recorded bid/ask + $0.20 extra "
        "spread, $0.10 slippage per fill, $8/lot commission; '2x' doubles all three. "
        "Stop at the middle of the reference range. Development 2014-2024; 2025 shown "
        "only for rules positive at 2x on development; 2026 not loaded.",
        "",
        "## Plans",
        "",
        "| Plan | Rules | Days | Median range $ | Round-trip cost $/oz "
        "| Skipped days |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for name, i in p["plans"].items():
        L.append(
            f"| {name} | {i['label']} | {i['dev_days']} | {i['median_range']:.2f} | "
            f"{i['median_round_trip_cost']:.2f} | {i['skipped_incomplete']} |"
        )
    L += [
        "",
        f"## All {p['rules_tested']} rules on 2014-2024 "
        f"({p['rules_profitable_dev']} profitable after expensive costs)",
        "",
        "'Edge $/oz' is the average mid-price gain per trade with no spread and no "
        "costs (|t| above ~2 suggests a real effect).",
        "",
        "| Plan | Rule | Trades | Win % | Net $ | $/day | Worst day $ | Max DD $ | PF "
        "| Net $ at 2x | Edge $/oz | t | Hold min | Stop/target/time |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
        "| ---: | ---: | --- |",
    ]
    for r in results:
        b, d, e, x = r["base"], r["double"], r["raw_edge"], r["exit_mix"]
        pf = f"{b.profit_factor:.2f}" if b.profit_factor else "-"
        L.append(
            f"| {r['plan']} | {r['rule'].name} | {b.trades} | {b.win_rate:.0%} | "
            f"{fmt(b.net_usd)} | {b.avg_per_window_day:.2f} | {fmt(b.worst_day)} | "
            f"{fmt(b.max_drawdown_usd)} | {pf} | {fmt(d.net_usd)} | "
            f"{e['usd_per_oz']:+.2f} | {e['t_stat']:+.1f} | {r['median_hold_min']:.0f} "
            f"| {x['stop']}/{x['target']}/{x['time_exit']} |"
        )
    years = list(DEV_YEARS)
    L += [
        "",
        "Net $ per year for the top 5:",
        "",
        "| Plan / rule | " + " | ".join(str(y) for y in years) + " |",
        "| --- |" + " ---: |" * len(years),
    ]
    for r in results[:5]:
        cells = [fmt(r["base"].by_year.get(y, 0.0)) for y in years]
        L.append(f"| {r['plan']} {r['rule'].name} | " + " | ".join(cells) + " |")
    L += [
        "",
        "## First check on 2025 (rules picked on 2014-2024, positive at 2x)",
        "",
        "| Plan | Rule | Trades | Win % | Net $ | $/day | Worst day $ | Max DD $ | "
        "Net $ at 2x |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if not check:
        L.append(
            "| (none: no rule was profitable at 2x on 2014-2024) | | | | | | | | |"
        )
    for c in check:
        b, d = c["base"], c["double"]
        L.append(
            f"| {c['plan']} | {c['rule']} | {b.trades} | {b.win_rate:.0%} | "
            f"{fmt(b.net_usd)} | {b.avg_per_window_day:.2f} | {fmt(b.worst_day)} | "
            f"{fmt(b.max_drawdown_usd)} | {fmt(d.net_usd)} |"
        )
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
