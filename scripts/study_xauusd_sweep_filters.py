"""Does an intraday trend filter or a moving stop fix the YouTube sweep strategy?

Four versions, fixed before running, all with the video's 2R target and stop on
15-minute candle close:

1. as before (the video's rules);
2. + trend filter: sell only if the confirmation candle closes below the 20-hour
   moving average of hourly closes, buy only if above;
3. + moving stop: once 1R in profit, a touch stop trails 1R behind the best price
   (so the trade can no longer turn into a loss);
4. both.

Development 2014-2024 with expensive and doubled costs plus the edge before any
costs; versions profitable at 2x are shown once on 2025. 2026 is never loaded.

Writes docs/xauusd-sweep-filters.{json,md}.
Usage: PYTHONPATH=src .venv/bin/python scripts/study_xauusd_sweep_filters.py
"""

import json
import statistics
from pathlib import Path
from typing import Any

import numpy as np

from trading_bot.backtesting.session_hold import HoldTrade, mid_only
from trading_bot.backtesting.session_window import (
    Array,
    CostModel,
    Sizing,
    load_bars,
    summarize,
)
from trading_bot.backtesting.sweep_strategy import SweepRule, build_days, run_sweep
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-sweep-filters")
DEV = range(2014, 2025)
CHECK = range(2025, 2026)
ZERO = CostModel(0.0, 0.0, 0.0)
VERSIONS = [
    ("1. As in the video", SweepRule(2.0, "close")),
    ("2. + trend filter", SweepRule(2.0, "close", trend_filter=True)),
    ("3. + moving stop", SweepRule(2.0, "close", trail=True)),
    ("4. Both", SweepRule(2.0, "close", trend_filter=True, trail=True)),
]
REASONS = ("stop", "trail", "target", "time_exit")


def stats(trades: list[HoldTrade], days: int, bars: dict[str, Array]) -> dict[str, Any]:
    s = summarize(trades, days)
    daily: dict[str, float] = {}
    for t in trades:
        daily[t.day.isoformat()] = daily.get(t.day.isoformat(), 0.0) + t.pnl_usd
    mid_h = (bars["bid_high"] + bars["ask_high"]) / 2
    mid_l = (bars["bid_low"] + bars["ask_low"]) / 2
    mid_o = (bars["bid_open"] + bars["ask_open"]) / 2
    mfe_r = []
    for t in trades:
        e = float(mid_o[t.entry_minute])
        risk = abs(e - t.stop) or 1e-9
        hi = float(mid_h[t.entry_minute : t.exit_bar + 1].max())
        lo = float(mid_l[t.entry_minute : t.exit_bar + 1].min())
        mfe_r.append(((hi - e) if t.direction == 1 else (e - lo)) / risk)
    return {
        "trades": s.trades,
        "trades_per_day": round(s.trades / days, 2) if days else 0,
        "win_rate": round(s.win_rate, 4),
        "net_usd": round(s.net_usd, 2),
        "avg_per_trade": round(s.avg_per_trade, 2),
        "avg_win": (
            round(statistics.mean(t.pnl_usd for t in trades if t.pnl_usd > 0), 2)
            if any(t.pnl_usd > 0 for t in trades)
            else 0.0
        ),
        "avg_loss": (
            round(statistics.mean(t.pnl_usd for t in trades if t.pnl_usd <= 0), 2)
            if any(t.pnl_usd <= 0 for t in trades)
            else 0.0
        ),
        "worst_day": round(min(daily.values()), 2) if daily else 0.0,
        "max_drawdown_usd": round(s.max_drawdown_usd, 2),
        "profit_factor": None if s.profit_factor is None else round(s.profit_factor, 3),
        "green_days": (
            round(float(np.mean([v > 0 for v in daily.values()])), 3) if daily else 0.0
        ),
        "by_year": s.by_year,
        "exit_mix": {r: sum(t.exit_reason == r for t in trades) for r in REASONS},
        "reached_1r": (
            round(float(np.mean([x >= 1 for x in mfe_r])), 3) if mfe_r else 0.0
        ),
    }


def raw_edge(trades: list[HoldTrade]) -> dict[str, float]:
    moves = [(t.exit - t.entry) * t.direction for t in trades]
    mean, sd = statistics.mean(moves), statistics.stdev(moves)
    return {
        "trades": len(moves),
        "usd_per_oz": round(mean, 3),
        "t_stat": round(mean / sd * len(moves) ** 0.5, 2),
    }


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    sizing = Sizing()
    bars = load_bars(BARS_DIR, 201401, 202512)
    mids = mid_only(bars)
    days = build_days(bars)

    dev: list[dict[str, Any]] = []
    for label, rule in VERSIONS:
        base, n = run_sweep(bars, days, rule, costs, sizing, DEV)
        dbl, _ = run_sweep(bars, days, rule, stress, sizing, DEV)
        raw, _ = run_sweep(mids, days, rule, ZERO, sizing, DEV)
        dev.append(
            {
                "label": label,
                "rule": rule.name,
                "base": stats(base, n, bars),
                "double": stats(dbl, n, bars),
                "raw_edge": raw_edge(raw),
            }
        )
        print(label, dev[-1]["base"]["net_usd"], dev[-1]["raw_edge"], flush=True)

    check = []
    for (label, rule), r in zip(VERSIONS, dev, strict=True):
        if r["double"]["net_usd"] > 0:
            base, n = run_sweep(bars, days, rule, costs, sizing, CHECK)
            dbl, _ = run_sweep(bars, days, rule, stress, sizing, CHECK)
            check.append(
                {
                    "label": label,
                    "base": stats(base, n, bars),
                    "double": stats(dbl, n, bars),
                }
            )

    payload = {
        "question": "Does an intraday trend filter or a moving stop fix the "
        "sweep strategy?",
        "dev_years": [DEV.start, DEV.stop - 1],
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
        "# Sweep strategy: intraday trend filter and moving stop",
        "",
        "All versions use the video's rules with a 2R target and the stop counted on "
        "15-minute candle close. Trend filter: sell only below the 20-hour moving "
        "average of hourly closes, buy only above. Moving stop: once 1R in profit, a "
        "normal (touch) stop trails 1R behind the best price. $3,000 account, $30 "
        "risk per trade, expensive costs; 2x doubles them. Rules fixed before "
        "running. Development 2014-2024; 2025 only for versions profitable at 2x; "
        "2026 not loaded.",
        "",
        "## 2014-2024",
        "",
        "| Version | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ "
        "| PF | Net $ at 2x | Edge before costs $/oz | t | Green days |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
        "| ---: |",
    ]
    for r in dev:
        b, d, e = r["base"], r["double"], r["raw_edge"]
        pf = f"{b['profit_factor']:.2f}" if b["profit_factor"] else "-"
        L.append(
            f"| {r['label']} | {b['trades']:,} | {b['win_rate']:.0%} | "
            f"{b['avg_win']:.2f} | {b['avg_loss']:.2f} | {b['avg_per_trade']:.2f} | "
            f"{fmt(b['net_usd'])} | {pf} | {fmt(d['net_usd'])} | "
            f"{e['usd_per_oz']:+.3f} | {e['t_stat']:+.1f} | {b['green_days']:.0%} |"
        )
    L += ["", "Exits (stop / moving stop / target / end of day):", ""]
    for r in dev:
        x = r["base"]["exit_mix"]
        L.append(
            f"- {r['label']}: {x['stop']:,} / {x['trail']:,} / {x['target']:,} / "
            f"{x['time_exit']:,}; {r['base']['reached_1r']:.0%} of trades were "
            "1R in profit at some point"
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
            f"| {r['label']} | "
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
            f"| {c['label']} | {c['base']['trades']:,} | "
            f"{c['base']['win_rate']:.0%} | {fmt(c['base']['net_usd'])} | "
            f"{fmt(c['double']['net_usd'])} |"
        )
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
