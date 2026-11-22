"""Support and resistance round 2: each level type alone, ADR-scaled, against two
random-entry baselines, plus raw after-touch behaviour. Rules fixed beforehand in
docs/xauusd-sr-v2-plan.md (with amendments 1 and 2).

* Equiti cautious costs (config/xauusd_costs_equiti.yaml), $30 risk on $3,000.
* 30 combinations: 5 level types x bounce / retest / breakout x 1R / 1.5R
  ("all levels together" shown for reference, never chosen).
* Baselines, 1,000 runs each: after-signal twins (same day, random later
  15-minute mark) and hour-matched twins (same clock time, random other day of the
  same year, stop in the same ADR units).
* Development 2014-2022, every setup counted (no daily cap). Pass: beats >= 99% of
  hour-matched runs and >= 95% of after-signal runs, money made on 2014-2020 (also
  at 2x costs) and on 2021-2022, >= 200 trades.
* Only if something passes: one look at 2023-2024 with one trade at a time, at most
  2 a day; profitable at 1x and 2x costs, >= 60 trades, largest drop < $600, beats
  the same baseline thresholds.
2025-2026 never loaded.

Writes docs/xauusd-sr-compare.{json,md}.
Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/study_xauusd_sr_compare.py
(SR_RUNS=20 for a quick check).
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

from trading_bot.backtesting import sr_compare as C
from trading_bot.backtesting.news_day import NY
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, load_bars
from trading_bot.backtesting.sr_strategy import (
    ADR_DAYS,
    ASIA_END,
    FIRST_CLOSE,
    LAST_CLOSE,
    ZONE,
    Level,
    Mids,
    _candles15,
    _ny_epoch,
    adr_at,
)
from trading_bot.backtesting.sweep_strategy import TradingDay, build_days
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_equiti.yaml")
OUT = Path("docs/xauusd-sr-compare")
RUNS = int(os.environ.get("SR_RUNS", "1000"))
SEED = 11
BEAT_HOUR, BEAT_AFTER = 0.99, 0.95
CHANCE = 0.05 * 30  # combinations expected over the 95th percentile by luck
MIN_DEV_TRADES, MIN_TEST_TRADES = 200, 60
MAX_DD = 600.0
WORKERS = 8
FAKE_SHIFT = (0.3, 0.7)  # x ADR

Combo = tuple[str, str, float]  # level type, setup, target R
Item = tuple[int, C.Result]  # day index, result
Avgs = dict[Combo, tuple[list[float], list[float]]]  # after, hour


@dataclass
class World:
    bars: dict[str, Array]
    days: list[TradingDay]
    mid: Mids
    costs: CostModel
    marks: dict[int, Array]
    adrs: dict[int, float]
    year_days: dict[int, list[int]]


W: World | None = None  # set before forking workers


def collect(w: World, years: range, costs: CostModel) -> dict[Combo, list[Item]]:
    out: dict[Combo, list[Item]] = defaultdict(list)
    for k, d in enumerate(w.days):
        if d.day.year not in years or k not in w.adrs:
            continue
        for s in C.find_signals(w.bars, w.days, k, w.mid):
            for tr in C.TARGETS:
                r = C.simulate(w.bars, w.mid, d, s, tr, costs)
                if r is not None:
                    out[(s.ltype, s.kind, tr)].append((k, r))
    return out


def clock_of(w: World, minute: int) -> time:
    return datetime.fromtimestamp(int(w.bars["minute_utc"][minute]), NY).time()


def after_twins(
    w: World, items: Sequence[Item], rng: np.random.Generator
) -> list[C.Result]:
    out = []
    for k, r in items:
        # only marks after the real entry: the twin knows the direction, so an
        # earlier entry would trade the move that created the signal
        mk = w.marks[k][w.marks[k] > r.signal.entry_minute]
        if len(mk) == 0:
            continue
        e = int(mk[rng.integers(len(mk))])
        t = C.twin(w.bars, w.mid, w.days[k], r, e, w.costs)
        if t is not None:
            sig = replace(r.signal, entry_minute=e)
            out.append(C.Result(sig, r.target_r, r.risk_mid, t))
    return out


def hour_twins(
    w: World,
    items: Sequence[Item],
    clocks: Sequence[time],
    rng: np.random.Generator,
) -> list[C.Result]:
    out = []
    for (k, r), clock in zip(items, clocks, strict=True):
        pool = w.year_days[w.days[k].day.year]
        k2 = pool[int(rng.integers(len(pool)))]
        if k2 == k:
            continue
        got = C.hour_twin(w.bars, w.mid, w.days[k2], w.adrs[k2], r, clock, w.costs)
        if got is None:
            continue
        e, t = got
        sig = replace(r.signal, entry_minute=e, day=w.days[k2].day)
        out.append(C.Result(sig, r.target_r, r.risk_mid, t))
    return out


def avg(trades: Sequence[HoldTrade]) -> float:
    return float(np.mean([t.pnl_usd for t in trades])) if trades else 0.0


def _runs(
    args: tuple[list[int], dict[Combo, list[Item]], dict[Combo, list[time]], bool],
) -> Avgs:
    runs, res, clocks, capped = args
    assert W is not None
    out: Avgs = {c: ([], []) for c in res}
    for run in runs:
        rng = np.random.default_rng([SEED, run])
        for c, items in res.items():
            a = after_twins(W, items, rng)
            h = hour_twins(W, items, clocks[c], rng)
            if capped:
                out[c][0].append(avg(C.take(a)))
                out[c][1].append(avg(C.take(h)))
            else:
                out[c][0].append(avg([x.trade for x in a]))
                out[c][1].append(avg([x.trade for x in h]))
    return out


def twin_avgs(res: dict[Combo, list[Item]], capped: bool) -> Avgs:
    assert W is not None
    w = W
    clocks = {
        c: [clock_of(w, r.signal.entry_minute) for _, r in v] for c, v in res.items()
    }
    chunks = [list(range(i, RUNS, WORKERS)) for i in range(WORKERS)]
    with mp.get_context("fork").Pool(WORKERS) as pool:
        parts = pool.map(_runs, [(ch, res, clocks, capped) for ch in chunks])
    out: Avgs = {c: ([], []) for c in res}
    for p in parts:
        for c, (a, h) in p.items():
            out[c][0].extend(a)
            out[c][1].extend(h)
    return out


def baseline(real: float, twin: Sequence[float]) -> dict[str, float]:
    a = np.array(twin)
    return {
        "avg": round(float(a.mean()), 2),
        "p95": round(float(np.percentile(a, 95)), 2),
        "p99": round(float(np.percentile(a, 99)), 2),
        "beats": round(float((a < real).mean()), 4),
    }


def years_of(items: Sequence[Item], y0: int, y1: int) -> list[Item]:
    return [x for x in items if y0 <= x[1].signal.day.year <= y1]


def day_levels_by_type(w: World, k: int, adr: float) -> dict[str, list[float]]:
    d = w.days[k]
    lv = C.type_levels(w.bars, w.mid, w.days, k, adr)
    a1 = int(np.searchsorted(w.bars["minute_utc"], _ny_epoch(d.day, ASIA_END)))
    lv["asia"] = []
    if a1 > d.i0:
        lv["asia"] = [
            Level(float(w.mid.h[d.i0 : a1].max())),
            Level(float(w.mid.lo[d.i0 : a1].min())),
        ]
    out = {t: [x.price for x in lv[t]] for t in C.TYPES}
    out["all"] = sorted({round(p, 2) for t in C.TYPES for p in out[t]})
    return out


def zone_share(w: World, years: range) -> dict[str, float]:
    """Share of 15-minute candles closing 03:00-13:00 that touch a level's zone."""
    hit: dict[str, int] = defaultdict(int)
    total = 0
    m = w.bars["minute_utc"]
    for k, d in enumerate(w.days):
        if d.day.year not in years or k not in w.adrs:
            continue
        adr = w.adrs[k]
        lv = day_levels_by_type(w, k, adr)
        starts, ends = _candles15(m, d.i0, d.i1)
        ct = (m[starts] // 900 + 1) * 900
        t0, t1 = _ny_epoch(d.day, FIRST_CLOSE), _ny_epoch(d.day, LAST_CLOSE)
        z = ZONE * adr
        for a, b, t in zip(starts, ends, ct, strict=True):
            if not (t0 <= t <= t1):
                continue
            total += 1
            h, lo = w.mid.h[a:b].max(), w.mid.lo[a:b].min()
            for name, levels in lv.items():
                if any(lo <= x + z and h >= x - z for x in levels):
                    hit[name] += 1
    return {n: round(hit[n] / total, 3) for n in (*C.TYPES, "all")}


def touches(w: World, years: range) -> dict[str, dict[str, Any]]:
    """After-touch behaviour per level type, real levels vs fake (shifted) ones."""
    rng = np.random.default_rng(SEED + 7)
    m = w.bars["minute_utc"]
    rows: dict[tuple[str, bool], list[C.Touch]] = defaultdict(list)
    for k, d in enumerate(w.days):
        if d.day.year not in years or k not in w.adrs:
            continue
        adr = w.adrs[k]
        start = int(np.searchsorted(m, _ny_epoch(d.day, FIRST_CLOSE)))
        if start >= d.i1:
            continue
        for lt, prices in day_levels_by_type(w, k, adr).items():
            fake = [
                p + float(rng.choice([-1, 1])) * float(rng.uniform(*FAKE_SHIFT)) * adr
                for p in prices
            ]
            for is_fake, lv in ((False, prices), (True, fake)):
                rows[(lt, is_fake)] += C.touch_events(
                    w.bars, w.mid, d, lv, adr, lt, is_fake, start
                )
    out: dict[str, dict[str, Any]] = {}
    for lt in (*C.TYPES, "all"):
        out[lt] = {}
        for is_fake in (False, True):
            ev = rows[(lt, is_fake)]
            mv = np.array([e.move_60 for e in ev])
            n = len(ev)
            out[lt]["fake" if is_fake else "real"] = {
                "touches": n,
                "held": round(sum(e.outcome == "held" for e in ev) / n, 3),
                "broke": round(sum(e.outcome == "broke" for e in ev) / n, 3),
                "neither": round(sum(e.outcome == "neither" for e in ev) / n, 3),
                "move_60_mean": round(float(mv.mean()), 3),
                "move_60_median": round(float(np.median(mv)), 3),
                "move_60_se": round(float(mv.std() / np.sqrt(n)), 3),
            }
    return out


def main() -> None:
    global W
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    bars = load_bars(BARS_DIR, 201401, 202412)
    days = build_days(bars)
    mid = Mids.of(bars)
    adrs: dict[int, float] = {}
    year_days: dict[int, list[int]] = defaultdict(list)
    marks: dict[int, Array] = {}
    for k, d in enumerate(days):
        a = adr_at(days, k)
        if k < ADR_DAYS or not a:
            continue
        adrs[k] = a
        year_days[d.day.year].append(k)
        marks[k] = C.entry_marks(bars, d)
    W = World(bars, days, mid, costs, marks, adrs, dict(year_days))
    dev_years = range(2014, 2023)

    tch = touches(W, dev_years)
    for lt, v in tch.items():
        print("touch", lt, v, flush=True)
    share = zone_share(W, dev_years)
    print("zone share", share, flush=True)

    res = collect(W, dev_years, costs)
    res_2x = collect(W, range(2014, 2021), stress)
    combos = sorted(res)
    tw = twin_avgs({c: res[c] for c in combos}, capped=False)

    rows = []
    for c in combos:
        items = res[c]
        all_t = [r.trade for _, r in items]
        real = avg(all_t)
        early = summary([r.trade for _, r in years_of(items, 2014, 2020)])
        early_2x = summary([r.trade for _, r in res_2x.get(c, [])])
        late = summary([r.trade for _, r in years_of(items, 2021, 2022)])
        ba, bh = baseline(real, tw[c][0]), baseline(real, tw[c][1])
        s = summary(all_t)
        row: dict[str, Any] = {
            "level_type": c[0],
            "setup": c[1],
            "target_r": c[2],
            "trades": s.get("trades", 0),
            "win_rate": s.get("win_rate"),
            "avg_per_trade": s.get("avg_per_trade"),
            "net_2014_2020": early.get("net_usd", 0.0),
            "net_2014_2020_2x": early_2x.get("net_usd", 0.0),
            "net_2021_2022": late.get("net_usd", 0.0),
            "net_2014_2022": s.get("net_usd", 0.0),
            "after_twins": ba,
            "hour_twins": bh,
        }
        row["passes"] = bool(
            c[0] != "all"
            and bh["beats"] >= BEAT_HOUR
            and ba["beats"] >= BEAT_AFTER
            and row["net_2014_2020"] > 0
            and row["net_2014_2020_2x"] > 0
            and row["net_2021_2022"] > 0
            and row["trades"] >= MIN_DEV_TRADES
        )
        rows.append(row)
        print(
            f"{c[0]:9s} {c[1]:8s} {c[2]}R n={row['trades']:5d} "
            f"win={row['win_rate']} avg={row['avg_per_trade']} "
            f"after={ba['avg']}/{ba['beats']} hour={bh['avg']}/{bh['beats']} "
            f"pass={row['passes']}",
            flush=True,
        )

    eligible = [r for r in rows if r["level_type"] != "all"]
    over95 = {
        "after_twins": sum(r["after_twins"]["beats"] >= 0.95 for r in eligible),
        "hour_twins": sum(r["hour_twins"]["beats"] >= 0.95 for r in eligible),
        "both": sum(
            r["after_twins"]["beats"] >= 0.95 and r["hour_twins"]["beats"] >= 0.95
            for r in eligible
        ),
        "expected_by_luck": CHANCE,
    }
    print("over 95th", over95)
    passed = [r for r in rows if r["passes"]]
    test: dict[str, Any] | None = None
    if passed:
        ch = max(passed, key=lambda r: (r["hour_twins"]["beats"], r["avg_per_trade"]))
        combo = (ch["level_type"], ch["setup"], ch["target_r"])
        test = run_test(W, combo, stress)
        test["combo"] = list(combo)
        print("test", test)

    result = {
        "costs": COSTS_YAML.stem,
        "plan": "docs/xauusd-sr-v2-plan.md",
        "twin_runs": RUNS,
        "zone_share": share,
        "touches": tch,
        "over_95th": over95,
        "rows": rows,
        "passed_development": [
            [r["level_type"], r["setup"], r["target_r"]] for r in passed
        ],
        "test_2023_2024": test,
    }
    OUT.with_suffix(".json").write_text(json.dumps(result, indent=2, default=str))
    OUT.with_suffix(".md").write_text(render_md(result))
    print("wrote", OUT)


def run_test(w: World, combo: Combo, stress: CostModel) -> dict[str, Any]:
    years = range(2023, 2025)
    items = collect(w, years, w.costs)[combo]
    items_2x = collect(w, years, stress)[combo]
    real = C.take([r for _, r in items])
    real_2x = C.take([r for _, r in items_2x])
    tw = twin_avgs({combo: items}, capped=True)[combo]
    s, s2 = summary(real), summary(real_2x)
    ba, bh = baseline(avg(real), tw[0]), baseline(avg(real), tw[1])
    passed = bool(
        s.get("trades", 0) >= MIN_TEST_TRADES
        and s.get("net_usd", 0) > 0
        and s2.get("net_usd", 0) > 0
        and s.get("max_drawdown_usd", 1e9) < MAX_DD
        and bh["beats"] >= BEAT_HOUR
        and ba["beats"] >= BEAT_AFTER
    )
    return {
        "summary": s,
        "summary_2x": s2,
        "after_twins": ba,
        "hour_twins": bh,
        "passed": passed,
    }


def money(v: float | None) -> str:
    if v is None:
        return "-"
    return f"-${-v:,.0f}" if v < 0 else f"+${v:,.0f}"


def pct(v: float) -> str:
    return f"{v:.1%}"


def render_md(r: dict[str, Any]) -> str:
    n = r["twin_runs"]
    lines = [
        "# XAUUSD support and resistance, round 2: each level against random entries",
        "",
        f"Rules fixed before running: [{r['plan']}](xauusd-sr-v2-plan.md) (with "
        f"amendments 1 and 2). Costs: {r['costs']}. $30 risk per trade. Development "
        "years 2014-2022, every setup counted on its own (no daily cap).",
        "",
        "## 1. What price does after touching a level (no stops, no targets)",
        "",
        "First touch of each level per day, 03:00-13:00 New York, price arriving "
        "from outside the zone. **Held** = within 60 minutes price first went 0.25 "
        "ADR beyond the zone back on the side it came from; **broke** = it went 0.25 "
        "ADR through to the other side first. **Move** = where price was 60 minutes "
        "later, in ADR units, positive = back on the approach side. **Fake** levels "
        "are the same levels moved 0.3-0.7 ADR up or down at random: the level's "
        "own effect is the gap between real and fake.",
        "",
        "| Level | Touches | Held | Broke | Neither | Move (mean ± se) | Fake held "
        "| Fake broke | Fake move |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for lt, v in r["touches"].items():
        a, f = v["real"], v["fake"]
        lines.append(
            f"| {lt} | {a['touches']} | {a['held']:.0%} | {a['broke']:.0%} "
            f"| {a['neither']:.0%} | {a['move_60_mean']:+.3f} ± {a['move_60_se']:.3f} "
            f"| {f['held']:.0%} | {f['broke']:.0%} | {f['move_60_mean']:+.3f} |"
        )
    lines += [
        "",
        "## 2. Setups against random entries",
        "",
        f"Two baselines, {n:,} runs each. **After** twin: the same trade (direction, "
        "stop distance, target) entered at a random later 15-minute mark on the same "
        "day. **Hour** twin: the same trade at the same clock time on a random other "
        "day of the same year, stop in the same ADR units. **Beats** = share of runs "
        "the real setup's average $ per trade beat. Passing needs hour >= 99%, after "
        ">= 95%, money in 2014-20 (also at 2x costs) and 2021-22, 200+ trades.",
        "",
        "| Level | Setup | Target | Trades | Win | $/trade | After avg | Beats "
        "| Hour avg | Beats | 2014-20 | 2014-20 2x | 2021-22 | Pass |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for x in sorted(
        r["rows"],
        key=lambda x: (x["level_type"] == "all", -x["hour_twins"]["beats"]),
    ):
        a, h = x["after_twins"], x["hour_twins"]
        lines.append(
            f"| {x['level_type']} | {x['setup']} | {x['target_r']}R | {x['trades']} "
            f"| {x['win_rate']:.0%} | {x['avg_per_trade']:+.2f} "
            f"| {a['avg']:+.2f} | {pct(a['beats'])} | {h['avg']:+.2f} "
            f"| {pct(h['beats'])} | {money(x['net_2014_2020'])} "
            f"| {money(x['net_2014_2020_2x'])} | {money(x['net_2021_2022'])} "
            f"| {'yes' if x['passes'] else 'no'} |"
        )
    o = r["over_95th"]
    lines += [
        "",
        f"Of the 30 eligible combinations, **{o['after_twins']}** beat the 95th "
        f"percentile of after-signal twins, **{o['hour_twins']}** of hour-matched "
        f"twins and **{o['both']}** both; about {o['expected_by_luck']:.1f} would by "
        "luck alone (more, in clusters, because the combinations share levels).",
        "",
        "## 3. How often price sits at a level",
        "",
        "Share of 15-minute candles (03:00-13:00, 2014-2022) that touch a level's "
        "zone:",
        "",
        "| Level type | Share |",
        "|---|---:|",
    ]
    for k, v in r["zone_share"].items():
        lines.append(f"| {k} | {v:.0%} |")
    lines += [
        "",
        "## 4. Spreads in the data",
        "",
        "The recorded spread is almost constant in 2014-2018 ($0.51 in 2014, $0.35 "
        "in 2015-2018, little widening at news), so costs in those years are likely "
        "too low. 2014-2020 must also be profitable at 2x costs to pass.",
        "",
        "## 5. 2023-2024 test",
        "",
    ]
    t = r["test_2023_2024"]
    if t is None:
        lines.append(
            "Nothing passed development, so 2023-2024 was not looked at (as planned)."
        )
    else:
        s, s2 = t["summary"], t["summary_2x"]
        lines += [
            f"Combination: {' / '.join(map(str, t['combo']))}, one trade at a time, "
            "at most 2 a day.",
            "",
            f"* {s.get('trades', 0)} trades, {s.get('win_rate', 0):.0%} winners, "
            f"net {money(s.get('net_usd'))}, at 2x costs {money(s2.get('net_usd'))}, "
            f"largest drop ${s.get('max_drawdown_usd', 0):,.0f}",
            f"* beats {pct(t['after_twins']['beats'])} of after-signal twins and "
            f"{pct(t['hour_twins']['beats'])} of hour-matched twins",
            f"* **passed: {'yes' if t['passed'] else 'no'}**",
        ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
