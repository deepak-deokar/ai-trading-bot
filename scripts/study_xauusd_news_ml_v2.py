"""Gold + global news, round 2: stricter tuning, more news, and a move-size target.

Same daily setup as study_xauusd_news_ml (08:00 New York decision, 1:1 trade at
half the 20-day average daily range, closed 12:00). Rules fixed before running:

Inputs, three sets:
  base   21 inputs (gold, US dollar, yields, S&P 500, VIX, US news calendar)
  news   base + 71 topic inputs (last 24 h vs the week before)
  full   news + fresh-news surges (last 3 h vs the 24 h before) + event records
         (threats, protests, force, coercion/sanctions, fighting, conflict vs
         cooperation, regional conflict) + people/organisations in the news

Tuning: every combination below is fitted on 2015-03..2020 and scored on
2021-2022 (log loss; 0.693 = no better than 50/50). 2023-2024 is not used for
any choice. Grid for gradient-boosted trees: depth 2/3, at least 100/250 days
per leaf, 100/300 rounds, L2 1/20, each split sees 30%/100% of inputs, learning
rate 0.03.

The winning set and settings are refitted on 2015-03..2022 and looked at once on
2023-2024 (this is the second look at those years; the first was the previous
study). Trades: buy at P >= 0.55, sell at P <= 0.45. Pass: profitable after
expensive costs, at least 50% winners, better than the best simple rule.

Move size: the same tuning picks a tree regression for the 08:00-12:00 range
(high - low, in units of the 20-day average daily range), compared with simply
predicting the training average; scored by R-squared and rank correlation.

2025 and 2026 are never loaded.
Writes docs/xauusd-news-ml-v2.{json,md}.
Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/study_xauusd_news_ml_v2.py
"""

import itertools
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.metrics import log_loss, r2_score
from study_xauusd_news_model import fmt, summary  # type: ignore[import-not-found]

from trading_bot.backtesting.daily_model import FEATURES as BASE_FEATURES
from trading_bot.backtesting.daily_model import DayRow, build_rows, trade_row
from trading_bot.backtesting.news_day import load_events
from trading_bot.backtesting.news_features import (
    HourlyTable,
    NewsHours,
    entity_feature_names,
    entity_features_at,
    event_feature_names,
    event_features_at,
    news_feature_names,
    short_feature_names,
    short_features_at,
)
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, Sizing, load_bars
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.data.gdelt_news import (
    ENTITIES_CSV,
    EVENTS_CSV,
    ORGANISATIONS,
    PERSONS,
    load_hourly,
    load_table,
)
from trading_bot.data.histdata_bulk import BARS_DIR
from trading_bot.data.macro_daily import load as load_macro

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-news-ml-v2")
FIRST_DAY = date(2015, 3, 2)
FIT_LAST, VALID = 2020, (2021, 2022)
TRAIN_LAST, TEST = 2022, (2023, 2024)
MARGIN = 0.05
SEED = 7
GRID = {
    "max_depth": (2, 3),
    "min_samples_leaf": (100, 250),
    "max_iter": (100, 300),
    "l2_regularization": (1.0, 20.0),
    "max_features": (0.3, 1.0),
}


def combos() -> list[dict[str, Any]]:
    keys = list(GRID)
    return [dict(zip(keys, v, strict=True)) for v in itertools.product(*GRID.values())]


def clf(params: dict[str, Any]) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        learning_rate=0.03, early_stopping=False, random_state=SEED, **params
    )


def reg(params: dict[str, Any]) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        learning_rate=0.03, early_stopping=False, random_state=SEED, **params
    )


def trades_for(
    bars: dict[str, Array], rows: list[DayRow], p: Array, costs: CostModel
) -> list[HoldTrade]:
    out = []
    for r, q in zip(rows, p, strict=True):
        d = 1 if q >= 0.5 + MARGIN else -1 if q <= 0.5 - MARGIN else 0
        if d:
            t = trade_row(bars, r, d, costs, Sizing())
            if t is not None:
                out.append(t)
    return out


def spearman(a: Array, b: Array) -> float:
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    bars = load_bars(BARS_DIR, 201501, 202412)
    days = build_days(bars)
    rows_all = build_rows(
        bars, days, load_macro(), load_events(one_per_day=False), range(2015, 2025)
    )
    news = NewsHours.from_columns(*load_hourly())
    eh, ed = load_table(EVENTS_CSV)
    events = HourlyTable.from_columns(eh, ed, weighted={"ev_goldstein": "ev_n"})
    nh, nd = load_table(ENTITIES_CSV)
    ents = HourlyTable.from_columns(
        nh, nd, weighted={f"tone_{n}": f"n_{n}" for n in [*PERSONS, *ORGANISATIONS]}
    )
    m = bars["minute_utc"]
    mh = (bars["bid_high"] + bars["ask_high"]) / 2
    ml = (bars["bid_low"] + bars["ask_low"]) / 2
    rows, xb, xn, xf, move = [], [], [], [], []
    for r in rows_all:
        if r.day < FIRST_DAY:
            continue
        t = int(m[r.entry_minute])
        f24 = news.features_at(t)
        f3 = short_features_at(news, t)
        fe = event_features_at(events, t)
        fp = entity_features_at(ents, news, t)
        if f24 is None or f3 is None or fe is None or fp is None:
            continue
        rows.append(r)
        xb.append(r.features)
        xn.append(r.features + f24)
        xf.append(r.features + f24 + f3 + fe + fp)
        sl = slice(r.entry_minute, r.last_minute + 1)
        move.append(float(mh[sl].max() - ml[sl].min()) / (2 * r.risk))  # in ADR
    sets = {"base": np.array(xb), "news": np.array(xn), "full": np.array(xf)}
    names = {
        "base": list(BASE_FEATURES),
        "news": list(BASE_FEATURES) + news_feature_names(),
        "full": list(BASE_FEATURES)
        + news_feature_names()
        + short_feature_names()
        + event_feature_names()
        + entity_feature_names(),
    }
    y = np.array([r.label for r in rows])
    mv = np.array(move)
    yr = np.array([r.year for r in rows])
    fit, valid = yr <= FIT_LAST, np.isin(yr, VALID)
    train, test = yr <= TRAIN_LAST, np.isin(yr, TEST)
    print(
        {k: v.shape for k, v in sets.items()},
        "fit",
        fit.sum(),
        "valid",
        valid.sum(),
        "test",
        test.sum(),
        flush=True,
    )

    # ---- direction: tune on 2015-2020 -> 2021-2022 -----------------------------
    tuning = []
    for set_name, x in sets.items():
        for params in combos():
            model = clf(params).fit(x[fit], y[fit])
            p = model.predict_proba(x[valid])[:, 1]
            tuning.append(
                {
                    "set": set_name,
                    "params": params,
                    "valid_log_loss": round(float(log_loss(y[valid], p)), 5),
                    "valid_accuracy": round(
                        float(np.mean((p > 0.5) == (y[valid] == 1))), 4
                    ),
                    "fit_accuracy": round(
                        float(
                            np.mean(
                                (model.predict_proba(x[fit])[:, 1] > 0.5)
                                == (y[fit] == 1)
                            )
                        ),
                        4,
                    ),
                }
            )
    tuning.sort(key=lambda d: d["valid_log_loss"])
    best = tuning[0]
    best_per_set = {s: next(d for d in tuning if d["set"] == s) for s in sets}
    print("best", best, flush=True)

    # ---- one look at 2023-2024 --------------------------------------------------
    test_rows = [r for r, k in zip(rows, test, strict=True) if k]
    direction: dict[str, Any] = {}
    for s, d in best_per_set.items():
        model = clf(d["params"]).fit(sets[s][train], y[train])
        p = model.predict_proba(sets[s][test])[:, 1]
        res = summary(trades_for(bars, test_rows, p, costs))
        direction[s] = {
            "params": d["params"],
            "valid_log_loss": d["valid_log_loss"],
            "valid_accuracy": d["valid_accuracy"],
            "test_log_loss": round(float(log_loss(y[test], p)), 5),
            "test_accuracy": round(float(np.mean((p > 0.5) == (y[test] == 1))), 4),
            "trades": res,
        }
        print(
            s,
            direction[s]["test_accuracy"],
            res.get("trades"),
            res.get("win_rate"),
            res.get("net_usd"),
            flush=True,
        )
    always_buy = summary(trades_for(bars, test_rows, np.ones(int(test.sum())), costs))

    # ---- move size --------------------------------------------------------------
    small = [
        {
            "max_depth": 3,
            "min_samples_leaf": leaf,
            "max_iter": it,
            "l2_regularization": 1.0,
            "max_features": mf,
        }
        for leaf in (100, 250)
        for it in (100, 300)
        for mf in (0.3, 1.0)
    ]
    move_tuning = []
    for set_name, x in sets.items():
        for params in small:
            pr = reg(params).fit(x[fit], mv[fit]).predict(x[valid])
            move_tuning.append(
                {
                    "set": set_name,
                    "params": params,
                    "valid_r2": round(float(r2_score(mv[valid], pr)), 4),
                    "valid_rank_corr": round(spearman(mv[valid], pr), 4),
                }
            )
    move_tuning.sort(key=lambda d: -d["valid_r2"])
    move_best = {s: next(d for d in move_tuning if d["set"] == s) for s in sets}
    move_result: dict[str, Any] = {}
    for s, d in move_best.items():
        pr = reg(d["params"]).fit(sets[s][train], mv[train]).predict(sets[s][test])
        move_result[s] = {
            "params": d["params"],
            "valid_r2": d["valid_r2"],
            "valid_rank_corr": d["valid_rank_corr"],
            "test_r2": round(float(r2_score(mv[test], pr)), 4),
            "test_rank_corr": round(spearman(mv[test], pr), 4),
        }
        print("move", s, move_result[s], flush=True)
    # naive comparison: yesterday's volatility ratio only (ADR5/ADR20) is in base

    main_dir = direction[best["set"]]["trades"]
    passed = (
        main_dir.get("trades", 0) > 0
        and main_dir["net_usd"] > 0
        and main_dir["win_rate"] >= 0.5
        and main_dir["net_usd"] > always_buy["net_usd"]
    )
    payload = {
        "design": "see this script's docstring",
        "rows": {
            "fit_2015_2020": int(fit.sum()),
            "valid_2021_2022": int(valid.sum()),
            "test_2023_2024": int(test.sum()),
        },
        "inputs": {k: len(v) for k, v in names.items()},
        "chosen_on_validation": best,
        "direction": direction,
        "always_buy_test": always_buy,
        "move_size": move_result,
        "move_test_average_range_adr": round(float(mv[test].mean()), 3),
        "top_tuning": tuning[:10],
        "passed": passed,
        "2025_2026": "not loaded",
    }
    OUT.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(payload))
    print("passed", passed, "wrote", OUT)


def render_md(p: dict[str, Any]) -> str:
    b = p["chosen_on_validation"]
    L = [
        "# Gold + global news, round 2 (tuned on 2021-2022, tested on 2023-2024)",
        "",
        "Daily 08:00-12:00 New York trade (1:1 at half the 20-day range). Three input "
        f"sets: base {p['inputs']['base']}, news {p['inputs']['news']}, full "
        f"{p['inputs']['full']} (adds fresh 3-hour news, event records, people and "
        "organisations). Every setting chosen by fitting 2015-2020 and scoring "
        f"2021-2022 ({p['rows']['fit_2015_2020']} / {p['rows']['valid_2021_2022']} "
        f"days); then refitted on 2015-2022 and looked at once on 2023-2024 "
        f"({p['rows']['test_2023_2024']} days). Log loss 0.693 = no better than "
        "50/50. Expensive costs. 2025-2026 not loaded.",
        "",
        f"Best on 2021-2022: **{b['set']}** inputs, log loss "
        f"{b['valid_log_loss']:.4f}, "
        f"accuracy {b['valid_accuracy']:.1%} (fit years {b['fit_accuracy']:.1%}). "
        f"Passed: **{'yes' if p['passed'] else 'no'}**.",
        "",
        "## Direction",
        "",
        "| Inputs | 2021-22 log loss | 2021-22 right | 2023-24 log loss | "
        "2023-24 right "
        "| Trades | Win % | Net $ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s, d in p["direction"].items():
        t = d["trades"]
        L.append(
            f"| {s} | {d['valid_log_loss']:.4f} | {d['valid_accuracy']:.1%} | "
            f"{d['test_log_loss']:.4f} | {d['test_accuracy']:.1%} | "
            f"{t.get('trades', 0)} | {t.get('win_rate', 0):.0%} | "
            f"{fmt(t.get('net_usd', 0))} |"
        )
    ab = p["always_buy_test"]
    L += [
        f"| always buy (2023-24) | | | | | {ab['trades']} | {ab['win_rate']:.0%} | "
        f"{fmt(ab['net_usd'])} |",
        "",
        "## How much gold moves 08:00-12:00 (range in units of the 20-day average "
        "daily range)",
        "",
        f"Average 2023-24 range: {p['move_test_average_range_adr']:.2f} x ADR. "
        "R-squared "
        "0 = no better than predicting the average; rank correlation 0 = no "
        "ordering skill.",
        "",
        "| Inputs | 2021-22 R-squared | 2021-22 rank corr | 2023-24 R-squared | "
        "2023-24 rank corr |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for s, d in p["move_size"].items():
        L.append(
            f"| {s} | {d['valid_r2']:+.3f} | {d['valid_rank_corr']:+.3f} | "
            f"{d['test_r2']:+.3f} | {d['test_rank_corr']:+.3f} |"
        )
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
