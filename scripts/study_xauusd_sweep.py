"""Backtest the YouTube 'daily zone + liquidity sweep' gold strategy.

Video: "Gold Trading Strategy That Every Trader Should Know!" (The Trading School,
youtube.com/watch?v=ctLHzjrH3Rk). Rules and assumptions: see
trading_bot.backtesting.sweep_strategy. Variants: target 2R / 3R x stop on candle
close (as in the video) / stop on touch. Development 2014-2024 with expensive and
doubled costs on a $3,000 account risking 1% per trade; variants positive at 2x
are shown once on 2025. 2026 is never loaded.

Writes docs/xauusd-sweep-strategy.{json,md} and docs/trade-logs/sweep__*.csv.
Usage: PYTHONPATH=src .venv/bin/python scripts/study_xauusd_sweep.py
"""

import csv
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
OUT = Path("docs/xauusd-sweep-strategy")
LOG_DIR = Path("docs/trade-logs")
DEV = range(2014, 2025)
CHECK = range(2025, 2026)
RULES = [SweepRule(t, s) for t in (2.0, 3.0) for s in ("close", "touch")]  # type: ignore[arg-type]
ZERO = CostModel(0.0, 0.0, 0.0)


def fmt(x: float) -> str:
    return f"{x:,.0f}"


def stats(trades: list[HoldTrade], days: int, bars: dict[str, Array]) -> dict[str, Any]:
    s = summarize(trades, days)
    daily: dict[str, float] = {}
    for t in trades:
        daily[t.day.isoformat()] = daily.get(t.day.isoformat(), 0.0) + t.pnl_usd
    mid_o = (bars["bid_open"] + bars["ask_open"]) / 2
    mid_c = (bars["bid_close"] + bars["ask_close"]) / 2

    def after(t: HoldTrade, n: int) -> float:
        return float(
            (mid_c[t.entry_minute + n - 1] - mid_o[t.entry_minute]) * t.direction
        )

    return {
        "trading_days": days,
        "trades": s.trades,
        "trades_per_day": round(s.trades / days, 2) if days else 0,
        "win_rate": round(s.win_rate, 4),
        "net_usd": round(s.net_usd, 2),
        "avg_per_trade": round(s.avg_per_trade, 2),
        "avg_per_day": round(s.avg_per_window_day, 2),
        "worst_day": round(min(daily.values()), 2) if daily else 0.0,
        "worst_trade": round(s.worst_day, 2),
        "best_day": round(max(daily.values()), 2) if daily else 0.0,
        "max_drawdown_usd": round(s.max_drawdown_usd, 2),
        "profit_factor": None if s.profit_factor is None else round(s.profit_factor, 3),
        "by_year": s.by_year,
        "exit_mix": {
            r: sum(t.exit_reason == r for t in trades)
            for r in ("stop", "target", "time_exit")
        },
        "losses_beyond_1_5r": sum(t.pnl_usd < -45 for t in trades),
        "median_hold_min": (
            statistics.median(t.hold_minutes for t in trades) if trades else 0
        ),
        "pct_in_profit_after_15m": (
            round(float(np.mean([after(t, 15) > 0 for t in trades])), 3)
            if trades
            else 0.0
        ),
        "avg_move_15m_per_oz": (
            round(float(np.mean([after(t, 15) for t in trades])), 3) if trades else 0.0
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


def write_log(path: Path, trades: list[HoldTrade], bars: dict[str, Array]) -> None:
    mid_o = (bars["bid_open"] + bars["ask_open"]) / 2
    m = bars["minute_utc"]
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "day",
                "direction",
                "entry_time_utc",
                "exit_time_utc",
                "exit_reason",
                "lots",
                "entry_mid",
                "entry_fill",
                "stop",
                "target",
                "exit_fill",
                "fill_move_per_oz",
                "net_usd",
                "hold_minutes",
            ]
        )
        for t in trades:
            entry_mid = float(mid_o[t.entry_minute])
            w.writerow(
                [
                    t.day,
                    "BUY" if t.direction == 1 else "SELL",
                    np.datetime64(int(m[t.entry_minute]), "s"),
                    np.datetime64(int(m[t.exit_bar]), "s"),
                    t.exit_reason,
                    t.lots,
                    round(entry_mid, 3),
                    round(t.entry, 3),
                    round(t.stop, 3),
                    round(t.target or 0.0, 3),
                    round(t.exit, 3),
                    round((t.exit - t.entry) * t.direction, 3),
                    round(t.pnl_usd, 2),
                    t.hold_minutes,
                ]
            )


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    sizing = Sizing()
    bars = load_bars(BARS_DIR, 201401, 202512)
    mids = mid_only(bars)
    days = build_days(bars)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    dev: list[dict[str, Any]] = []
    for rule in RULES:
        base, n = run_sweep(bars, days, rule, costs, sizing, DEV)
        dbl, _ = run_sweep(bars, days, rule, stress, sizing, DEV)
        raw, _ = run_sweep(mids, days, rule, ZERO, sizing, DEV)
        write_log(LOG_DIR / f"sweep__{rule.name.replace('/', '_')}.csv", base, bars)
        dev.append(
            {
                "rule": rule,
                "base": stats(base, n, bars),
                "double": stats(dbl, n, bars),
                "raw_edge": raw_edge(raw),
            }
        )
        print(rule.name, dev[-1]["base"]["net_usd"], dev[-1]["raw_edge"], flush=True)

    check = []
    for r in dev:
        if r["double"]["net_usd"] > 0:
            base, n = run_sweep(bars, days, r["rule"], costs, sizing, CHECK)
            dbl, _ = run_sweep(bars, days, r["rule"], stress, sizing, CHECK)
            check.append(
                {
                    "rule": r["rule"].name,
                    "base": stats(base, n, bars),
                    "double": stats(dbl, n, bars),
                }
            )

    payload = {
        "video": "https://www.youtube.com/watch?v=ctLHzjrH3Rk",
        "account_usd": sizing.account_usd,
        "risk_per_trade_usd": sizing.risk_usd,
        "dev_years": [DEV.start, DEV.stop - 1],
        "holdout": "2026 not loaded",
        "dev": [{**r, "rule": r["rule"].name} for r in dev],
        "check_2025": check,
    }
    OUT.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n"
    )
    OUT.with_suffix(".md").write_text(render_md(dev, check))
    print("wrote", OUT)


def render_md(dev: list[dict[str, Any]], check: list[dict[str, Any]]) -> str:
    L = [
        "# YouTube 'daily zone + liquidity sweep' gold strategy, backtested",
        "",
        "Source: *Gold Trading Strategy That Every Trader Should Know!* (The Trading "
        "School). Previous day's upper wick = supply (sells only), lower wick = demand "
        "(buys only), mother candle if inside day. On 15-minute candles: a candle "
        "sweeps the previous candle's high/low inside the zone and closes back; enter "
        "when a later candle closes beyond the sweep candle's other end; stop beyond "
        "the sweep extreme; fixed R target; closed by 16:45 New York. Exact rules and "
        "assumptions: `src/trading_bot/backtesting/sweep_strategy.py`.",
        "",
        "$3,000 account, $30 risk (1%) per trade, expensive costs (recorded bid/ask + "
        "$0.20 extra spread, $0.10 slippage per fill, $8/lot); 2x doubles them. "
        "Development 2014-2024; 2025 only for variants positive at 2x; "
        "2026 not loaded.",
        "",
        "## 2014-2024",
        "",
        "| Variant | Trades | Per day | Win % | Net $ | $/day | Worst day $ | "
        "Max DD $ | PF | Net $ at 2x | Edge before costs $/oz | t "
        "| In profit after 15 min |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
        "| ---: | ---: |",
    ]
    for r in dev:
        b, d, e = r["base"], r["double"], r["raw_edge"]
        pf = f"{b['profit_factor']:.2f}" if b["profit_factor"] else "-"
        L.append(
            f"| {r['rule'].name} | {b['trades']:,} | {b['trades_per_day']:.2f} | "
            f"{b['win_rate']:.0%} | {fmt(b['net_usd'])} | {b['avg_per_day']:.2f} | "
            f"{fmt(b['worst_day'])} | {fmt(b['max_drawdown_usd'])} | {pf} | "
            f"{fmt(d['net_usd'])} | {e['usd_per_oz']:+.2f} | {e['t_stat']:+.1f} | "
            f"{b['pct_in_profit_after_15m']:.0%} |"
        )
    L += [
        "",
        "Exits (stop / target / end of day), losses worse than 1.5R, median hold:",
        "",
    ]
    for r in dev:
        b = r["base"]
        x = b["exit_mix"]
        L.append(
            f"- {r['rule'].name}: {x['stop']:,} / {x['target']:,} / "
            f"{x['time_exit']:,}; "
            f"{b['losses_beyond_1_5r']} trades lost more than $45; "
            f"median hold {b['median_hold_min']:.0f} min"
        )
    years = list(DEV)
    L += [
        "",
        "Net $ per year:",
        "",
        "| Variant | " + " | ".join(str(y) for y in years) + " |",
        "| --- |" + " ---: |" * len(years),
    ]
    for r in dev:
        by = r["base"]["by_year"]
        L.append(
            f"| {r['rule'].name} | "
            + " | ".join(fmt(by.get(y, 0.0)) for y in years)
            + " |"
        )
    L += [
        "",
        "## 2025 check (variants positive at 2x on 2014-2024)",
        "",
        "| Variant | Trades | Win % | Net $ | $/day | Worst day $ | Max DD $ "
        "| Net $ at 2x |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if not check:
        L.append(
            "| (none: no variant was profitable at 2x on 2014-2024) | | | | | | | |"
        )
    for c in check:
        b, d = c["base"], c["double"]
        L.append(
            f"| {c['rule']} | {b['trades']:,} | {b['win_rate']:.0%} | "
            f"{fmt(b['net_usd'])} | {b['avg_per_day']:.2f} | {fmt(b['worst_day'])} | "
            f"{fmt(b['max_drawdown_usd'])} | "
            f"{fmt(d['net_usd'])} |"
        )
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
