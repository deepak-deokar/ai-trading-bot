"""Support and resistance setups with an AI filter, Equiti costs.

Setups and levels: trading_bot.backtesting.sr_strategy.

Fixed before running:
* costs: config/xauusd_costs_equiti.yaml (cautious Equiti), 2x stress, $30 risk on
  $3,000; one trade at a time, at most 2 a day, out by 16:45 New York;
* 18 rule options: setups (bounce / retest / both) x target (1R / 1.5R / next
  level) x stop buffer (0.05 / 0.15 x ADR);
* choose the option on 2014-2022 only: it must make money on 2014-2020 and on
  2021-2022 with at least 100 trades over 2014-2022; among those the highest
  2014-2022 net (if none qualifies, the best 2021-2022 net is shown and the test
  counts as failed);
* AI filter for the chosen option: gradient-boosted trees (depth 2, 40+ trades per
  leaf, 150 rounds) on the setup's features, fitted on 2014-2020 setups, "would
  this trade win?"; the probability cut-off is chosen on 2021-2022 from none /
  0.40 / 0.45 / 0.50 / 0.55 / 0.60 (at least 30 trades), then the model is refitted
  on 2014-2022 and looked at once on 2023-2024;
* pass: on 2023-2024 profitable at Equiti costs and at 2x, at least 60 trades,
  largest drop below $600 (20%). The 50%-winners goal is reported separately.
2025-2026 never loaded.

Writes docs/xauusd-sr.{json,md} and docs/replays/xauusd-sr-2023-2024.html.
Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/study_xauusd_sr.py
"""

import itertools
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from study_xauusd_news_model import summary  # type: ignore[import-not-found]

from trading_bot.backtesting import sr_strategy as S
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, load_bars
from trading_bot.backtesting.sweep_strategy import TradingDay, build_days
from trading_bot.backtesting.trade_replay import (
    Highlight,
    ReplayContext,
    render_page,
    replay_record,
)
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_equiti.yaml")
OUT = Path("docs/xauusd-sr")
REPLAY = Path("docs/replays/xauusd-sr-2023-2024.html")
KINDS = {
    "bounce": frozenset({"bounce"}),
    "retest": frozenset({"retest"}),
    "both": frozenset({"bounce", "retest"}),
}
CUTS = (None, 0.40, 0.45, 0.50, 0.55, 0.60)
MIN_CHOICE_TRADES, MIN_CUT_TRADES, MIN_TEST_TRADES = 100, 30, 60
MAX_DD = 600.0
SEED = 7

Key = tuple[int, int, float]  # entry minute, direction, level


def key(c: S.Candidate) -> Key:
    return (c.setup.entry_minute, c.setup.direction, round(c.setup.level, 2))


def in_years(cands: Sequence[S.Candidate], y0: int, y1: int) -> list[S.Candidate]:
    return [c for c in cands if y0 <= c.setup.day.year <= y1]


def model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_depth=2,
        min_samples_leaf=40,
        max_iter=150,
        learning_rate=0.05,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=SEED,
    )


def fit_predict(
    train: Sequence[S.Candidate], score: Sequence[S.Candidate]
) -> dict[Key, float]:
    y = np.array([c.win for c in train], dtype=int)
    if len(train) < 50 or y.min() == y.max() or not score:
        return {}
    mdl = model().fit(S.feature_matrix(train), y)
    p = mdl.predict_proba(S.feature_matrix(score))[:, 1]
    return {key(c): float(q) for c, q in zip(score, p, strict=True)}


def keeper(
    probs: dict[Key, float], cut: float | None
) -> Callable[[S.Candidate], bool] | None:
    if cut is None:
        return None
    return lambda c: probs.get(key(c), 0.0) >= cut


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    bars = load_bars(BARS_DIR, 201401, 202412)
    days = build_days(bars)
    cands = S.candidates(bars, days, range(2014, 2025), costs)
    cands_2x = S.candidates(bars, days, range(2023, 2025), stress)
    print("candidates", {f"{k[0]}/{k[1]}": len(v) for k, v in cands.items()})

    # 1. rule options on 2014-2022
    options = []
    for (kname, kinds), (tname, buf) in itertools.product(KINDS.items(), cands):
        c = cands[(tname, buf)]
        early = summary(S.take(in_years(c, 2014, 2020), kinds=kinds))
        valid = summary(S.take(in_years(c, 2021, 2022), kinds=kinds))
        both = summary(S.take(in_years(c, 2014, 2022), kinds=kinds))
        options.append(
            {
                "setups": kname,
                "target": tname,
                "buffer": buf,
                "2014_2020": early,
                "2021_2022": valid,
                "2014_2022": both,
                "qualifies": bool(
                    early.get("net_usd", 0) > 0
                    and valid.get("net_usd", 0) > 0
                    and both.get("trades", 0) >= MIN_CHOICE_TRADES
                ),
            }
        )
    ok = [o for o in options if o["qualifies"]]
    if ok:
        chosen = max(ok, key=lambda o: o["2014_2022"]["net_usd"])
    else:
        chosen = max(options, key=lambda o: o["2021_2022"].get("net_usd", -1e9))
    kinds = KINDS[chosen["setups"]]
    ck = (chosen["target"], chosen["buffer"])
    c_all = [c for c in cands[ck] if c.setup.kind in kinds]
    print("chosen", chosen["setups"], ck, "qualifies", chosen["qualifies"])

    # 2. AI filter: fit 2014-2020, choose the cut-off on 2021-2022
    p_valid = fit_predict(in_years(c_all, 2014, 2020), in_years(c_all, 2021, 2022))
    cut_rows = []
    for cut in CUTS:
        tr = S.take(in_years(c_all, 2021, 2022), keep=keeper(p_valid, cut))
        cut_rows.append({"cut": cut, **summary(tr)})
    usable = [
        r for r in cut_rows if r.get("trades", 0) >= MIN_CUT_TRADES or r["cut"] is None
    ]
    best_cut = max(usable, key=lambda r: r.get("net_usd", -1e9))["cut"]
    print(
        "cut",
        best_cut,
        [(r["cut"], r.get("trades"), r.get("net_usd")) for r in cut_rows],
    )

    # 3. one look at 2023-2024
    test = in_years(c_all, 2023, 2024)
    test_2x = [c for c in cands_2x[ck] if c.setup.kind in kinds]
    p_test = fit_predict(in_years(c_all, 2014, 2022), test)
    keep = keeper(p_test, best_cut)
    ai = S.take(test, keep=keep)
    ai_2x = S.take(test_2x, keep=keep)
    rules = S.take(test)
    rules_2x = S.take(test_2x)
    sa, s2 = summary(ai), summary(ai_2x)
    passed = bool(
        sa.get("trades", 0) >= MIN_TEST_TRADES
        and sa["net_usd"] > 0
        and s2.get("net_usd", 0) > 0
        and sa["max_drawdown_usd"] < MAX_DD
    )
    report: dict[str, Any] = {
        "costs": COSTS_YAML.stem,
        "options": options,
        "chosen": {k: chosen[k] for k in ("setups", "target", "buffer", "qualifies")},
        "ai_cutoffs_2021_2022": cut_rows,
        "ai_cutoff": best_cut,
        "test_2023_2024": {
            "with_ai": sa,
            "with_ai_2x": s2,
            "rules_only": summary(rules),
            "rules_only_2x": summary(rules_2x),
        },
        "passed": passed,
        "fifty_percent_winners": bool(sa.get("win_rate", 0) >= 0.5),
        "2025_2026": "not loaded",
    }
    print(
        "test ai",
        sa.get("trades"),
        sa.get("win_rate"),
        sa.get("net_usd"),
        "2x",
        s2.get("net_usd"),
        "rules",
        summary(rules).get("net_usd"),
        "passed",
        passed,
        flush=True,
    )
    OUT.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(report))
    write_replay(bars, days, test, keep, ai, chosen, best_cut, costs)
    print("wrote", OUT, REPLAY)


def fmt(v: dict[str, Any]) -> str:
    if not v.get("trades"):
        return "0 | | | |"
    return (
        f"{v['trades']} | {v['win_rate']:.0%} | {v['avg_per_trade']:.2f} | "
        f"{v['net_usd']:,.0f} | {v['max_drawdown_usd']:,.0f}"
    )


def render_md(r: dict[str, Any]) -> str:
    c = r["chosen"]
    L = [
        "# Support and resistance with an AI filter (Equiti costs)",
        "",
        "Levels: yesterday's and last week's high/low, hourly swing levels with 2+ "
        "turns, $50 round numbers, the Asian range. Setups on 15-minute candles "
        "closing 03:00-13:00 New York: bounce off a level, or break and retest. Stop "
        "beyond the zone and wick plus a buffer ($5-$30), target 1R / 1.5R / next "
        "level, only with room to the next major level. One trade at a time, max 2 a "
        f"day, out by 16:45. Costs: {r['costs']}, $30 risk on $3,000. Option chosen on "
        "2014-2022; AI fitted on 2014-2020, cut-off chosen on 2021-2022; one look at "
        "2023-2024. 2025-2026 not loaded.",
        "",
        "## Rule options (2014-2022 only)",
        "",
        "| Setups | Target | Stop buffer | 2014-20 trades | Win % | Net $ | 2021-22 "
        "trades | Win % | Net $ | Qualifies |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for o in sorted(r["options"], key=lambda o: -o["2014_2022"].get("net_usd", -1e9)):
        a, b = o["2014_2020"], o["2021_2022"]
        L.append(
            f"| {o['setups']} | {o['target']} | {o['buffer']:g} x ADR | "
            f"{a.get('trades', 0)} | {a.get('win_rate', 0):.0%} | "
            f"{a.get('net_usd', 0):,.0f} | {b.get('trades', 0)} | "
            f"{b.get('win_rate', 0):.0%} | {b.get('net_usd', 0):,.0f} | "
            f"{'yes' if o['qualifies'] else 'no'} |"
        )
    L += [
        "",
        f"Chosen: **{c['setups']}, target {c['target']}, stop buffer {c['buffer']:g} x "
        f"ADR** (qualified: {'yes' if c['qualifies'] else 'no - none did'}).",
        "",
        "## AI cut-off (2021-2022)",
        "",
        "| Cut-off | Trades | Win % | Net $/trade | Net $ | Max drop $ |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in r["ai_cutoffs_2021_2022"]:
        name = "no filter" if row["cut"] is None else f">= {row['cut']:.2f}"
        L.append(f"| {name} | {fmt(row)} |")
    cut = r["ai_cutoff"]
    t = r["test_2023_2024"]
    L += [
        "",
        f"Chosen cut-off: **{'no filter' if cut is None else f'>= {cut:.2f}'}**.",
        "",
        "## 2023-2024 (one look)",
        "",
        "| | Trades | Win % | Net $/trade | Net $ | Max drop $ |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        f"| With AI filter | {fmt(t['with_ai'])} |",
        f"| With AI filter, 2x costs | {fmt(t['with_ai_2x'])} |",
        f"| Rules only | {fmt(t['rules_only'])} |",
        f"| Rules only, 2x costs | {fmt(t['rules_only_2x'])} |",
        "",
        f"Passed: **{'yes' if r['passed'] else 'no'}** (profitable at 1x and 2x, "
        f">= {MIN_TEST_TRADES} trades, max drop < ${MAX_DD:,.0f}). "
        f"50% winners: **{'yes' if r['fifty_percent_winners'] else 'no'}**.",
        "",
        "Replays: `docs/replays/xauusd-sr-2023-2024.html`.",
        "",
    ]
    return "\n".join(L)


def write_replay(
    bars: dict[str, Array],
    days: list[TradingDay],
    test: list[S.Candidate],
    keep: Callable[[S.Candidate], bool] | None,
    trades: list[HoldTrade],
    chosen: dict[str, Any],
    cut: float | None,
    costs: CostModel,
) -> None:
    mid = S.Mids.of(bars)
    index = {d.day: n for n, d in enumerate(days)}
    by_trade = {id(c.trade): c for c in test}
    nbar = len(bars["minute_utc"])
    records = []
    for t in trades:
        c = by_trade[id(t)]
        s = c.setup
        k = index[s.day]
        lv = S.merge_levels(S.day_levels(bars, mid, days, k, s.adr), S.ZONE * s.adr)
        lo_p, hi_p = t.entry - 3 * s.adr, t.entry + 3 * s.adr
        levels = tuple(
            (x.price, "/".join(sorted(x.kinds)).replace("_", " "))
            for x in lv
            if lo_p <= x.price <= hi_p
        )
        side = "support" if s.direction == 1 else "resistance"
        what = (
            f"bounced off {side}"
            if s.kind == "bounce"
            else f"came back to a broken level, now {side}"
        )
        ctx = ReplayContext(
            zone=(s.level - S.ZONE * s.adr, s.level + S.ZONE * s.adr),
            zone_label=f"Level {s.level:.2f} ({', '.join(sorted(s.level_kinds))})",
            levels=levels,
            highlights=(
                Highlight(
                    s.candle_close_minute - 14,
                    s.candle_close_minute,
                    s.kind.upper(),
                    f"This 15-minute candle {what} and closed back away from the "
                    "zone; enter at the next minute.",
                ),
            ),
        )
        records.append(
            replay_record(
                bars,
                t,
                costs,
                exit_at_close=t.exit_reason == "time_exit",
                window=(max(0, t.entry_minute - 240), min(nbar, t.exit_bar + 60)),
                context=ctx,
            )
        )
    cut_txt = "no AI filter" if cut is None else f"AI probability >= {cut:.2f}"
    html = render_page(
        title="Support & Resistance 2023-2024",
        subtitle=(
            f"{chosen['setups']} setups, target {chosen['target']}, stop buffer "
            f"{chosen['buffer']:g} x ADR, {cut_txt}; {len(trades)} trades. Rules "
            "chosen on 2014-2022 only. 5-minute mid-price candles, New York time; "
            f"$3,000 account, $30 risk, costs: {costs_name()}."
        ),
        rules=[
            "Levels: yesterday's and last week's high and low, hourly swing levels "
            "with 2+ turns, $50 round numbers, the Asian range.",
            "Bounce: a 15-minute candle dips into a level's zone and closes back "
            "out of it near its far end. Retest: price breaks a level, comes back "
            "to it within 2 hours and holds.",
            "Stop beyond the zone and the wick plus a buffer; trade only if the next "
            "major level leaves room for the target.",
            "One trade at a time, at most 2 a day, out by 16:45 New York.",
        ],
        records=records,
        all_trades=trades,
        note="Account starts at $3,000.",
    )
    REPLAY.write_text(html)


def costs_name() -> str:
    return COSTS_YAML.stem


if __name__ == "__main__":
    main()
