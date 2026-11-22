"""Breakouts only on mornings the news model expects to be busy.

1. Move-size model: gradient-boosted tree regression on the "news" inputs
   (gold, US dollar, yields, S&P 500, VIX, calendar, 24 h world-news topics),
   settings as chosen on 2021-2022 in study_xauusd_news_ml_v2. It predicts the
   08:00-12:00 New York range in units of the 20-day average daily range (ADR).
2. Trade (trading_bot.backtesting.move_strategy): on days whose predicted move
   is in the top share of the training years' predictions, place buy/sell stop
   orders k x ADR above/below the 08:00 price; the first one hit is the trade,
   stop at the other level, target target_r x risk, out by 12:00.

Choices, fixed before running: top share 40% / 30% / 20%, k 0.10 / 0.15 /
0.20, target 1 / 1.5 / 2 R. Chosen by fitting the model on 2015-03..2020 and
scoring the trades on 2021-2022 (most net profit with at least 30 trades). Then
the model is refitted on 2015-03..2022 and the chosen rule is looked at once on
2023-2024, next to the same breakout on every day and on predicted-quiet days.

Pass: 2023-2024 profitable after expensive costs, at least 50% winning trades,
better than taking the same breakout every day. 2025-2026 never loaded.
Writes docs/xauusd-move-strategy.{json,md} and a 2023-2024 replay page.
Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/study_xauusd_move_strategy.py
"""

import itertools
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from study_xauusd_news_model import fmt, summary  # type: ignore[import-not-found]

from trading_bot.backtesting.daily_model import DayRow
from trading_bot.backtesting.levels import key_levels
from trading_bot.backtesting.move_strategy import breakout_trade
from trading_bot.backtesting.news_dataset import NewsDataset, build_dataset
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, Sizing, load_bars
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.backtesting.trade_replay import (
    Highlight,
    ReplayContext,
    render_page,
    replay_record,
)
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path(os.environ.get("XAU_COSTS", "config/xauusd_costs_expensive.yaml"))
SUFFIX = os.environ.get("XAU_OUT_SUFFIX", "")  # e.g. "-equiti"
OUT = Path("docs/xauusd-move-strategy" + SUFFIX)
REPLAY = Path("docs/replays/xauusd-move-strategy-2023-2024" + SUFFIX + ".html")
FIT_LAST, VALID = 2020, (2021, 2022)
TRAIN_LAST, TEST = 2022, (2023, 2024)
SEED = 7
INPUTS = "news"
MODEL = {
    "max_depth": 3,
    "min_samples_leaf": 250,
    "max_iter": 100,
    "l2_regularization": 1.0,
    "max_features": 0.3,
}
TOP_SHARES = (0.40, 0.30, 0.20)
KS = (0.10, 0.15, 0.20)
TARGETS = (1.0, 1.5, 2.0)
MIN_TRADES = 30


def model() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        learning_rate=0.03, early_stopping=False, random_state=SEED, **MODEL
    )


def run(
    bars: dict[str, Array],
    rows: list[DayRow],
    take: Array,
    k: float,
    target_r: float,
    costs: CostModel,
) -> list[HoldTrade]:
    out = []
    for r, ok in zip(rows, take, strict=True):
        if ok:
            t = breakout_trade(bars, r, k, target_r, costs, Sizing())
            if t is not None:
                out.append(t)
    return out


def predictions(ds: NewsDataset, fit: Array, apply: Array) -> tuple[Array, Array]:
    x = ds.x[INPUTS]
    reg = model().fit(x[fit], ds.move[fit])
    return reg.predict(x[fit]), reg.predict(x[apply])


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    bars = load_bars(BARS_DIR, 201501, 202412)
    days = build_days(bars)
    ds = build_dataset(bars, days, range(2015, 2025))
    yr = ds.year
    fit, valid = yr <= FIT_LAST, np.isin(yr, VALID)
    train, test = yr <= TRAIN_LAST, np.isin(yr, TEST)
    rows_valid = [r for r, v in zip(ds.rows, valid, strict=True) if v]
    rows_test = [r for r, v in zip(ds.rows, test, strict=True) if v]

    # ---- choose the rule on 2021-2022 ---------------------------------------
    p_fit, p_valid = predictions(ds, fit, valid)
    tuning = []
    for share, k, tr in itertools.product(TOP_SHARES, KS, TARGETS):
        cut = float(np.quantile(p_fit, 1 - share))
        res = summary(run(bars, rows_valid, p_valid >= cut, k, tr, costs))
        tuning.append({"top_share": share, "k": k, "target_r": tr, **res})
    ok = [t for t in tuning if t.get("trades", 0) >= MIN_TRADES]
    best = max(ok, key=lambda t: t["net_usd"])
    print(
        "chosen on 2021-22:",
        {
            x: best[x]
            for x in ("top_share", "k", "target_r", "trades", "win_rate", "net_usd")
        },
        flush=True,
    )
    k, tr, share = best["k"], best["target_r"], best["top_share"]
    every_valid = summary(
        run(bars, rows_valid, np.ones(len(rows_valid), bool), k, tr, costs)
    )

    # ---- one look at 2023-2024 ----------------------------------------------
    p_train, p_test = predictions(ds, train, test)
    cut = float(np.quantile(p_train, 1 - share))
    busy = p_test >= cut
    quiet_cut = float(np.quantile(p_train, share))
    quiet = p_test <= quiet_cut
    res_busy = summary(run(bars, rows_test, busy, k, tr, costs))
    res_busy_2x = summary(run(bars, rows_test, busy, k, tr, stress))
    res_every = summary(
        run(bars, rows_test, np.ones(len(rows_test), bool), k, tr, costs)
    )
    res_quiet = summary(run(bars, rows_test, quiet, k, tr, costs))
    actual = ds.move[test]
    corr = float(
        np.corrcoef(np.argsort(np.argsort(actual)), np.argsort(np.argsort(p_test)))[
            0, 1
        ]
    )
    busy_actual = float(actual[busy].mean()) if busy.any() else 0.0
    rest_actual = float(actual[~busy].mean()) if (~busy).any() else 0.0
    passed = (
        res_busy.get("trades", 0) > 0
        and res_busy["net_usd"] > 0
        and res_busy["win_rate"] >= 0.5
        and res_busy["net_usd"] > res_every["net_usd"]
    )
    for name, v in (
        ("busy days", res_busy),
        ("every day", res_every),
        ("quiet days", res_quiet),
        ("busy at 2x", res_busy_2x),
    ):
        print(name, v.get("trades"), v.get("win_rate"), v.get("net_usd"), flush=True)
    payload = {
        "design": "see this script's docstring",
        "model_inputs": INPUTS,
        "model_settings": MODEL,
        "chosen_on_2021_2022": best,
        "every_day_2021_2022": every_valid,
        "tuning_2021_2022": sorted(tuning, key=lambda t: -t.get("net_usd", -1e9)),
        "test_2023_2024": {
            "busy_days": res_busy,
            "busy_days_at_2x_costs": res_busy_2x,
            "every_day": res_every,
            "quiet_days": res_quiet,
            "days": int(test.sum()),
            "busy_days_count": int(busy.sum()),
            "move_rank_corr": round(corr, 3),
            "avg_move_busy_days_adr": round(busy_actual, 3),
            "avg_move_other_days_adr": round(rest_actual, 3),
        },
        "passed": passed,
        "2025_2026": "not loaded",
    }
    OUT.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(payload))
    write_replay(bars, days, rows_test, busy, p_test, k, tr, costs)
    print("passed", passed, "wrote", OUT, REPLAY)


def write_replay(
    bars: dict[str, Array],
    days: list[Any],
    rows: list[DayRow],
    busy: Array,
    pred: Array,
    k: float,
    tr: float,
    costs: CostModel,
) -> None:
    index = {d.day: n for n, d in enumerate(days)}
    nbar = len(bars["minute_utc"])
    records, trades = [], []
    for r, b, p in zip(rows, busy, pred, strict=True):
        if not b:
            continue
        t = breakout_trade(bars, r, k, tr, costs, Sizing())
        if t is None:
            continue
        trades.append(t)
        lv = tuple(
            (x.price, x.name)
            for x in key_levels(bars, days, index[r.day], r.entry_minute)
        )
        ctx = ReplayContext(
            levels=lv,
            highlights=(
                Highlight(
                    r.entry_minute,
                    r.entry_minute,
                    "08:00",
                    f"08:00 New York: the model expects a range of {p:.2f} x the "
                    "average day, so buy and sell stop orders wait above and below.",
                ),
            ),
        )
        records.append(
            replay_record(
                bars,
                t,
                costs,
                exit_at_close=t.exit_reason == "time_exit",
                window=(max(0, r.entry_minute - 120), min(nbar, t.exit_bar + 30)),
                context=ctx,
            )
        )
    html = render_page(
        title="Busy-Day Breakouts 2023-2024",
        subtitle=(
            f"Breakouts taken only on mornings the news model expected to be busy, "
            f"2023-2024 ({len(trades)} trades; model trained on 2015-2022 only). "
            "5-minute mid-price candles, New York time; $3,000 account, $30 risk, "
            f"costs: {COSTS_YAML.stem}."
        ),
        rules=[
            "At 08:00 New York a model predicts how much gold will move by 12:00, "
            "from gold, the US dollar, yields, stocks, VIX, the US calendar and the "
            "last 24 hours of world news.",
            "Only on the busiest predicted mornings: buy if price rises "
            f"{k:g} x the average daily range above the 08:00 price, sell if it "
            "falls that far below.",
            f"Stop at the other level; target {tr:g} x the risk; out by 12:00.",
        ],
        records=records,
        all_trades=trades,
        note="Account starts at $3,000.",
    )
    REPLAY.write_text(html)


def render_md(p: dict[str, Any]) -> str:
    b, t = p["chosen_on_2021_2022"], p["test_2023_2024"]
    L = [
        "# Breakouts only on predicted busy mornings",
        "",
        "A news-aware model predicts the 08:00-12:00 New York range; on the "
        "busiest predicted mornings stop orders wait k x ADR above and below the "
        "08:00 price. Rule chosen by fitting 2015-2020 and scoring 2021-2022; "
        "looked at once on 2023-2024 with the model refitted on 2015-2022. "
        f"Costs: {COSTS_YAML.stem}, $30 risk on $3,000. 2025-2026 not loaded.",
        "",
        f"Chosen on 2021-2022: top {b['top_share']:.0%} busiest mornings, k = "
        f"{b['k']}, target {b['target_r']}R: {b['trades']} trades, "
        f"{b['win_rate']:.0%} winners, {fmt(b['net_usd'])} $ (every day with the "
        f"same rule: {fmt(p['every_day_2021_2022']['net_usd'])} $).",
        "",
        f"Passed on 2023-2024: **{'yes' if p['passed'] else 'no'}**.",
        "",
        f"Model check 2023-2024: rank correlation {t['move_rank_corr']:+.2f}; "
        f"mornings picked as busy moved {t['avg_move_busy_days_adr']:.2f} x ADR, "
        f"the others {t['avg_move_other_days_adr']:.2f} x ADR.",
        "",
        "| 2023-2024 | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ "
        "| PF | Max DD $ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, key in (
        ("Predicted busy days", "busy_days"),
        ("Predicted busy days, 2x costs", "busy_days_at_2x_costs"),
        ("Every day", "every_day"),
        ("Predicted quiet days", "quiet_days"),
    ):
        v = t[key]
        if not v.get("trades"):
            L.append(f"| {name} | 0 | | | | | | | |")
            continue
        pf = f"{v['profit_factor']:.2f}" if v.get("profit_factor") else "-"
        L.append(
            f"| {name} | {v['trades']} | {v['win_rate']:.0%} | {v['avg_win']:.2f} | "
            f"{v['avg_loss']:.2f} | {v['avg_per_trade']:.2f} | {fmt(v['net_usd'])} | "
            f"{pf} | {fmt(v['max_drawdown_usd'])} |"
        )
    L += [
        "",
        "## All rule choices on 2021-2022 (best first)",
        "",
        "| Top share | k | Target R | Trades | Win % | Net $ |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for x in p["tuning_2021_2022"]:
        if not x.get("trades"):
            continue
        L.append(
            f"| {x['top_share']:.0%} | {x['k']} | {x['target_r']} | {x['trades']} | "
            f"{x['win_rate']:.0%} | {fmt(x['net_usd'])} |"
        )
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
