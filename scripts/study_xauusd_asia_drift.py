"""Asia-session buy, optionally only after gold has fallen.

Rules: docs/xauusd-asia-drift-plan.md (written before running). 36 variants
(filter x entry x exit x stop), Equiti cautious costs and 2x, same-day random-time
twins (1,000 runs). Step 1 on 2014-2022; step 2 (2023-2024) once, only if a variant
passes. 2025-2026 never loaded.

Writes docs/xauusd-asia-drift.{json,md}.
Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/study_xauusd_asia_drift.py
"""

import itertools
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from study_xauusd_news_model import summary  # type: ignore[import-not-found]

from trading_bot.backtesting.news_day import NY, execute
from trading_bot.backtesting.session_window import CostModel, Sizing, load_bars
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_equiti.yaml")
OUT = Path("docs/xauusd-asia-drift")
RUNS = int(os.environ.get("ASIA_RUNS", "1000"))
SEED = 11
FILTERS = ("none", "fall_20d", "below_50d")
ENTRIES = (18, 19, 20)
EXITS = (2, 3)
STOPS = (0.5, 0.75)
MAX_STOP_USD = 30.0
LAST_TWIN = time(16, 45)


@dataclass(frozen=True)
class Day:
    k: int
    day: date
    i0: int
    i1: int
    adr: float
    chg20: float
    below50: bool


def ts(d: date, at: time, evening: bool) -> int:
    base = d - timedelta(days=1) if evening else d
    return int(datetime.combine(base, at, tzinfo=NY).timestamp())


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    costs2 = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    bars = load_bars(BARS_DIR, 201401, 202412)
    tdays = build_days(bars)
    m = bars["minute_utc"]
    closes = [d.close for d in tdays]
    ranges = [d.high - d.low for d in tdays]
    days: list[Day] = []
    for k, d in enumerate(tdays):
        if k < 50:
            continue
        adr = float(np.mean(ranges[k - 20 : k]))
        prev = closes[k - 1]
        days.append(
            Day(
                k,
                d.day,
                d.i0,
                d.i1,
                adr,
                (prev - closes[k - 21]) / adr,
                prev < float(np.mean(closes[k - 50 : k])),
            )
        )
    cut = float(np.quantile([d.chg20 for d in days if d.day.year <= 2020], 1 / 3))

    def passes(d: Day, f: str) -> bool:
        return (
            f == "none"
            or (f == "fall_20d" and d.chg20 <= cut)
            or (f == "below_50d" and d.below50)
        )

    def idx(d: Day, t: int) -> int | None:
        i = int(np.searchsorted(m, t))
        return i if d.i0 <= i < d.i1 else None

    def trade(d: Day, start: int, end: int, k_stop: float, c: CostModel) -> Any:
        if k_stop * d.adr > MAX_STOP_USD:
            return None
        s, e = idx(d, start), idx(d, end)
        if s is None or e is None or e - 1 <= s:
            return None
        return execute(
            bars, d.day, s, e - 1, 1, c, Sizing(), risk=k_stop * d.adr, target_r=None
        )

    # ---- twins: every half-hour start on each day, per holding time and stop ----
    holds = sorted({(24 - h0) + h1 for h0 in ENTRIES for h1 in EXITS})
    twin: dict[tuple[int, int, float], np.ndarray] = {}
    for d in days:
        first = ts(d.day, time(18), True)
        last_end = ts(d.day, LAST_TWIN, False)
        for h in holds:
            for st in STOPS:
                pnl = []
                start = first
                while start + h * 3600 <= last_end:
                    t = trade(d, start, start + h * 3600, st, costs)
                    if t is not None:
                        pnl.append(t.pnl_usd)
                    start += 1800
                twin[(d.k, h, st)] = np.array(pnl)
    print("twins ready", flush=True)

    rng = np.random.default_rng(SEED)
    rows: list[dict[str, Any]] = []
    keep: dict[str, Any] = {}
    for f, h0, h1, st in itertools.product(FILTERS, ENTRIES, EXITS, STOPS):
        name = f"{f} / buy {h0}:00 / exit 0{h1}:00 / stop {st} ADR"
        hold = (24 - h0) + h1
        t1, t2 = [], []
        for d in days:
            if not passes(d, f):
                continue
            a, b = ts(d.day, time(h0), True), ts(d.day, time(h1), False)
            t = trade(d, a, b, st, costs)
            if t is None:
                continue
            t1.append((d, t))
            t2.append(trade(d, a, b, st, costs2))

        def sel(lo: int, hi: int, src: list[Any]) -> list[Any]:
            return [x for x in src if lo <= x.day.year <= hi]

        net = [t for _, t in t1]
        stress = [t for t in t2 if t is not None]
        early, late = sel(2014, 2020, net), sel(2021, 2022, net)
        early2 = sel(2014, 2020, stress)
        dev = [(d, t) for d, t in t1 if d.day.year <= 2022]
        real_avg = float(np.mean([t.pnl_usd for _, t in dev])) if dev else 0.0
        pools = [twin[(d.k, hold, st)] for d, _ in dev]
        pools = [p for p in pools if len(p)]
        sims = np.zeros(RUNS)
        for p in pools:
            sims += p[rng.integers(0, len(p), RUNS)]
        sims /= max(len(pools), 1)
        beats = float(np.mean(sims < real_avg))
        s_early, s_late, s_early2 = summary(early), summary(late), summary(early2)
        row = {
            "variant": name,
            "filter": f,
            "entry": h0,
            "exit": h1,
            "stop_adr": st,
            "trades_2014_2022": len(dev),
            "net_2014_2020": s_early.get("net_usd", 0.0),
            "per_trade_2014_2020": s_early.get("avg_per_trade", 0.0),
            "win_2014_2020": s_early.get("win_rate", 0.0),
            "net_2014_2020_2x": s_early2.get("net_usd", 0.0),
            "net_2021_2022": s_late.get("net_usd", 0.0),
            "per_trade_2021_2022": s_late.get("avg_per_trade", 0.0),
            "avg_per_trade_2014_2022": round(real_avg, 2),
            "twin_avg_2014_2022": round(float(sims.mean()), 2),
            "beats": round(beats, 4),
        }
        row["passed"] = bool(
            row["net_2014_2020"] > 0
            and row["net_2014_2020_2x"] > 0
            and row["net_2021_2022"] > 0
            and len(dev) >= 200
            and beats >= 0.99
        )
        rows.append(row)
        keep[name] = (f, h0, h1, st)
        print(
            name,
            row["per_trade_2014_2020"],
            row["per_trade_2021_2022"],
            row["beats"],
            row["passed"],
            flush=True,
        )

    over_95 = sum(r["beats"] >= 0.95 for r in rows)
    passed = [r for r in rows if r["passed"]]
    test: dict[str, Any] = {"run": False}
    if passed:
        best = max(passed, key=lambda r: r["per_trade_2014_2020"])
        f, h0, h1, st = keep[best["variant"]]
        hold = (24 - h0) + h1
        t1, t2, pools = [], [], []
        for d in days:
            if d.day.year < 2023 or not passes(d, f):
                continue
            a, b = ts(d.day, time(h0), True), ts(d.day, time(h1), False)
            t = trade(d, a, b, st, costs)
            if t is None:
                continue
            t1.append(t)
            t2.append(trade(d, a, b, st, costs2))
            p = twin[(d.k, hold, st)]
            if len(p):
                pools.append(p)
        s1 = summary(t1)
        s2 = summary([t for t in t2 if t is not None])
        sims = np.zeros(RUNS)
        for p in pools:
            sims += p[rng.integers(0, len(p), RUNS)]
        sims /= max(len(pools), 1)
        beats = float(np.mean(sims < s1.get("avg_per_trade", 0.0)))
        test = {
            "run": True,
            "variant": best["variant"],
            "result": s1,
            "net_2x": s2.get("net_usd", 0.0),
            "twin_avg": round(float(sims.mean()), 2),
            "beats": round(beats, 4),
            "passed": bool(
                s1.get("net_usd", 0) > 0
                and s2.get("net_usd", 0) > 0
                and s1.get("trades", 0) >= 60
                and s1.get("max_drawdown_usd", 1e9) < 600
                and beats >= 0.99
            ),
        }
    payload = {
        "rules": "docs/xauusd-asia-drift-plan.md",
        "fall_cut_adr": round(cut, 3),
        "runs": RUNS,
        "variants": rows,
        "over_95th": over_95,
        "expected_by_luck": round(0.05 * len(rows), 1),
        "step1_passed": [r["variant"] for r in passed],
        "test_2023_2024": test,
        "2025_2026": "not loaded",
    }
    OUT.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(payload))
    print(OUT.with_suffix(".md").read_text())


def render_md(p: dict[str, Any]) -> str:
    out = [
        "# Asia-session buy (after gold has fallen)",
        "",
        "Rules: `docs/xauusd-asia-drift-plan.md` (written before running). Buy only, "
        "time exit, ADR stop, $30 risk, Equiti cautious costs (2x as stress). Twins: "
        f"same day, random half-hour start, same holding time and stop, {p['runs']} "
        f"runs. 20-day fall = 20-day change <= {p['fall_cut_adr']} ADR (bottom third "
        "of 2014-2020). 2025-2026 not loaded.",
        "",
        f"Step 1 passed: **{len(p['step1_passed'])} of {len(p['variants'])}**. Beat "
        f"the twins' 95th percentile: {p['over_95th']} (about {p['expected_by_luck']} "
        "expected by luck).",
        "",
        "| Variant | Trades 14-22 | $/trade 14-20 | Win % 14-20 | Net 14-20 | "
        "Net 14-20 at 2x | $/trade 21-22 | Net 21-22 | Twins $/trade | Beats | Pass |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in sorted(p["variants"], key=lambda r: -r["per_trade_2014_2020"]):
        out.append(
            f"| {r['variant']} | {r['trades_2014_2022']} | "
            f"{r['per_trade_2014_2020']:+.2f} | {r['win_2014_2020']:.0%} | "
            f"{r['net_2014_2020']:+.0f} | {r['net_2014_2020_2x']:+.0f} | "
            f"{r['per_trade_2021_2022']:+.2f} | {r['net_2021_2022']:+.0f} | "
            f"{r['twin_avg_2014_2022']:+.2f} | {r['beats']:.1%} | "
            f"{'yes' if r['passed'] else 'no'} |"
        )
    t = p["test_2023_2024"]
    out += ["", "## 2023-2024", ""]
    if not t["run"]:
        out.append("Not looked at: nothing passed step 1.")
    else:
        s = t["result"]
        out += [
            f"Variant: {t['variant']}. Passed: **{'yes' if t['passed'] else 'no'}**.",
            "",
            "| Trades | Win % | Net $ | Net $ at 2x | Max drop $ | Twins $/trade | "
            "Real $/trade | Beats |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            f"| {s['trades']} | {s['win_rate']:.0%} | {s['net_usd']:+.0f} | "
            f"{t['net_2x']:+.0f} | {s['max_drawdown_usd']:.0f} | "
            f"{t['twin_avg']:+.2f} | {s['avg_per_trade']:+.2f} | {t['beats']:.1%} |",
            "",
            "Net $ by year: "
            + ", ".join(f"{y}: {v:+.0f}" for y, v in s["by_year"].items()),
        ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
