"""Trade gold only on big US news days, at most once a day.

Rules: trading_bot.backtesting.news_day (fixed before running). Four versions:
momentum or fade x exit only at the time limit or at a 2R target. Each is also
broken down by event (jobs report, inflation, Fed) and compared with a control:
the same rule at 08:30 on ordinary days.

Pass criteria, also fixed before running: profitable on 2014-2024 at doubled
costs, profitable in at least 7 of the 11 years at normal expensive costs, and an
edge before costs with t >= 2. Versions profitable at 2x are shown once on 2025.
2026 is never loaded.

Writes docs/xauusd-news-days.{json,md}.
Usage: PYTHONPATH=src .venv/bin/python scripts/study_xauusd_news_days.py
"""

import json
import statistics
from pathlib import Path
from typing import Any

import numpy as np

from trading_bot.backtesting.news_day import (
    NewsRule,
    control_days,
    load_events,
    run_news,
)
from trading_bot.backtesting.session_hold import HoldTrade, mid_only
from trading_bot.backtesting.session_window import (
    CostModel,
    Sizing,
    load_bars,
    summarize,
)
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-news-days")
DEV = range(2014, 2025)
CHECK = range(2025, 2026)
ZERO = CostModel(0.0, 0.0, 0.0)
RULES = [
    NewsRule("momentum", None),
    NewsRule("momentum", 2.0),
    NewsRule("fade", None),
    NewsRule("fade", 2.0),
]
KINDS = ("nfp", "cpi", "fomc")
KIND_LABEL = {"nfp": "Jobs report", "cpi": "Inflation (CPI)", "fomc": "Fed decision"}
MIN_GREEN_YEARS = 7


def edge(trades: list[HoldTrade]) -> dict[str, float]:
    moves = [(t.exit - t.entry) * t.direction for t in trades]
    if len(moves) < 3:
        return {"trades": len(moves), "usd_per_oz": 0.0, "t_stat": 0.0}
    mean, sd = statistics.mean(moves), statistics.stdev(moves)
    return {
        "trades": len(moves),
        "usd_per_oz": round(mean, 3),
        "t_stat": round(mean / sd * len(moves) ** 0.5, 2) if sd else 0.0,
    }


def stats(trades: list[HoldTrade], events: int) -> dict[str, Any]:
    s = summarize(trades, events)
    risk = [abs(t.entry - t.stop) for t in trades]
    return {
        "events_with_data": events,
        "trades": s.trades,
        "win_rate": round(s.win_rate, 4),
        "net_usd": round(s.net_usd, 2),
        "avg_per_trade": round(s.avg_per_trade, 2),
        "max_drawdown_usd": round(s.max_drawdown_usd, 2),
        "profit_factor": None if s.profit_factor is None else round(s.profit_factor, 3),
        "by_year": s.by_year,
        "green_years": sum(v > 0 for v in s.by_year.values()),
        "median_risk_per_oz": round(statistics.median(risk), 2) if risk else 0.0,
        "exit_mix": {
            r: sum(t.exit_reason == r for t in trades)
            for r in ("stop", "target", "time_exit")
        },
    }


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    sizing = Sizing()
    bars = load_bars(BARS_DIR, 201401, 202512)
    mids = mid_only(bars)
    events = load_events()
    controls = control_days(bars, events, DEV)
    kind_of = {e.day: e.kind for e in events}

    dev: list[dict[str, Any]] = []
    for rule in RULES:
        base, n = run_news(bars, events, rule, costs, sizing, DEV)
        dbl, _ = run_news(bars, events, rule, stress, sizing, DEV)
        raw, _ = run_news(mids, events, rule, ZERO, sizing, DEV)
        ctl_raw, n_ctl = run_news(mids, controls, rule, ZERO, sizing, DEV)
        by_kind = {}
        for k in KINDS:
            b = [t for t in base if kind_of[t.day] == k]
            r = [t for t in raw if kind_of[t.day] == k]
            by_kind[k] = {
                "trades": len(b),
                "net_usd": round(sum(t.pnl_usd for t in b), 2),
                "avg_per_trade": (
                    round(statistics.mean(t.pnl_usd for t in b), 2) if b else 0.0
                ),
                "raw_edge": edge(r),
            }
        e = edge(raw)
        s_base, s_dbl = stats(base, n), stats(dbl, n)
        passed = (
            s_dbl["net_usd"] > 0
            and s_base["green_years"] >= MIN_GREEN_YEARS
            and e["t_stat"] >= 2
        )
        dev.append(
            {
                "rule": rule.name,
                "base": s_base,
                "double": s_dbl,
                "raw_edge": e,
                "by_event": by_kind,
                "control_raw_edge": {**edge(ctl_raw), "days_with_data": n_ctl},
                "passed": passed,
            }
        )
        print(rule.name, s_base["net_usd"], e, "control", edge(ctl_raw), flush=True)

    check = []
    for rule, r in zip(RULES, dev, strict=True):
        if r["double"]["net_usd"] > 0:
            base, n = run_news(bars, events, rule, costs, sizing, CHECK)
            dbl, _ = run_news(bars, events, rule, stress, sizing, CHECK)
            check.append(
                {"rule": rule.name, "base": stats(base, n), "double": stats(dbl, n)}
            )

    payload = {
        "question": "Does trading only on big US news days, once a day, make money?",
        "events_file": "config/us_news_events.csv",
        "dev_years": [DEV.start, DEV.stop - 1],
        "pass_criteria": "net > 0 at 2x costs, >= 7 of 11 green years, edge t >= 2",
        "holdout": "2026 not loaded",
        "dev": dev,
        "check_2025": check,
    }
    OUT.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(dev, check))
    print("wrote", OUT)


def fmt(x: float) -> str:
    return f"{x:,.0f}"


def render_md(dev: list[dict[str, Any]], check: list[dict[str, Any]]) -> str:
    L = [
        "# Gold on big US news days only (one trade a day)",
        "",
        "Events: jobs report and CPI at 08:30 New York, scheduled Fed statements at "
        "14:00 (`config/us_news_events.csv`). The 15-minute release candle sets the "
        "direction; entry at the next candle's open. Momentum trades with it (stop "
        "past the candle's other end), fade trades against it (stop past the "
        "candle's extreme). Exit at 2R or at the time limit (12:00 for 08:30 "
        "events, 16:45 for the Fed). $3,000 account, $30 risk per trade, expensive "
        "costs; 2x doubles them. Rules and pass criteria fixed before running. "
        "Development 2014-2024; 2026 not loaded.",
        "",
        "Pass: profitable at 2x costs, profitable in at least 7 of 11 years, edge "
        "before costs with t >= 2.",
        "",
        "## 2014-2024",
        "",
        "| Version | Trades | Win % | Net $/trade | Net $ | PF | Net $ at 2x | "
        "Green years | Edge before costs $/oz | t | Median stop $/oz | "
        "Ordinary days at 08:30: edge $/oz (t) | Passed |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
        "| ---: | --- |",
    ]
    for r in dev:
        b, d, e, c = r["base"], r["double"], r["raw_edge"], r["control_raw_edge"]
        pf = f"{b['profit_factor']:.2f}" if b["profit_factor"] else "-"
        L.append(
            f"| {r['rule']} | {b['trades']:,} | {b['win_rate']:.0%} | "
            f"{b['avg_per_trade']:.2f} | {fmt(b['net_usd'])} | {pf} | "
            f"{fmt(d['net_usd'])} | {b['green_years']}/11 | {e['usd_per_oz']:+.3f} | "
            f"{e['t_stat']:+.1f} | {b['median_risk_per_oz']:.2f} | "
            f"{c['usd_per_oz']:+.3f} ({c['t_stat']:+.1f}) | "
            f"{'yes' if r['passed'] else 'no'} |"
        )
    L += [
        "",
        "## By event (normal expensive costs)",
        "",
        "| Version | Event | Trades | Net $ | Net $/trade | Edge before costs $/oz "
        "| t |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in dev:
        for k in KINDS:
            x = r["by_event"][k]
            L.append(
                f"| {r['rule']} | {KIND_LABEL[k]} | {x['trades']} | "
                f"{fmt(x['net_usd'])} | {x['avg_per_trade']:.2f} | "
                f"{x['raw_edge']['usd_per_oz']:+.3f} | {x['raw_edge']['t_stat']:+.1f} |"
            )
    years = list(DEV)
    L += [
        "",
        "Net $ per year:",
        "",
        "| Version | " + " | ".join(str(y) for y in years) + " |",
        "| --- |" + " ---: |" * len(years),
    ]
    for r in dev:
        by = r["base"]["by_year"]
        L.append(
            f"| {r['rule']} | "
            + " | ".join(fmt(by.get(y, by.get(str(y), 0.0))) for y in years)
            + " |"
        )
    L += [
        "",
        "## 2025 check (versions profitable at 2x on 2014-2024)",
        "",
        "| Version | Trades | Win % | Net $ | Net $ at 2x |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    if not check:
        L.append("| (none: no version was profitable at 2x on 2014-2024) | | | | |")
    for c in check:
        L.append(
            f"| {c['rule']} | {c['base']['trades']} | {c['base']['win_rate']:.0%} | "
            f"{fmt(c['base']['net_usd'])} | {fmt(c['double']['net_usd'])} |"
        )
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
