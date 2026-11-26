"""Level breakouts: raw edge without costs first, then costs back in.

Rules fixed beforehand in docs/xauusd-breakout-plan.md.

* 60 variants: levels (yesterday / swing / both) x stop (behind the level, or
  0.25 / 0.4 / 0.6 / 0.8 ADR) x target (1R / 1.5R / 2R / hold to 16:45).
* Step 1 (2014-2022, no costs, mid-price fills): excess R over hour-matched twins
  (200 runs) must be >= 2 x the cost R in 2014-2020 and in 2021-2022; >= 200 trades.
* Step 2 (Equiti cautious costs): money on 2014-2020 (also 2x) and 2021-2022, beats
  >= 99% of 1,000 hour-matched twin runs; pick the highest net R per trade.
* Step 3 (2023-2024, once, only if step 2 passes): one trade at a time, at most 2 a
  day; profitable at 1x and 2x, >= 60 trades, largest drop < $600, beats >= 99% of
  1,000 hour-matched twin runs.
2025-2026 never loaded.

Writes docs/xauusd-breakout.{json,md}.
Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/study_xauusd_breakout.py
(BO_RUNS=20 for a quick check).
"""

import json
import multiprocessing as mp
import os
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, time
from pathlib import Path
from typing import Any

import numpy as np
from study_xauusd_news_model import summary  # type: ignore[import-not-found]

from trading_bot.backtesting import breakout as B
from trading_bot.backtesting import sr_compare as C
from trading_bot.backtesting.news_day import NY
from trading_bot.backtesting.session_window import Array, CostModel, load_bars
from trading_bot.backtesting.sr_strategy import ADR_DAYS, Mids, adr_at
from trading_bot.backtesting.sweep_strategy import TradingDay, build_days
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_equiti.yaml")
OUT = Path("docs/xauusd-breakout")
SCALE = int(os.environ.get("BO_RUNS", "1000"))
RUNS_RAW, RUNS_NET = max(SCALE // 5, 8), SCALE
SEED = 23
EARLY, LATE = (2014, 2020), (2021, 2022)
MIN_TRADES, MIN_TEST_TRADES = 200, 60
COST_MULTIPLE = 2.0
BEAT = 0.99
MAX_DD = 600.0
WORKERS = 8


@dataclass
class World:
    bars: dict[str, Array]
    mid: Mids
    days: list[TradingDay]
    adrs: dict[int, float]
    year_days: dict[int, list[int]]
    costs: CostModel


WORLDS: dict[str, World] = {}  # "raw" and "net"; set before forking workers

Item = tuple[int, C.Result]  # day index, result
Pair = tuple[int, C.Result, C.Result]  # day index, no-cost result, cost result


def period(year: int) -> str | None:
    if EARLY[0] <= year <= EARLY[1]:
        return "early"
    if LATE[0] <= year <= LATE[1]:
        return "late"
    return None


def signals(w: World, years: range) -> dict[str, list[tuple[int, C.Signal]]]:
    out: dict[str, list[tuple[int, C.Signal]]] = defaultdict(list)
    for k, d in enumerate(w.days):
        if d.day.year not in years or k not in w.adrs:
            continue
        for s in C.find_signals(w.bars, w.days, k, w.mid, B.LEVELS):
            if s.kind == "breakout":
                out[s.ltype].append((k, s))
    return out


def run_variant(
    w: World, sigs: Sequence[tuple[int, C.Signal]], v: B.Variant, costs: CostModel
) -> list[Item]:
    out = []
    for k, s in sigs:
        r = B.simulate(w.bars, w.mid, w.days[k], s, v, costs)
        if r is not None:
            out.append((k, r))
    return out


def clock_of(w: World, minute: int) -> time:
    return datetime.fromtimestamp(int(w.bars["minute_utc"][minute]), NY).time()


def _twins(
    args: tuple[str, list[int], dict[str, list[Item]], dict[str, list[time]], bool],
) -> dict[str, list[dict[str, float]]]:
    """Per variant, per run: sums and counts of twin R by period and $ overall."""
    world, runs, items, clocks, capped = args
    w = WORLDS[world]
    out: dict[str, list[dict[str, float]]] = {v: [] for v in items}
    for run in runs:
        rng = np.random.default_rng([SEED, run, world == "net"])
        for v, its in items.items():
            res: list[C.Result] = []
            for (k, r), clock in zip(its, clocks[v], strict=True):
                pool = w.year_days[w.days[k].day.year]
                k2 = pool[int(rng.integers(len(pool)))]
                if k2 == k:
                    continue
                got = C.hour_twin(
                    w.bars, w.mid, w.days[k2], w.adrs[k2], r, clock, w.costs
                )
                if got is None:
                    continue
                e, t = got
                risk2 = r.risk_mid / r.signal.adr * w.adrs[k2]
                sig = replace(r.signal, entry_minute=e, day=w.days[k2].day)
                res.append(C.Result(sig, r.target_r, risk2, t))
            if capped:
                kept = {id(t) for t in C.take(res)}
                res = [x for x in res if id(x.trade) in kept]
            acc: dict[str, float] = defaultdict(float)
            for x in res:
                p = period(x.signal.day.year) or "test"
                acc[f"r_{p}"] += B.r_of(x)
                acc[f"n_{p}"] += 1
                acc["usd"] += x.trade.pnl_usd
                acc["n"] += 1
            out[v].append(dict(acc))
    return out


def twin_runs(
    world: str, items: dict[str, list[Item]], runs: int, capped: bool = False
) -> dict[str, list[dict[str, float]]]:
    w = WORLDS[world]
    clocks = {
        v: [clock_of(w, r.signal.entry_minute) for _, r in its]
        for v, its in items.items()
    }
    chunks = [list(range(i, runs, WORKERS)) for i in range(WORKERS)]
    with mp.get_context("fork").Pool(WORKERS) as pool:
        parts = pool.map(
            _twins, [(world, ch, items, clocks, capped) for ch in chunks if ch]
        )
    out: dict[str, list[dict[str, float]]] = {v: [] for v in items}
    for p in parts:
        for v, rows in p.items():
            out[v] += rows
    return out


def mean(xs: Sequence[float]) -> float:
    return float(np.mean(xs)) if len(xs) else 0.0


def step1_row(
    v: B.Variant, pairs: Sequence[Pair], twins: Sequence[dict[str, float]]
) -> dict[str, Any]:
    row: dict[str, Any] = {"variant": v.name, "trades": len(pairs)}
    ok = len(pairs) >= MIN_TRADES
    for p in ("early", "late"):
        ps = [x for x in pairs if period(x[1].signal.day.year) == p]
        raw = [B.r_of(a) for _, a, _ in ps]
        cost = [B.r_of(a) - B.r_of(b) for _, a, b in ps]
        n_t = sum(t.get(f"n_{p}", 0) for t in twins)
        twin = sum(t.get(f"r_{p}", 0.0) for t in twins) / n_t if n_t else 0.0
        excess = mean(raw) - twin
        row[p] = {
            "trades": len(ps),
            "raw_r": round(mean(raw), 4),
            "twin_r": round(twin, 4),
            "excess_r": round(excess, 4),
            "cost_r": round(mean(cost), 4),
            "win_rate_raw": round(mean([x > 0 for x in raw]), 3),
            "avg_stop_usd": round(mean([a.risk_mid for _, a, _ in ps]), 2),
        }
        ok = ok and excess >= COST_MULTIPLE * mean(cost) and len(ps) > 0
    row["passes_step1"] = bool(ok)
    return row


def beats(real: float, twins: Sequence[dict[str, float]]) -> float:
    avgs = np.array([t["usd"] / t["n"] for t in twins if t.get("n")])
    return round(float((avgs < real).mean()), 4) if len(avgs) else 0.0


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    bars = load_bars(BARS_DIR, 201401, 202412)
    days = build_days(bars)
    mid = Mids.of(bars)
    adrs: dict[int, float] = {}
    year_days: dict[int, list[int]] = defaultdict(list)
    for k, d in enumerate(days):
        a = adr_at(days, k)
        if k >= ADR_DAYS and a:
            adrs[k] = a
            year_days[d.day.year].append(k)
    WORLDS["raw"] = World(B.mid_bars(bars), mid, days, adrs, year_days, B.NO_COSTS)
    WORLDS["net"] = World(bars, mid, days, adrs, year_days, costs)
    raw_w, net_w = WORLDS["raw"], WORLDS["net"]

    sigs = signals(net_w, range(2014, 2023))
    print({k: len(v) for k, v in sigs.items()}, flush=True)

    # step 1: raw edge without costs
    raw_items: dict[str, list[Item]] = {}
    pairs: dict[str, list[Pair]] = {}
    for v in B.VARIANTS:
        a = run_variant(raw_w, sigs[v.levels], v, B.NO_COSTS)
        b = {r.signal: r for _, r in run_variant(net_w, sigs[v.levels], v, costs)}
        pairs[v.name] = [(k, r, b[r.signal]) for k, r in a if r.signal in b]
        raw_items[v.name] = [(k, r) for k, r, _ in pairs[v.name]]
    tw_raw = twin_runs("raw", raw_items, RUNS_RAW)
    rows = []
    for v in B.VARIANTS:
        row = step1_row(v, pairs[v.name], tw_raw[v.name])
        rows.append(row)
        e, la = row["early"], row["late"]
        print(
            f"{v.name:45s} n={row['trades']:5d} "
            f"early raw={e['raw_r']:+.3f} ex={e['excess_r']:+.3f} "
            f"cost={e['cost_r']:.3f} | late raw={la['raw_r']:+.3f} "
            f"ex={la['excess_r']:+.3f} cost={la['cost_r']:.3f} "
            f"stop=${e['avg_stop_usd']}/{la['avg_stop_usd']} "
            f"pass={row['passes_step1']}",
            flush=True,
        )

    # step 2: costs back in, for survivors
    survivors = [v for v, r in zip(B.VARIANTS, rows, strict=True) if r["passes_step1"]]
    step2: list[dict[str, Any]] = []
    if survivors:
        net_items = {v.name: [(k, b) for k, _, b in pairs[v.name]] for v in survivors}
        tw_net = twin_runs("net", net_items, RUNS_NET)
        for v in survivors:
            its = net_items[v.name]
            stressed = run_variant(
                net_w,
                [x for x in sigs[v.levels] if x[1].day.year <= EARLY[1]],
                v,
                stress,
            )
            all_t = [r.trade for _, r in its]
            early = summary(
                [r.trade for _, r in its if period(r.signal.day.year) == "early"]
            )
            late = summary(
                [r.trade for _, r in its if period(r.signal.day.year) == "late"]
            )
            early_2x = summary([r.trade for _, r in stressed])
            b = beats(mean([t.pnl_usd for t in all_t]), tw_net[v.name])
            net_r = mean([B.r_of(r) for _, r in its])
            ok = bool(
                early.get("net_usd", 0) > 0
                and early_2x.get("net_usd", 0) > 0
                and late.get("net_usd", 0) > 0
                and b >= BEAT
            )
            step2.append(
                {
                    "variant": v.name,
                    "net_r": round(net_r, 4),
                    "net_2014_2020": early.get("net_usd", 0.0),
                    "net_2014_2020_2x": early_2x.get("net_usd", 0.0),
                    "net_2021_2022": late.get("net_usd", 0.0),
                    "win_rate": summary(all_t).get("win_rate"),
                    "beats_hour_twins": b,
                    "passes_step2": ok,
                }
            )
            print("step2", step2[-1], flush=True)

    test: dict[str, Any] | None = None
    passed = [s for s in step2 if s["passes_step2"]]
    if passed:
        ch = max(passed, key=lambda s: s["net_r"])
        v = next(x for x in B.VARIANTS if x.name == ch["variant"])
        test = run_test(v, costs, stress)
        print("test", test, flush=True)

    result = {
        "plan": "docs/xauusd-breakout-plan.md",
        "costs": COSTS_YAML.stem,
        "twin_runs_raw": RUNS_RAW,
        "twin_runs_net": RUNS_NET,
        "step1": rows,
        "step2": step2,
        "test_2023_2024": test,
    }
    OUT.with_suffix(".json").write_text(json.dumps(result, indent=2, default=str))
    OUT.with_suffix(".md").write_text(render_md(result))
    print("wrote", OUT)


def run_test(v: B.Variant, costs: CostModel, stress: CostModel) -> dict[str, Any]:
    w = WORLDS["net"]
    sigs = signals(w, range(2023, 2025))[v.levels]
    its = run_variant(w, sigs, v, costs)
    real = C.take([r for _, r in its])
    real_2x = C.take([r for _, r in run_variant(w, sigs, v, stress)])
    tw = twin_runs("net", {v.name: its}, RUNS_NET, capped=True)[v.name]
    s, s2 = summary(real), summary(real_2x)
    b = beats(mean([t.pnl_usd for t in real]), tw)
    passed = bool(
        s.get("trades", 0) >= MIN_TEST_TRADES
        and s.get("net_usd", 0) > 0
        and s2.get("net_usd", 0) > 0
        and s.get("max_drawdown_usd", 1e9) < MAX_DD
        and b >= BEAT
    )
    return {
        "variant": v.name,
        "summary": s,
        "summary_2x": s2,
        "beats_hour_twins": b,
        "passed": passed,
    }


def money(v: float | None) -> str:
    if v is None:
        return "-"
    return f"-${-v:,.0f}" if v < 0 else f"+${v:,.0f}"


def render_md(r: dict[str, Any]) -> str:
    lines = [
        "# XAUUSD level breakouts: raw edge first, then costs",
        "",
        f"Rules fixed before running: [{r['plan']}](xauusd-breakout-plan.md). "
        "Development years 2014-2022, every setup on its own.",
        "",
        "## Step 1: no costs (fills at the mid price)",
        "",
        "All numbers are **R per trade** (1R = the stop distance). **Raw** = average "
        "result with no costs. **Twin** = the same trade at the same clock time on a "
        f"random other day ({r['twin_runs_raw']} runs). **Excess** = raw - twin, the "
        "level's own edge. **Cost** = what Equiti cautious costs take per trade on "
        "the same setups. To pass, excess must be at least 2x cost in both periods.",
        "",
        "| Variant | Trades | Stop $ 14-20 / 21-22 | Raw 14-20 | Excess 14-20 "
        "| Cost 14-20 | Raw 21-22 | Excess 21-22 | Cost 21-22 | Pass |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for x in sorted(
        r["step1"], key=lambda x: -x["early"]["excess_r"] - x["late"]["excess_r"]
    ):
        e, la = x["early"], x["late"]
        lines.append(
            f"| {x['variant']} | {x['trades']} "
            f"| ${e['avg_stop_usd']:.0f} / ${la['avg_stop_usd']:.0f} "
            f"| {e['raw_r']:+.3f} | {e['excess_r']:+.3f} | {e['cost_r']:.3f} "
            f"| {la['raw_r']:+.3f} | {la['excess_r']:+.3f} | {la['cost_r']:.3f} "
            f"| {'yes' if x['passes_step1'] else 'no'} |"
        )
    lines += ["", "## Step 2: costs back in", ""]
    if not r["step2"]:
        lines.append("Nothing passed step 1, so step 2 did not run.")
    else:
        lines += [
            f"Equiti cautious costs; hour-matched twins after costs, "
            f"{r['twin_runs_net']} runs.",
            "",
            "| Variant | Net R/trade | 2014-20 | 2014-20 at 2x | 2021-22 | Win "
            "| Beats twins | Pass |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for s in r["step2"]:
            lines.append(
                f"| {s['variant']} | {s['net_r']:+.3f} | {money(s['net_2014_2020'])} "
                f"| {money(s['net_2014_2020_2x'])} | {money(s['net_2021_2022'])} "
                f"| {s['win_rate']:.0%} | {s['beats_hour_twins']:.1%} "
                f"| {'yes' if s['passes_step2'] else 'no'} |"
            )
    lines += ["", "## Step 3: 2023-2024", ""]
    t = r["test_2023_2024"]
    if t is None:
        lines.append("Nothing passed step 2, so 2023-2024 was not looked at.")
    else:
        s, s2 = t["summary"], t["summary_2x"]
        lines += [
            f"{t['variant']}, one trade at a time, at most 2 a day.",
            "",
            f"* {s.get('trades', 0)} trades, {s.get('win_rate', 0):.0%} winners, net "
            f"{money(s.get('net_usd'))}, at 2x costs {money(s2.get('net_usd'))}, "
            f"largest drop ${s.get('max_drawdown_usd', 0):,.0f}",
            f"* beats {t['beats_hour_twins']:.1%} of hour-matched twin runs",
            f"* **passed: {'yes' if t['passed'] else 'no'}**",
        ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
