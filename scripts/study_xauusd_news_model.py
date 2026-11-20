"""Walk-forward test of the news-reaction model (trading_bot.backtesting.news_model).

Every prediction for year Y comes from a model trained only on earlier years, so
2016-2024 results are all on years the model had not seen. Only 2014-2024 data is
loaded. Compared with simple rules on the same events and the same 1:1 exits:
follow the news candle (momentum), go against it (fade), always buy.

Pass criteria, fixed before running: profitable after expensive costs over
2016-2024 at the main confidence margin (0.05), at least 50% winning trades, and
better than the best simple rule.

Writes docs/xauusd-news-model.{json,md} and a 2024 replay page.
Usage: PYTHONPATH=src .venv/bin/python scripts/study_xauusd_news_model.py
"""

import json
import statistics
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from trading_bot.backtesting.levels import key_levels
from trading_bot.backtesting.news_day import load_events
from trading_bot.backtesting.news_model import (
    FEATURES,
    EventRow,
    build_rows,
    fit_logistic,
    trade_row,
    walk_forward,
)
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import (
    Array,
    CostModel,
    Sizing,
    load_bars,
)
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.backtesting.trade_replay import (
    Highlight,
    ReplayContext,
    render_page,
    replay_record,
)
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-news-model")
REPLAY = Path("docs/replays/xauusd-news-model-2024.html")
DATA_YEARS = range(2014, 2025)
FIRST_TEST_YEAR = 2016
MAIN_MARGIN = 0.05
MARGINS = (0.0, MAIN_MARGIN, 0.10)
L2 = 1.0
LABEL = {"nfp": "jobs report", "cpi": "inflation (CPI)", "fomc": "Fed decision"}


def summary(trades: list[HoldTrade]) -> dict[str, Any]:
    if not trades:
        return {"trades": 0}
    pnl = [t.pnl_usd for t in trades]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p <= 0]
    by_year: dict[int, float] = {}
    for t in trades:
        by_year[t.day.year] = by_year.get(t.day.year, 0.0) + t.pnl_usd
    eq = np.cumsum(pnl)
    return {
        "trades": len(trades),
        "win_rate": round(len(wins) / len(pnl), 3),
        "net_usd": round(sum(pnl), 2),
        "avg_per_trade": round(statistics.mean(pnl), 2),
        "avg_win": round(statistics.mean(wins), 2) if wins else 0.0,
        "avg_loss": round(statistics.mean(losses), 2) if losses else 0.0,
        "profit_factor": round(sum(wins) / -sum(losses), 3) if losses else None,
        "max_drawdown_usd": round(float(np.max(np.maximum.accumulate(eq) - eq)), 2),
        "by_year": {y: round(v, 2) for y, v in sorted(by_year.items())},
        "green_years": sum(v > 0 for v in by_year.values()),
        "exit_mix": {
            r: sum(t.exit_reason == r for t in trades)
            for r in ("stop", "target", "time_exit")
        },
    }


def run_rule(
    bars: dict[str, Array],
    rows: list[EventRow],
    choose: Callable[[int, EventRow], int],
    costs: CostModel,
) -> list[HoldTrade]:
    trades = []
    for i, r in enumerate(rows):
        d = choose(i, r)
        if d == 0:
            continue
        t = trade_row(bars, r, d, costs, Sizing())
        if t is not None:
            trades.append(t)
    return trades


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    bars = load_bars(BARS_DIR, 201401, 202412)
    days = build_days(bars)
    events = load_events()
    rows = build_rows(bars, days, events, DATA_YEARS)
    preds = walk_forward(rows, FIRST_TEST_YEAR, L2)
    test = [i for i in range(len(rows)) if i in preds]
    test_rows = [rows[i] for i in test]

    def model_choice(margin: float) -> Callable[[int, EventRow], int]:
        def choose(j: int, r: EventRow) -> int:
            p = preds[test[j]][0]
            if p >= 0.5 + margin and p > 0.5:
                return 1
            if p <= 0.5 - margin and p < 0.5:
                return -1
            return 0

        return choose

    def news_dir(r: EventRow) -> int:
        return 1 if r.features[FEATURES.index("news_move")] > 0 else -1

    results: dict[str, Any] = {}
    for mg in MARGINS:
        results[f"model, margin {mg:.2f}"] = summary(
            run_rule(bars, test_rows, model_choice(mg), costs)
        )
    results["simple: follow the news candle"] = summary(
        run_rule(bars, test_rows, lambda j, r: news_dir(r), costs)
    )
    results["simple: against the news candle"] = summary(
        run_rule(bars, test_rows, lambda j, r: -news_dir(r), costs)
    )
    results["simple: always buy"] = summary(
        run_rule(bars, test_rows, lambda j, r: 1, costs)
    )
    for k, v in results.items():
        print(
            k,
            v.get("trades"),
            v.get("win_rate"),
            v.get("net_usd"),
            v.get("avg_per_trade"),
            flush=True,
        )

    y = np.array([r.label for r in test_rows])
    p = np.array([preds[i][0] for i in test])
    hit = float(np.mean((p > 0.5) == (y == 1)))
    # what the model learned: average weight over the yearly models, sign agreement
    yearly = {}
    for i in test:
        yearly[rows[i].event.day.year] = preds[i][1]
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
    main_res = results[f"model, margin {MAIN_MARGIN:.2f}"]
    best_simple = max(
        v["net_usd"] for k, v in results.items() if k.startswith("simple")
    )
    passed = (
        main_res["net_usd"] > 0
        and main_res["win_rate"] >= 0.5
        and main_res["net_usd"] > best_simple
    )
    payload = {
        "design": "see trading_bot.backtesting.news_model",
        "data_years": [DATA_YEARS.start, DATA_YEARS.stop - 1],
        "test_years": [FIRST_TEST_YEAR, DATA_YEARS.stop - 1],
        "events": len(rows),
        "test_events": len(test_rows),
        "share_buy_wins": round(float(y.mean()), 3),
        "direction_accuracy": round(hit, 3),
        "results": results,
        "weights": weights,
        "final_model_weights_2014_2024": dict(
            zip(FEATURES, [round(float(v), 3) for v in final.weights], strict=True)
        ),
        "passed": passed,
        "2025_2026": "not loaded",
    }
    OUT.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(payload))
    print("direction accuracy", round(hit, 3), "passed", passed)
    write_replay(bars, days, rows, preds, test, costs)
    print("wrote", OUT, REPLAY)


def write_replay(
    bars: dict[str, Array],
    days: list[Any],
    rows: list[EventRow],
    preds: dict[int, tuple[float, Any]],
    test: list[int],
    costs: CostModel,
) -> None:
    index = {d.day: k for k, d in enumerate(days)}
    records, trades = [], []
    n = len(bars["minute_utc"])
    for i in test:
        r = rows[i]
        if r.event.day.year != 2024:
            continue
        p = preds[i][0]
        d = 1 if p >= 0.5 + MAIN_MARGIN else -1 if p <= 0.5 - MAIN_MARGIN else 0
        if d == 0:
            continue
        t = trade_row(bars, r, d, costs, Sizing())
        if t is None:
            continue
        trades.append(t)
        release = int(np.searchsorted(bars["minute_utc"], r.event.utc()))
        k = index[r.event.day]
        lv = tuple((x.price, x.name) for x in key_levels(bars, days, k, release))
        conf = p if d == 1 else 1 - p
        ctx = ReplayContext(
            levels=lv,
            highlights=(
                Highlight(
                    release,
                    r.entry_minute - 1,
                    "NEWS",
                    f"The {LABEL[r.event.kind]} came out. After this candle the model "
                    f"gave {conf:.0%} odds that a {'buy' if d == 1 else 'sell'} "
                    "would win, so it took that side.",
                ),
            ),
        )
        records.append(
            replay_record(
                bars,
                t,
                costs,
                exit_at_close=t.exit_reason == "time_exit",
                window=(max(0, release - 90), min(n, t.exit_bar + 30)),
                context=ctx,
            )
        )
    html = render_page(
        title="News Model Replay 2024",
        subtitle=(
            f"Trades chosen by the news-reaction model in 2024 ({len(trades)} trades). "
            "The model for 2024 was trained only on 2014-2023. 5-minute mid-price "
            "candles, New York time; $3,000 account, $30 risk, expensive costs."
        ),
        rules=[
            "Only US jobs-report, CPI and scheduled Fed days; at most one trade.",
            "After the 15-minute news candle, the model estimates the chance that a "
            "buy wins. It buys at 55% or more, sells at 45% or less, otherwise skips.",
            "Stop and target are both half of the 20-day average daily range away "
            "(1:1). Normal stop orders that fill on touch.",
            "Anything still open closes at 12:00 New York (16:45 for the Fed).",
            "Dotted lines: yesterday's high/low and today's high/low before the news.",
        ],
        records=records,
        all_trades=trades,
        note="Account starts at $3,000.",
    )
    REPLAY.write_text(html)


def fmt(x: float) -> str:
    return f"{x:,.0f}"


def render_md(p: dict[str, Any]) -> str:
    years = list(range(p["test_years"][0], p["test_years"][1] + 1))
    L = [
        "# News-reaction model (walk-forward, 2014-2024 only)",
        "",
        "A logistic-regression model reads the first 15 minutes after US jobs, CPI "
        "and Fed releases and estimates the chance that a buy wins a 1:1 trade "
        "(stop and target = half the 20-day average daily range, normal stops, "
        "closed by 12:00 or 16:45 New York). For each year from "
        f"{p['test_years'][0]} the model is trained only on earlier years. "
        "Expensive costs, $30 risk on $3,000. 2025 and 2026 not loaded.",
        "",
        f"Events: {p['events']}; traded years {p['test_years'][0]}-"
        f"{p['test_years'][1]}: {p['test_events']} events. A buy won "
        f"{p['share_buy_wins']:.0%} of them. Model direction right: "
        f"{p['direction_accuracy']:.0%}.",
        "",
        "Pass: profitable, at least 50% winning trades, and better than the best "
        f"simple rule (main margin {MAIN_MARGIN}). Passed: "
        f"**{'yes' if p['passed'] else 'no'}**.",
        "",
        "| Rule | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ | PF "
        "| Max DD $ | Green years |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for k, v in p["results"].items():
        if not v["trades"]:
            L.append(f"| {k} | 0 | | | | | | | | |")
            continue
        pf = f"{v['profit_factor']:.2f}" if v["profit_factor"] else "-"
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
