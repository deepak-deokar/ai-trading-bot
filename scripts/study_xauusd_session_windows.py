"""Step 2: find the best XAUUSD 30-minute session window and simple rules for it.

1. Survey each candidate window: typical 30-minute move versus the cost of a trade.
2. Backtest a small, pre-declared rule grid (2 strategies x 3 exits x filter on/off)
   in every window on the development years 2014-2024, with the expensive cost
   profile and with doubled costs, on a $3,000 account risking 1% per trade.
3. Pick the top rules on development data only, then show them once on 2025.
   2026 is never loaded.

Writes docs/xauusd-session-windows.{json,md}.
Usage: PYTHONPATH=src .venv/bin/python scripts/study_xauusd_session_windows.py
"""

import json
import statistics
from dataclasses import asdict
from pathlib import Path

from trading_bot.backtesting.session_window import (
    WINDOWS,
    CostModel,
    Rule,
    Sizing,
    Summary,
    WindowDay,
    extract_window_days,
    load_bars,
    run_rule,
    summarize,
    survey,
)
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-session-windows")
DEV_YEARS = range(2014, 2025)
CHECK_YEAR = 2025
TOP_N = 5
ZERO_COSTS = CostModel(0.0, 0.0, 0.0)


def mid_only(bars: dict[str, object]) -> dict[str, object]:
    """Bars with bid = ask = mid, to measure a rule's edge before any costs."""
    out = dict(bars)
    for part in ("open", "high", "low", "close"):
        mid = (bars[f"bid_{part}"] + bars[f"ask_{part}"]) / 2  # type: ignore[operator]
        out[f"bid_{part}"], out[f"ask_{part}"] = mid, mid
    return out


def raw_edge(days: list[WindowDay], rule: Rule) -> dict[str, float]:
    """Average mid-price gain per ounce per trade (no spread, no costs) and t-stat."""
    moves = [
        (t.exit - t.entry) * t.direction
        for t in run_rule(days, rule, ZERO_COSTS, Sizing())
    ]
    mean, sd = statistics.mean(moves), statistics.stdev(moves)
    return {
        "trades": len(moves),
        "usd_per_oz": round(mean, 3),
        "t_stat": round(mean / sd * len(moves) ** 0.5, 2),
    }


RULES = [
    Rule(strategy, target, flt)  # type: ignore[arg-type]
    for strategy in ("orb", "momentum")
    for target in (1.0, 2.0, None)
    for flt in (False, True)
]


def fmt(x: float) -> str:
    return f"{x:,.0f}"


def summary_row(s: Summary) -> dict[str, object]:
    d = asdict(s)
    for k in (
        "win_rate",
        "net_usd",
        "avg_per_trade",
        "avg_per_window_day",
        "worst_day",
        "best_day",
        "max_drawdown_usd",
    ):
        d[k] = round(d[k], 4 if k == "win_rate" else 2)
    if d["profit_factor"] is not None:
        d["profit_factor"] = round(d["profit_factor"], 3)
    return d


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    sizing = Sizing()
    bars = load_bars(BARS_DIR, 201401, 202512)
    mid_bars = mid_only(bars)  # type: ignore[arg-type]

    surveys: dict[str, dict[str, object]] = {}
    dev_days: dict[str, list[WindowDay]] = {}
    check_days: dict[str, list[WindowDay]] = {}
    skipped: dict[str, int] = {}
    for w in WINDOWS:
        days, skipped[w.name] = extract_window_days(bars, w)
        dev_days[w.name] = [d for d in days if d.day.year in DEV_YEARS]
        check_days[w.name] = [d for d in days if d.day.year == CHECK_YEAR]
        per_year = {
            y: survey([d for d in days if d.day.year == y], costs)
            for y in range(2014, CHECK_YEAR + 1)
        }
        surveys[w.name] = {
            "label": w.label,
            "dev": survey(dev_days[w.name], costs),
            "by_year": per_year,
        }
        mid_days = [
            d
            for d in extract_window_days(mid_bars, w)[0]  # type: ignore[arg-type]
            if d.day.year in DEV_YEARS
        ]
        surveys[w.name]["raw_edge"] = {
            s: raw_edge(mid_days, Rule(s, None, False))  # type: ignore[arg-type]
            for s in ("orb", "momentum")
        }
        print(w.name, surveys[w.name]["dev"], surveys[w.name]["raw_edge"], flush=True)

    dev_results = []
    for w in WINDOWS:
        n = len(dev_days[w.name])
        for rule in RULES:
            base = summarize(run_rule(dev_days[w.name], rule, costs, sizing), n)
            dbl = summarize(run_rule(dev_days[w.name], rule, stress, sizing), n)
            dev_results.append(
                {"window": w.name, "rule": rule, "base": base, "double": dbl}
            )
    dev_results.sort(key=lambda r: -r["base"].net_usd)  # type: ignore[union-attr]
    picks = [r for r in dev_results if r["double"].net_usd > 0][:TOP_N]  # type: ignore[union-attr]

    check = []
    for r in picks:
        rule, w = r["rule"], r["window"]
        n = len(check_days[w])  # type: ignore[index]
        check.append(
            {
                "window": w,
                "rule": rule.name,  # type: ignore[union-attr]
                "base": summarize(run_rule(check_days[w], rule, costs, sizing), n),  # type: ignore[arg-type,index]
                "double": summarize(run_rule(check_days[w], rule, stress, sizing), n),  # type: ignore[arg-type,index]
            }
        )

    profitable = sum(1 for r in dev_results if r["base"].net_usd > 0)  # type: ignore[union-attr]
    payload = {
        "account_usd": sizing.account_usd,
        "risk_per_trade_usd": sizing.risk_usd,
        "cost_profile": str(COSTS_YAML),
        "dev_years": [DEV_YEARS.start, DEV_YEARS.stop - 1],
        "check_year": CHECK_YEAR,
        "holdout": "2026 not loaded",
        "skipped_incomplete_windows": skipped,
        "survey": surveys,
        "rules_tested": len(dev_results),
        "rules_profitable_dev": profitable,
        "dev_results": [
            {
                "window": r["window"],
                "rule": r["rule"].name,  # type: ignore[union-attr]
                "base": summary_row(r["base"]),
                "double": summary_row(r["double"]),
            }  # type: ignore[arg-type]
            for r in dev_results
        ],
        "check_2025": [
            {
                "window": c["window"],
                "rule": c["rule"],
                "base": summary_row(c["base"]),
                "double": summary_row(c["double"]),
            }  # type: ignore[arg-type]
            for c in check
        ],
    }
    OUT.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n"
    )
    OUT.with_suffix(".md").write_text(render_md(payload, dev_results, check))
    print(f"wrote {OUT}.json/.md; {profitable}/{len(dev_results)} rules profitable")


def render_md(
    p: dict[str, object], dev: list[dict[str, object]], check: list[dict[str, object]]
) -> str:
    L = ["# XAUUSD 30-minute session windows (step 2)", ""]
    L += [
        "$3,000 account, $30 risk (1%) per trade, at most one trade per window per "
        "day, everything closed by the window's end. Expensive costs: recorded "
        "bid/ask + $0.20 extra spread, $0.10 slippage per fill, $8/lot commission; "
        "'2x' doubles all three. Development 2014-2024; 2025 shown only for rules "
        "picked on development data; 2026 not loaded.",
        "",
        "## 1. How much gold moves in each window (2014-2024 medians)",
        "",
        "| Window | Days | 30-min range $ | Open→close move $ | Entry spread $ | "
        "Round-trip cost $/oz | Range ÷ cost |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    survey_all = p["survey"]
    assert isinstance(survey_all, dict)
    for s in survey_all.values():
        d = s["dev"]
        L.append(
            f"| {s['label']} | {d['days']} | {d['median_range']:.2f} | "
            f"{d['median_abs_move']:.2f} | {d['median_entry_spread']:.2f} | "
            f"{d['median_round_trip_cost']:.2f} | {d['range_to_cost']:.1f} |"
        )
    L += [
        "",
        "Range ÷ cost by year:",
        "",
        "| Window | " + " | ".join(str(y) for y in range(2014, 2026)) + " |",
        "| --- |" + " ---: |" * 12,
    ]
    for s in survey_all.values():
        cells = [
            f"{s['by_year'][y].get('range_to_cost', 0):.1f}" for y in range(2014, 2026)
        ]
        L.append(f"| {s['label']} | " + " | ".join(cells) + " |")

    L += [
        "",
        "## 2. Edge before any costs (mid price, time exit, all days, " "2014-2024)",
        "",
        "Average gain per ounce per trade if there were no spread and no costs. "
        "|t| above ~2 suggests a real but small effect.",
        "",
        "| Window | Breakout $/oz | t | Momentum $/oz | t | Round-trip cost $/oz |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in survey_all.values():
        e = s["raw_edge"]
        L.append(
            f"| {s['label']} | {e['orb']['usd_per_oz']:+.2f} | "
            f"{e['orb']['t_stat']:+.1f} | {e['momentum']['usd_per_oz']:+.2f} | "
            f"{e['momentum']['t_stat']:+.1f} | "
            f"{s['dev']['median_round_trip_cost']:.2f} |"
        )
    L += [
        "",
        f"## 3. Rule grid on 2014-2024 ({p['rules_profitable_dev']} of "
        f"{p['rules_tested']} rules profitable after expensive costs)",
        "",
        "Top 15 by net profit:",
        "",
        "| Window | Rule | Trades | Win % | Net $ | $/window-day | Worst day $ | "
        "Max DD $ | PF | Net $ at 2x |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in dev[:15]:
        b, d = r["base"], r["double"]
        assert isinstance(b, Summary) and isinstance(d, Summary)
        pf = f"{b.profit_factor:.2f}" if b.profit_factor else "-"
        L.append(
            f"| {r['window']} | {r['rule'].name} | {b.trades} | "  # type: ignore[attr-defined]
            f"{b.win_rate:.0%} | {fmt(b.net_usd)} | {b.avg_per_window_day:.2f} | "
            f"{fmt(b.worst_day)} | {fmt(b.max_drawdown_usd)} | {pf} | "
            f"{fmt(d.net_usd)} |"
        )
    L += [
        "",
        "Net $ per year for the top 5:",
        "",
        "| Window / rule | " + " | ".join(str(y) for y in DEV_YEARS) + " |",
        "| --- |" + " ---: |" * len(DEV_YEARS),
    ]
    for r in dev[:5]:
        b = r["base"]
        assert isinstance(b, Summary)
        cells = [fmt(b.by_year.get(y, 0.0)) for y in DEV_YEARS]
        L.append(f"| {r['window']} {r['rule'].name} | " + " | ".join(cells) + " |")  # type: ignore[attr-defined]

    L += [
        "",
        "## 4. First check on 2025 (rules picked on 2014-2024, positive at 2x)",
        "",
        "| Window | Rule | Trades | Win % | Net $ | $/window-day | Worst day $ | "
        "Max DD $ | Net $ at 2x |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if not check:
        L.append(
            "| (none: no rule was profitable at 2x on 2014-2024) " "| | | | | | | | |"
        )
    for c in check:
        b, d = c["base"], c["double"]
        assert isinstance(b, Summary) and isinstance(d, Summary)
        L.append(
            f"| {c['window']} | {c['rule']} | {b.trades} | {b.win_rate:.0%} | "
            f"{fmt(b.net_usd)} | {b.avg_per_window_day:.2f} | {fmt(b.worst_day)} | "
            f"{fmt(b.max_drawdown_usd)} | {fmt(d.net_usd)} |"
        )
    L += [
        "",
        "Incomplete windows skipped (feed holes, holidays): "
        + ", ".join(f"{k} {v}" for k, v in p["skipped_incomplete_windows"].items())  # type: ignore[attr-defined]
        + ".",
        "",
    ]
    return "\n".join(L)


if __name__ == "__main__":
    main()
