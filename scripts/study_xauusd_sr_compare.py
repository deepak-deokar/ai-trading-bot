"""Support and resistance round 2: each level type alone, ADR-scaled, against a
random-entry baseline. Rules fixed beforehand in docs/xauusd-sr-v2-plan.md.

* Equiti cautious costs (config/xauusd_costs_equiti.yaml), $30 risk on $3,000.
* 30 combinations: 5 level types x bounce / retest / breakout x 1R / 1.5R
  ("all levels together" shown for reference, never chosen).
* Development 2014-2022, every setup counted (no daily cap). Pass: average $ per
  trade beats >= 95 of 100 random-time twin runs, money made on 2014-2020 and on
  2021-2022, >= 200 trades.
* Only if something passes: one look at 2023-2024 with one trade at a time, at most
  2 a day; profitable at 1x and 2x costs, >= 60 trades, largest drop < $600, beats
  >= 95 of 100 twin runs.
2025-2026 never loaded.

Writes docs/xauusd-sr-compare.{json,md}.
Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/study_xauusd_sr_compare.py
"""

import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
from study_xauusd_news_model import summary  # type: ignore[import-not-found]

from trading_bot.backtesting import sr_compare as C
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, load_bars
from trading_bot.backtesting.sr_strategy import ADR_DAYS, ASIA_END, ZONE, Level, Mids
from trading_bot.backtesting.sweep_strategy import TradingDay, build_days
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_equiti.yaml")
OUT = Path("docs/xauusd-sr-compare")
RUNS = 100
SEED = 11
BEAT = 95
MIN_DEV_TRADES, MIN_TEST_TRADES = 200, 60
MAX_DD = 600.0

Combo = tuple[str, str, float]  # level type, setup, target R
Item = tuple[int, C.Result]  # day index, result


def collect(
    bars: dict[str, Array],
    days: Sequence[TradingDay],
    mid: Mids,
    years: range,
    costs: CostModel,
) -> dict[Combo, list[Item]]:
    out: dict[Combo, list[Item]] = defaultdict(list)
    for k, d in enumerate(days):
        if d.day.year not in years or k < ADR_DAYS:
            continue
        for s in C.find_signals(bars, days, k, mid):
            for tr in C.TARGETS:
                r = C.simulate(bars, mid, d, s, tr, costs)
                if r is not None:
                    out[(s.ltype, s.kind, tr)].append((k, r))
    return out


def twin_results(
    bars: dict[str, Array],
    days: Sequence[TradingDay],
    mid: Mids,
    items: Sequence[Item],
    marks: dict[int, Array],
    rng: np.random.Generator,
    costs: CostModel,
) -> list[C.Result]:
    out = []
    for k, r in items:
        # only marks after the real entry: the twin knows the direction, so an
        # earlier entry would trade the move that created the signal
        mk = marks[k][marks[k] > r.signal.entry_minute]
        if len(mk) == 0:
            continue
        e = int(mk[rng.integers(len(mk))])
        t = C.twin(bars, mid, days[k], r, e, costs)
        if t is not None:
            sig = replace(r.signal, entry_minute=e)
            out.append(C.Result(sig, r.target_r, r.risk_mid, t))
    return out


def avg(trades: Sequence[HoldTrade]) -> float:
    return float(np.mean([t.pnl_usd for t in trades])) if trades else 0.0


def baseline(real: float, twin_avgs: Sequence[float]) -> dict[str, float | int | None]:
    a = np.array(twin_avgs)
    return {
        "twin_avg_per_trade": round(float(a.mean()), 2),
        "twin_p5": round(float(np.percentile(a, 5)), 2),
        "twin_p95": round(float(np.percentile(a, 95)), 2),
        "beats": int((a < real).sum()),
    }


def zone_share(
    bars: dict[str, Array], days: Sequence[TradingDay], mid: Mids, years: range
) -> dict[str, float]:
    """Share of 15-minute candles closing 03:00-13:00 that touch a level's zone."""
    from trading_bot.backtesting.sr_strategy import (
        FIRST_CLOSE,
        LAST_CLOSE,
        _candles15,
        _ny_epoch,
        adr_at,
    )

    hit: dict[str, int] = defaultdict(int)
    total = 0
    m = bars["minute_utc"]
    for k, d in enumerate(days):
        if d.day.year not in years or k < ADR_DAYS:
            continue
        adr = adr_at(days, k)
        if not adr:
            continue
        lv = C.type_levels(bars, mid, days, k, adr)
        a1 = int(np.searchsorted(m, _ny_epoch(d.day, ASIA_END)))
        lv["asia"] = []
        if a1 > d.i0:
            lv["asia"] = [
                Level(float(mid.h[d.i0 : a1].max())),
                Level(float(mid.lo[d.i0 : a1].min())),
            ]
        lv["all"] = [x for t in C.TYPES for x in lv[t]]
        starts, ends = _candles15(m, d.i0, d.i1)
        ct = (m[starts] // 900 + 1) * 900
        t0, t1 = _ny_epoch(d.day, FIRST_CLOSE), _ny_epoch(d.day, LAST_CLOSE)
        z = ZONE * adr
        for a, b, t in zip(starts, ends, ct, strict=True):
            if not (t0 <= t <= t1):
                continue
            total += 1
            h, lo = mid.h[a:b].max(), mid.lo[a:b].min()
            for name, levels in lv.items():
                if any(lo <= x.price + z and h >= x.price - z for x in levels):
                    hit[name] += 1
    return {n: round(hit[n] / total, 3) for n in (*C.TYPES, "all")}


def years_of(items: Sequence[Item], y0: int, y1: int) -> list[Item]:
    return [x for x in items if y0 <= x[1].signal.day.year <= y1]


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    bars = load_bars(BARS_DIR, 201401, 202412)
    days = build_days(bars)
    mid = Mids.of(bars)
    dev_years = range(2014, 2023)
    res = collect(bars, days, mid, dev_years, costs)
    marks = {
        k: C.entry_marks(bars, d)
        for k, d in enumerate(days)
        if d.day.year in range(2014, 2025) and k >= ADR_DAYS
    }
    rng = np.random.default_rng(SEED)
    combos = sorted(res)
    twin_avgs: dict[Combo, list[float]] = defaultdict(list)
    for run in range(RUNS):
        for c in combos:
            tw = twin_results(bars, days, mid, res[c], marks, rng, costs)
            twin_avgs[c].append(avg([r.trade for r in tw]))
        if run % 10 == 0:
            print("twin run", run, flush=True)

    rows = []
    for c in combos:
        items = res[c]
        all_t = [r.trade for _, r in items]
        early = summary([r.trade for _, r in years_of(items, 2014, 2020)])
        late = summary([r.trade for _, r in years_of(items, 2021, 2022)])
        b = baseline(avg(all_t), twin_avgs[c])
        s = summary(all_t)
        row = {
            "level_type": c[0],
            "setup": c[1],
            "target_r": c[2],
            "trades": s.get("trades", 0),
            "win_rate": s.get("win_rate"),
            "avg_per_trade": s.get("avg_per_trade"),
            "net_2014_2020": early.get("net_usd", 0.0),
            "net_2021_2022": late.get("net_usd", 0.0),
            "net_2014_2022": s.get("net_usd", 0.0),
            **b,
        }
        row["passes"] = bool(
            c[0] != "all"
            and b["beats"] is not None
            and int(b["beats"]) >= BEAT
            and row["net_2014_2020"] > 0
            and row["net_2021_2022"] > 0
            and row["trades"] >= MIN_DEV_TRADES
        )
        rows.append(row)
        print(
            f"{c[0]:9s} {c[1]:8s} {c[2]}R n={row['trades']:5d} "
            f"win={row['win_rate']} avg={row['avg_per_trade']} "
            f"twin={b['twin_avg_per_trade']} beats={b['beats']} pass={row['passes']}",
            flush=True,
        )

    share = zone_share(bars, days, mid, dev_years)
    print("zone share", share)
    passed = [r for r in rows if r["passes"]]
    test: dict[str, Any] | None = None
    if passed:
        ch = max(passed, key=lambda r: (r["beats"], r["avg_per_trade"]))
        combo = (ch["level_type"], ch["setup"], ch["target_r"])
        test = run_test(bars, days, mid, combo, marks, costs, stress)
        test["combo"] = list(combo)
        print("test", test["summary"], test["summary_2x"], test["baseline"])

    result = {
        "costs": COSTS_YAML.stem,
        "plan": "docs/xauusd-sr-v2-plan.md",
        "twin_runs": RUNS,
        "zone_share": share,
        "rows": rows,
        "passed_development": [
            [r["level_type"], r["setup"], r["target_r"]] for r in passed
        ],
        "test_2023_2024": test,
    }
    OUT.with_suffix(".json").write_text(json.dumps(result, indent=2, default=str))
    OUT.with_suffix(".md").write_text(render_md(result))
    print("wrote", OUT)


def run_test(
    bars: dict[str, Array],
    days: Sequence[TradingDay],
    mid: Mids,
    combo: Combo,
    marks: dict[int, Array],
    costs: CostModel,
    stress: CostModel,
) -> dict[str, Any]:
    years = range(2023, 2025)
    items = collect(bars, days, mid, years, costs)[combo]
    items_2x = collect(bars, days, mid, years, stress)[combo]
    real = C.take([r for _, r in items])
    real_2x = C.take([r for _, r in items_2x])
    rng = np.random.default_rng(SEED + 1)
    tw = [
        avg(C.take(twin_results(bars, days, mid, items, marks, rng, costs)))
        for _ in range(RUNS)
    ]
    s, s2 = summary(real), summary(real_2x)
    b = baseline(avg(real), tw)
    passed = bool(
        s.get("trades", 0) >= MIN_TEST_TRADES
        and s.get("net_usd", 0) > 0
        and s2.get("net_usd", 0) > 0
        and s.get("max_drawdown_usd", 1e9) < MAX_DD
        and int(b["beats"] or 0) >= BEAT
    )
    return {"summary": s, "summary_2x": s2, "baseline": b, "passed": passed}


def money(v: float | None) -> str:
    if v is None:
        return "-"
    return f"-${-v:,.0f}" if v < 0 else f"+${v:,.0f}"


def render_md(r: dict[str, Any]) -> str:
    lines = [
        "# XAUUSD support and resistance, round 2: each level against random entries",
        "",
        f"Rules fixed before running: [{r['plan']}](xauusd-sr-v2-plan.md). Costs: "
        f"{r['costs']}. $30 risk per trade. Development years 2014-2022, every "
        "setup counted on its own (no daily cap).",
        "",
        "**Twin** = the same trade (day, direction, stop distance, target) entered at "
        "a random 15-minute mark after the real entry, up to 13:00 New York, "
        f"{r['twin_runs']} times. "
        "**Beats** = how many of those runs the real setup's average $ per trade "
        f"beat. Passing needs {BEAT}+, money made in 2014-20 and 2021-22, and "
        f"{MIN_DEV_TRADES}+ trades.",
        "",
        "| Level | Setup | Target | Trades | Win rate | Avg $/trade | Twin avg "
        "| Beats | 2014-20 | 2021-22 | Pass |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for x in sorted(r["rows"], key=lambda x: (x["level_type"] == "all", -x["beats"])):
        lines.append(
            f"| {x['level_type']} | {x['setup']} | {x['target_r']}R | {x['trades']} "
            f"| {x['win_rate']:.0%} | {x['avg_per_trade']:+.2f} "
            f"| {x['twin_avg_per_trade']:+.2f} | {x['beats']} "
            f"| {money(x['net_2014_2020'])} | {money(x['net_2021_2022'])} "
            f"| {'yes' if x['passes'] else 'no'} |"
        )
    lines += [
        "",
        "## How often price sits at a level",
        "",
        "Share of 15-minute candles (03:00-13:00, 2014-2022) that touch a level's "
        "zone:",
        "",
        "| Level type | Share |",
        "|---|---:|",
    ]
    for k, v in r["zone_share"].items():
        lines.append(f"| {k} | {v:.0%} |")
    lines += ["", "## 2023-2024 test", ""]
    t = r["test_2023_2024"]
    if t is None:
        lines.append(
            "Nothing passed development, so 2023-2024 was not looked at (as planned)."
        )
    else:
        s, s2, b = t["summary"], t["summary_2x"], t["baseline"]
        lines += [
            f"Combination: {' / '.join(map(str, t['combo']))}, one trade at a time, "
            "at most 2 a day.",
            "",
            f"* {s.get('trades', 0)} trades, {s.get('win_rate', 0):.0%} winners, "
            f"net {money(s.get('net_usd'))}, at 2x costs {money(s2.get('net_usd'))}, "
            f"largest drop ${s.get('max_drawdown_usd', 0):,.0f}",
            f"* beats {b['beats']} of {r['twin_runs']} twin runs "
            f"(twin average {b['twin_avg_per_trade']:+.2f} $/trade)",
            f"* **passed: {'yes' if t['passed'] else 'no'}**",
        ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
