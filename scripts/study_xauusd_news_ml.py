"""Gold with global news sentiment: gradient-boosted trees, train 2015-2022,
test 2023-2024.

Same daily trade as trading_bot.backtesting.daily_model: every trading day at
08:00 New York, buy or sell 1:1 (stop = target = half the 20-day average daily
range, normal stops), closed at 12:00. Inputs: the 21 daily-model inputs (gold,
US dollar, yields, S&P 500, VIX, US news calendar) plus 71 global-news inputs
from GDELT (trading_bot.backtesting.news_features): share, surge, tone and tone
change for gold, central banks, gold + central banks, inflation, dollar/FX, stock
markets, war, terror, sanctions, elections/government, policy uncertainty, oil,
debt crises, AI/tech, bubbles/speculation, funds/investors, crypto, and all news.

Fixed before running (no tuning on the test years):
* train on 2015-03 .. 2022-12, test once on 2023-01 .. 2024-12;
* models: gradient-boosted trees (max depth 3, 300 rounds, learning rate 0.03,
  at least 60 days per leaf, L2 1.0) with and without the news inputs, and the
  L2 logistic regression with news inputs;
* trade if P(buy wins) >= 0.55 (buy) or <= 0.45 (sell), else skip;
* pass: profitable after expensive costs in 2023-2024, at least 50% winning
  trades, better than the best simple rule. 2025 and 2026 are never loaded.

Writes docs/xauusd-news-ml.{json,md} and a 2023-2024 replay page.
Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/study_xauusd_news_ml.py
"""

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from study_xauusd_news_model import fmt, summary  # type: ignore[import-not-found]

from trading_bot.backtesting.daily_model import FEATURES as BASE_FEATURES
from trading_bot.backtesting.daily_model import DayRow, build_rows, trade_row
from trading_bot.backtesting.levels import key_levels
from trading_bot.backtesting.news_day import load_events
from trading_bot.backtesting.news_features import NewsHours, news_feature_names
from trading_bot.backtesting.news_model import fit_logistic
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import (
    Array,
    CostModel,
    Sizing,
    load_bars,
)
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.backtesting.trade_replay import (
    ReplayContext,
    render_page,
    replay_record,
)
from trading_bot.data.gdelt_news import load_hourly
from trading_bot.data.histdata_bulk import BARS_DIR
from trading_bot.data.macro_daily import load as load_macro

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-news-ml")
REPLAY = Path("docs/replays/xauusd-news-ml-2023-2024.html")
FIRST_DAY = date(2015, 3, 2)  # GDELT starts 2015-02-18; 8 days of news history
TRAIN_LAST_YEAR = 2022
TEST_YEARS = (2023, 2024)
MARGIN = 0.05
SEED = 7


def gbm() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_depth=3,
        learning_rate=0.03,
        max_iter=300,
        min_samples_leaf=60,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=SEED,
    )


def choose_from(p: Array) -> list[int]:
    return [1 if q >= 0.5 + MARGIN else -1 if q <= 0.5 - MARGIN else 0 for q in p]


def trades_for(
    bars: dict[str, Array], rows: list[DayRow], dirs: list[int], costs: CostModel
) -> list[HoldTrade]:
    out = []
    for r, d in zip(rows, dirs, strict=True):
        if d:
            t = trade_row(bars, r, d, costs, Sizing())
            if t is not None:
                out.append(t)
    return out


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    bars = load_bars(BARS_DIR, 201501, 202412)
    days = build_days(bars)
    rows_all = build_rows(
        bars, days, load_macro(), load_events(one_per_day=False), range(2015, 2025)
    )
    news = NewsHours.from_columns(*load_hourly())
    m = bars["minute_utc"]
    rows, xnews = [], []
    for r in rows_all:
        if r.day < FIRST_DAY:
            continue
        f = news.features_at(int(m[r.entry_minute]))
        if f is None:
            continue
        rows.append(r)
        xnews.append(f)
    xb = np.array([r.features for r in rows])
    xn = np.array(xnews)
    x_all = np.hstack([xb, xn])
    y = np.array([r.label for r in rows])
    yr = np.array([r.year for r in rows])
    train, test = yr <= TRAIN_LAST_YEAR, np.isin(yr, TEST_YEARS)
    names_all = list(BASE_FEATURES) + news_feature_names()
    test_rows = [r for r, t in zip(rows, test, strict=True) if t]

    models: dict[str, tuple[Array, Array]] = {}  # name -> (train p, test p)
    g_news = gbm().fit(x_all[train], y[train])
    models["trees, with global news"] = (
        g_news.predict_proba(x_all[train])[:, 1],
        g_news.predict_proba(x_all[test])[:, 1],
    )
    g_base = gbm().fit(xb[train], y[train])
    models["trees, without news"] = (
        g_base.predict_proba(xb[train])[:, 1],
        g_base.predict_proba(xb[test])[:, 1],
    )
    lin = fit_logistic(x_all[train], y[train].astype(float), l2=1.0)
    models["linear, with global news"] = (
        lin.proba(x_all[train]),
        lin.proba(x_all[test]),
    )

    fi = {f: j for j, f in enumerate(BASE_FEATURES)}

    def sign(v: float) -> int:
        return 1 if v > 0 else -1 if v < 0 else 0

    simple: dict[str, Callable[[DayRow], int]] = {
        "simple: always buy": lambda r: 1,
        "simple: follow the overnight move": lambda r: sign(
            r.features[fi["overnight_move"]]
        ),
        "simple: against the overnight move": lambda r: -sign(
            r.features[fi["overnight_move"]]
        ),
        "simple: follow the 20-day trend": lambda r: sign(r.features[fi["trend_20d"]]),
    }
    results: dict[str, Any] = {}
    accuracy: dict[str, Any] = {}
    yt = y[test]
    for name, (ptr, pte) in models.items():
        dirs = choose_from(pte)
        results[name] = summary(trades_for(bars, test_rows, dirs, costs))
        results[name]["net_usd_at_2x"] = round(
            sum(t.pnl_usd for t in trades_for(bars, test_rows, dirs, stress)), 2
        )
        sure = np.abs(pte - 0.5) >= MARGIN
        accuracy[name] = {
            "train": round(float(np.mean((ptr > 0.5) == (y[train] == 1))), 3),
            "test": round(float(np.mean((pte > 0.5) == (yt == 1))), 3),
            "test_when_confident": (
                round(float(np.mean(((pte > 0.5) == (yt == 1))[sure])), 3)
                if sure.any()
                else None
            ),
        }
        print(
            name,
            accuracy[name],
            results[name]["trades"],
            results[name]["win_rate"],
            results[name]["net_usd"],
            flush=True,
        )
    for name, rule in simple.items():
        results[name] = summary(
            trades_for(bars, test_rows, [rule(r) for r in test_rows], costs)
        )
        print(
            name,
            results[name]["trades"],
            results[name]["win_rate"],
            results[name]["net_usd"],
            flush=True,
        )

    imp = permutation_importance(
        g_news, x_all[test], yt, n_repeats=10, random_state=SEED, scoring="accuracy"
    )
    top = sorted(
        zip(names_all, imp.importances_mean, imp.importances_std, strict=True),
        key=lambda z: -z[1],
    )[:15]
    main_name = "trees, with global news"
    main_res = results[main_name]
    best_simple = max(
        v["net_usd"] for k, v in results.items() if k.startswith("simple")
    )
    passed = (
        main_res["trades"] > 0
        and main_res["net_usd"] > 0
        and main_res["win_rate"] >= 0.5
        and main_res["net_usd"] > best_simple
    )
    payload = {
        "design": "see this script's docstring",
        "train": [FIRST_DAY.isoformat(), f"{TRAIN_LAST_YEAR}-12-31"],
        "test": [f"{TEST_YEARS[0]}-01-01", f"{TEST_YEARS[-1]}-12-31"],
        "train_days": int(train.sum()),
        "test_days": int(test.sum()),
        "inputs": len(names_all),
        "share_buy_wins_test": round(float(yt.mean()), 3),
        "accuracy": accuracy,
        "results": results,
        "test_importance_top15": [
            {"input": n, "accuracy_drop": round(float(a), 4), "std": round(float(s), 4)}
            for n, a, s in top
        ],
        "passed": passed,
        "2025_2026": "not loaded",
    }
    OUT.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(payload))
    print("passed", passed)
    write_replay(
        bars,
        days,
        test_rows,
        choose_from(models[main_name][1]),
        models[main_name][1],
        costs,
    )
    print("wrote", OUT, REPLAY)


def write_replay(
    bars: dict[str, Array],
    days: list[Any],
    rows: list[DayRow],
    dirs: list[int],
    probs: Array,
    costs: CostModel,
) -> None:
    index = {d.day: k for k, d in enumerate(days)}
    n = len(bars["minute_utc"])
    records, trades = [], []
    for r, d, _p in zip(rows, dirs, probs, strict=True):
        if not d:
            continue
        t = trade_row(bars, r, d, costs, Sizing())
        if t is None:
            continue
        trades.append(t)
        lv = tuple(
            (x.price, x.name)
            for x in key_levels(bars, days, index[r.day], r.entry_minute)
        )
        records.append(
            replay_record(
                bars,
                t,
                costs,
                exit_at_close=t.exit_reason == "time_exit",
                window=(max(0, r.entry_minute - 120), min(n, t.exit_bar + 30)),
                context=ReplayContext(levels=lv),
            )
        )
    html = render_page(
        title="News Model Test 2023-2024",
        subtitle=(
            f"Trades chosen by the global-news model in its test years 2023-2024 "
            f"({len(trades)} trades). Trained only on 2015-2022. Decision at 08:00 "
            "New York; $3,000 account, $30 risk, expensive costs."
        ),
        rules=[
            "Every trading day at 08:00 New York a gradient-boosted tree model "
            "estimates the chance that a buy wins by 12:00. It buys at 55% or "
            "more, sells at 45% or less, otherwise skips.",
            "Inputs: gold's own context, yesterday's US dollar, yields, S&P 500 and "
            "VIX, the US news calendar, and worldwide news from GDELT over the last "
            "24 hours against the week before (war, central banks, gold, inflation, "
            "stock markets, sanctions, elections, AI/tech, bubbles, funds and more).",
            "Stop and target are both half of the 20-day average daily range (1:1), "
            "normal stop orders. Anything open closes at 12:00 New York.",
        ],
        records=records,
        all_trades=trades,
        note="Account starts at $3,000.",
    )
    REPLAY.write_text(html)


def render_md(p: dict[str, Any]) -> str:
    L = [
        "# Gold with global news sentiment (train 2015-2022, test 2023-2024)",
        "",
        "Every trading day at 08:00 New York a model estimates the chance that a "
        "1:1 buy wins by 12:00 (stop = target = half the 20-day average daily range, "
        f"normal stops). {p['inputs']} inputs: gold, US dollar, yields, S&P 500, VIX, "
        "US news calendar, and 71 worldwide-news inputs from GDELT (share, surge, "
        "tone and tone change per topic over the last 24 hours vs the week before). "
        f"Trained on {p['train_days']} days ({p['train'][0]} to {p['train'][1]}), "
        f"tested once on {p['test_days']} days ({p['test'][0]} to {p['test'][1]}). "
        "Settings fixed before running. Expensive costs, $30 risk on $3,000. 2025 "
        "and 2026 not loaded.",
        "",
        f"A buy won {p['share_buy_wins_test']:.0%} of test days. Pass: profitable, "
        "at least 50% winning trades, better than the best simple rule. Passed: "
        f"**{'yes' if p['passed'] else 'no'}**.",
        "",
        "## Direction right",
        "",
        "| Model | Training years | Test years | Test, when confident |",
        "| --- | ---: | ---: | ---: |",
    ]
    for k, a in p["accuracy"].items():
        conf = f"{a['test_when_confident']:.1%}" if a["test_when_confident"] else "-"
        L.append(f"| {k} | {a['train']:.1%} | {a['test']:.1%} | {conf} |")
    L += [
        "",
        "## Trades in 2023-2024",
        "",
        "| Rule | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ | "
        "Net $ at 2x | PF | Max DD $ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for k, v in p["results"].items():
        if not v["trades"]:
            L.append(f"| {k} | 0 | | | | | | | | |")
            continue
        pf = f"{v['profit_factor']:.2f}" if v.get("profit_factor") else "-"
        x2 = fmt(v["net_usd_at_2x"]) if "net_usd_at_2x" in v else "-"
        L.append(
            f"| {k} | {v['trades']} | {v['win_rate']:.0%} | {v['avg_win']:.2f} | "
            f"{v['avg_loss']:.2f} | {v['avg_per_trade']:.2f} | {fmt(v['net_usd'])} | "
            f"{x2} | {pf} | {fmt(v['max_drawdown_usd'])} |"
        )
    L += [
        "",
        "## Inputs that mattered most in the test years",
        "",
        "Drop in test accuracy when the input is shuffled (trees, with news). Values "
        "near zero mean the input did not help.",
        "",
        "| Input | Accuracy drop | +/- |",
        "| --- | ---: | ---: |",
    ]
    for t in p["test_importance_top15"]:
        L.append(f"| {t['input']} | {t['accuracy_drop']:+.4f} | {t['std']:.4f} |")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
