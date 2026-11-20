"""Walk-forward test of the every-day model (trading_bot.backtesting.daily_model).

Each trading day 2014-2024 at 08:00 New York the model estimates the chance that
a 1:1 buy wins by 12:00, using gold's own context, the previous US close of the
US dollar, Treasury yields, the S&P 500 and VIX, and the day's news calendar.
Every prediction for year Y comes from a model trained only on earlier years.
Compared with simple rules on the same days and the same exits.

Pass criteria, fixed before running: profitable after expensive costs over
2016-2024 at the main margin (0.05), at least 50% winning trades, better than the
best simple rule. Only 2014-2024 is loaded.

Writes docs/xauusd-daily-model.{json,md} and a 2024 replay page.
Usage: PYTHONPATH=src .venv/bin/python scripts/study_xauusd_daily_model.py
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

# reuse the report helpers of the news-model study
from study_xauusd_news_model import fmt, summary  # type: ignore[import-not-found]

from trading_bot.backtesting.daily_model import (
    FEATURES,
    DayRow,
    build_rows,
    trade_row,
)
from trading_bot.backtesting.levels import key_levels
from trading_bot.backtesting.news_day import load_events
from trading_bot.backtesting.news_model import fit_logistic, walk_forward
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
from trading_bot.data.histdata_bulk import BARS_DIR
from trading_bot.data.macro_daily import load as load_macro

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-daily-model")
REPLAY = Path("docs/replays/xauusd-daily-model-2024.html")
DATA_YEARS = range(2014, 2025)
FIRST_TEST_YEAR = 2016
MAIN_MARGIN = 0.05
MARGINS = (0.0, MAIN_MARGIN, 0.10)
L2 = 1.0


def run_rule(
    bars: dict[str, Array],
    rows: list[DayRow],
    choose: Callable[[int, DayRow], int],
    costs: CostModel,
) -> list[HoldTrade]:
    trades = []
    for j, r in enumerate(rows):
        d = choose(j, r)
        if d:
            t = trade_row(bars, r, d, costs, Sizing())
            if t is not None:
                trades.append(t)
    return trades


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    bars = load_bars(BARS_DIR, 201401, 202412)
    days = build_days(bars)
    macro = load_macro()
    rows = build_rows(bars, days, macro, load_events(one_per_day=False), DATA_YEARS)
    preds = walk_forward(rows, FIRST_TEST_YEAR, L2)
    test = [i for i in range(len(rows)) if i in preds]
    test_rows = [rows[i] for i in test]
    fi = {f: j for j, f in enumerate(FEATURES)}

    def model_choice(margin: float) -> Callable[[int, DayRow], int]:
        def choose(j: int, r: DayRow) -> int:
            p = preds[test[j]][0]
            if p >= 0.5 + margin and p > 0.5:
                return 1
            if p <= 0.5 - margin and p < 0.5:
                return -1
            return 0

        return choose

    def sign(x: float) -> int:
        return 1 if x > 0 else -1 if x < 0 else 0

    rules: dict[str, Callable[[int, DayRow], int]] = {
        f"model, margin {mg:.2f}": model_choice(mg) for mg in MARGINS
    }
    rules["simple: always buy"] = lambda j, r: 1
    rules["simple: follow the overnight move"] = lambda j, r: sign(
        r.features[fi["overnight_move"]]
    )
    rules["simple: against the overnight move"] = lambda j, r: -sign(
        r.features[fi["overnight_move"]]
    )
    rules["simple: follow the 20-day trend"] = lambda j, r: sign(
        r.features[fi["trend_20d"]]
    )
    rules["simple: against yesterday's US dollar move"] = lambda j, r: -sign(
        r.features[fi["usd_1d"]]
    )
    results: dict[str, Any] = {}
    for name, choose in rules.items():
        results[name] = summary(run_rule(bars, test_rows, choose, costs))
        v = results[name]
        print(name, v["trades"], v["win_rate"], v["net_usd"], flush=True)
    main_name = f"model, margin {MAIN_MARGIN:.2f}"
    stress_main = summary(run_rule(bars, test_rows, rules[main_name], stress))

    y = np.array([r.label for r in test_rows])
    p = np.array([preds[i][0] for i in test])
    acc = float(np.mean((p > 0.5) == (y == 1)))
    sure = np.abs(p - 0.5) >= MAIN_MARGIN
    acc_sure = float(np.mean(((p > 0.5) == (y == 1))[sure])) if sure.any() else 0.0
    yearly = {rows[i].year: preds[i][1] for i in test}
    w = np.array([m.weights for m in yearly.values()])
    weights = {
        f: {
            "avg_weight": round(float(w[:, j].mean()), 3),
            "same_sign_years": int(max((w[:, j] > 0).sum(), (w[:, j] < 0).sum())),
        }
        for j, f in enumerate(FEATURES)
    }
    final = fit_logistic(
        np.array([r.features for r in rows]),
        np.array([r.label for r in rows], dtype=float),
        L2,
    )
    main_res = results[main_name]
    best_simple = max(
        v["net_usd"] for k, v in results.items() if k.startswith("simple")
    )
    passed = (
        main_res["net_usd"] > 0
        and main_res["win_rate"] >= 0.5
        and main_res["net_usd"] > best_simple
    )
    payload = {
        "design": "see trading_bot.backtesting.daily_model",
        "data_years": [2014, 2024],
        "test_years": [FIRST_TEST_YEAR, 2024],
        "days": len(rows),
        "test_days": len(test_rows),
        "share_buy_wins": round(float(y.mean()), 3),
        "direction_accuracy": round(acc, 3),
        "direction_accuracy_when_confident": round(acc_sure, 3),
        "results": results,
        "main_at_2x_costs": stress_main,
        "weights": weights,
        "final_model_weights_2014_2024": dict(
            zip(FEATURES, [round(float(v), 3) for v in final.weights], strict=True)
        ),
        "passed": passed,
        "2025_2026": "not loaded",
    }
    OUT.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(payload))
    print("accuracy", round(acc, 3), "confident", round(acc_sure, 3), "passed", passed)
    write_replay(bars, days, rows, preds, test, costs)
    print("wrote", OUT, REPLAY)


def write_replay(
    bars: dict[str, Array],
    days: list[Any],
    rows: list[DayRow],
    preds: dict[int, tuple[float, Any]],
    test: list[int],
    costs: CostModel,
) -> None:
    index = {d.day: k for k, d in enumerate(days)}
    records, trades = [], []
    n = len(bars["minute_utc"])
    for i in test:
        r = rows[i]
        if r.year != 2024:
            continue
        p = preds[i][0]
        d = 1 if p >= 0.5 + MAIN_MARGIN else -1 if p <= 0.5 - MAIN_MARGIN else 0
        if not d:
            continue
        t = trade_row(bars, r, d, costs, Sizing())
        if t is None:
            continue
        trades.append(t)
        k = index[r.day]
        lv = tuple((x.price, x.name) for x in key_levels(bars, days, k, r.entry_minute))
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
        title="Daily Model Replay 2024",
        subtitle=(
            f"Trades chosen by the every-day model in 2024 ({len(trades)} trades), "
            "trained only on 2014-2023. Decision at 08:00 New York. 5-minute "
            "mid-price candles; $3,000 account, $30 risk, expensive costs."
        ),
        rules=[
            "Every trading day at 08:00 New York the model estimates the chance "
            "that a buy wins by 12:00. It buys at 55% or more, sells at 45% or "
            "less, otherwise skips the day.",
            "Inputs: gold's overnight move and range, trends, place in yesterday's "
            "range, room to support/resistance, volatility; yesterday's US dollar, "
            "10-year and 3-month yields, S&P 500 and VIX; whether jobs, CPI or Fed "
            "news is due today.",
            "Stop and target are both half of the 20-day average daily range (1:1), "
            "normal stop orders. Anything open closes at 12:00 New York.",
            "Dotted lines: yesterday's high/low and today's high/low before 08:00.",
        ],
        records=records,
        all_trades=trades,
        note="Account starts at $3,000.",
    )
    REPLAY.write_text(html)


def render_md(p: dict[str, Any]) -> str:
    years = list(range(p["test_years"][0], p["test_years"][1] + 1))
    s2 = p["main_at_2x_costs"]
    L = [
        "# Every-day model with US dollar, yields, stocks and VIX (walk-forward)",
        "",
        "Each trading day at 08:00 New York a logistic-regression model estimates "
        "the chance that a 1:1 buy wins by 12:00 (stop and target = half the 20-day "
        "average daily range, normal stops). Inputs: gold's own context, the "
        "previous US close of the US dollar index, 10-year and 3-month yields, S&P "
        "500 and VIX, and the day's jobs/CPI/Fed calendar. For each year from "
        f"{p['test_years'][0]} the model is trained only on earlier years. "
        "Expensive costs, $30 risk on $3,000. 2025 and 2026 not loaded.",
        "",
        f"Days: {p['days']}; traded years: {p['test_days']} days. A buy won "
        f"{p['share_buy_wins']:.0%} of them. Model direction right: "
        f"{p['direction_accuracy']:.1%} (when confident: "
        f"{p['direction_accuracy_when_confident']:.1%}).",
        "",
        "Pass: profitable, at least 50% winning trades, better than the best simple "
        f"rule (main margin {MAIN_MARGIN}). Passed: "
        f"**{'yes' if p['passed'] else 'no'}**. Main model at 2x costs: "
        f"{fmt(s2['net_usd'])} $.",
        "",
        "| Rule | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ | PF "
        "| Max DD $ | Green years |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for k, v in p["results"].items():
        pf = f"{v['profit_factor']:.2f}" if v.get("profit_factor") else "-"
        L.append(
            f"| {k} | {v['trades']} | {v['win_rate']:.0%} | {v['avg_win']:.2f} | "
            f"{v['avg_loss']:.2f} | {v['avg_per_trade']:.2f} | {fmt(v['net_usd'])} | "
            f"{pf} | {fmt(v['max_drawdown_usd'])} | {v['green_years']}/{len(years)} |"
        )
    L += [
        "",
        "Net $ per year:",
        "",
        "| Rule | " + " | ".join(str(y) for y in years) + " |",
        "| --- |" + " ---: |" * len(years),
    ]
    for k, v in p["results"].items():
        by = v.get("by_year", {})
        L.append(
            f"| {k} | "
            + " | ".join(fmt(by.get(y, by.get(str(y), 0.0))) for y in years)
            + " |"
        )
    L += [
        "",
        "What the model learned (positive = favours buying), averaged over the "
        "yearly models, and in how many yearly models the weight had that sign:",
        "",
        "| Input | Avg weight | Same sign in years | Weight, trained on 2014-2024 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for f, w in p["weights"].items():
        L.append(
            f"| {f} | {w['avg_weight']:+.3f} | {w['same_sign_years']}/{len(years)} | "
            f"{p['final_model_weights_2014_2024'][f]:+.3f} |"
        )
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
