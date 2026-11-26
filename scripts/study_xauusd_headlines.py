"""Gold headlines vs the 08:00-12:00 New York direction.

Rules: docs/xauusd-headlines-plan.md (written before running). Candidates:
  v2_news         news-ml-v2 inputs (reference)
  news_words      v2 news + headline word-list inputs (trees)
  headline_text   TF-IDF of the last 24 h of gold titles + logistic regression
  words_only      headline word-list inputs alone (trees)
Each tuned on 2019-10..2021 -> 2022 log loss (amendment 1: titles start
2019-09-22); the best is refitted on 2019-10..2022 and looked at once on
2023-2024 (third look at those years for news
models). 2025-2026 never loaded.

Writes docs/xauusd-headlines.{json,md}.
Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/study_xauusd_headlines.py
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, r2_score
from study_xauusd_news_ml_v2 import (  # type: ignore[import-not-found]
    TEST,
    TRAIN_LAST,
    clf,
    combos,
    reg,
    spearman,
    trades_for,
)
from study_xauusd_news_model import summary  # type: ignore[import-not-found]

from trading_bot.backtesting.headline_features import Headlines, feature_names
from trading_bot.backtesting.news_dataset import build_dataset
from trading_bot.backtesting.session_window import CostModel, load_bars
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-headlines")
TEXT_C = (0.01, 0.1, 1.0, 10.0)
FIRST_DAY = date(2019, 10, 1)  # amendment 1
FIT_LAST, VALID = 2021, (2022,)


def text_model(c: float) -> tuple[TfidfVectorizer, LogisticRegression]:
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=20, sublinear_tf=True)
    return vec, LogisticRegression(C=c, max_iter=2000)


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    costs2 = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    bars = load_bars(BARS_DIR, 201501, 202412)
    days = build_days(bars)
    ds = build_dataset(bars, days, range(2015, 2025))
    hl = Headlines.load()
    print("headlines", len(hl.titles), flush=True)
    m = bars["minute_utc"]
    starts = [int(m[r.entry_minute]) for r in ds.rows]
    xw = np.array([hl.features_at(t) for t in starts])
    docs = [hl.text_before(t) for t in starts]
    sets = {
        "v2_news": ds.x["news"],
        "news_words": np.hstack([ds.x["news"], xw]),
        "words_only": xw,
    }
    y, yr, mv = ds.label, ds.year, ds.move
    # amendment 1: page titles exist only from 2019-09-22
    has_titles = np.array([r.day >= FIRST_DAY for r in ds.rows])
    fit = has_titles & (yr <= FIT_LAST)
    valid = np.isin(yr, VALID)
    train, test = has_titles & (yr <= TRAIN_LAST), np.isin(yr, TEST)
    print("fit", fit.sum(), "valid", valid.sum(), "test", test.sum(), flush=True)
    empty_days = int(sum(1 for d in docs if not d))

    # ---- diagnostic, no model, 2019-10 to 2022 only ----
    names = feature_names()
    umd = xw[:, names.index("hl24_up_minus_down")]
    q = np.quantile(umd[train], [0.2, 0.8])
    diag = {
        "bottom_fifth_buy_won": round(float(y[train & (umd <= q[0])].mean()), 4),
        "middle_buy_won": round(
            float(y[train & (umd > q[0]) & (umd < q[1])].mean()), 4
        ),
        "top_fifth_buy_won": round(float(y[train & (umd >= q[1])].mean()), 4),
        "all_buy_won": round(float(y[train].mean()), 4),
        "cut_points": [round(float(v), 3) for v in q],
    }
    print("diagnostic", diag, flush=True)

    # ---- tuning ------------------------------------------------------------------
    tuning: list[dict[str, Any]] = []
    for name, x in sets.items():
        for params in combos():
            p = clf(params).fit(x[fit], y[fit]).predict_proba(x[valid])[:, 1]
            tuning.append(
                {
                    "candidate": name,
                    "params": params,
                    "valid_log_loss": round(float(log_loss(y[valid], p)), 5),
                    "valid_accuracy": round(float(np.mean((p > 0.5) == y[valid])), 4),
                }
            )
    docs_a = np.array(docs, dtype=object)
    for c in TEXT_C:
        vec, lr = text_model(c)
        xf = vec.fit_transform(docs_a[fit])
        p = lr.fit(xf, y[fit]).predict_proba(vec.transform(docs_a[valid]))[:, 1]
        tuning.append(
            {
                "candidate": "headline_text",
                "params": {"C": c, "vocabulary": len(vec.vocabulary_)},
                "valid_log_loss": round(float(log_loss(y[valid], p)), 5),
                "valid_accuracy": round(float(np.mean((p > 0.5) == y[valid])), 4),
            }
        )
    tuning.sort(key=lambda d: d["valid_log_loss"])
    cands = ["v2_news", "news_words", "headline_text", "words_only"]
    best_each = {c: next(d for d in tuning if d["candidate"] == c) for c in cands}
    winner = tuning[0]["candidate"]
    print("best per candidate", best_each, flush=True)

    # ---- one look at 2023-2024 -----------------------------------------------------
    test_rows = [r for r, k in zip(ds.rows, test, strict=True) if k]
    results: dict[str, Any] = {}
    top_words: dict[str, list[str]] = {}
    for c, d in best_each.items():
        if c == "headline_text":
            vec, lr = text_model(d["params"]["C"])
            lr.fit(vec.fit_transform(docs_a[train]), y[train])
            p = lr.predict_proba(vec.transform(docs_a[test]))[:, 1]
            vocab = np.array(vec.get_feature_names_out())
            order = np.argsort(lr.coef_[0])
            top_words = {
                "before_gold_rose": list(vocab[order[::-1][:20]]),
                "before_gold_fell": list(vocab[order[:20]]),
            }
        else:
            model = clf(d["params"]).fit(sets[c][train], y[train])
            p = model.predict_proba(sets[c][test])[:, 1]
        res = summary(trades_for(bars, test_rows, p, costs))
        res2 = summary(trades_for(bars, test_rows, p, costs2))
        results[c] = {
            "params": d["params"],
            "valid_log_loss": d["valid_log_loss"],
            "valid_accuracy": d["valid_accuracy"],
            "test_log_loss": round(float(log_loss(y[test], p)), 5),
            "test_accuracy": round(float(np.mean((p > 0.5) == y[test])), 4),
            "trades": res,
            "net_usd_2x": res2.get("net_usd", 0.0),
        }
        print(c, results[c]["test_accuracy"], res.get("net_usd"), flush=True)
    always_buy = summary(trades_for(bars, test_rows, np.ones(int(test.sum())), costs))

    # ---- move size: v2 news vs news + headline words --------------------------------
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
    move: dict[str, Any] = {}
    for c in ("v2_news", "news_words"):
        x = sets[c]
        scored = []
        for params in small:
            pr = reg(params).fit(x[fit], mv[fit]).predict(x[valid])
            scored.append((float(r2_score(mv[valid], pr)), params))
        r2v, params = max(scored, key=lambda s: s[0])
        pr = reg(params).fit(x[train], mv[train]).predict(x[test])
        move[c] = {
            "valid_r2": round(r2v, 4),
            "test_r2": round(float(r2_score(mv[test], pr)), 4),
            "test_rank_corr": round(spearman(mv[test], pr), 4),
        }

    w = results[winner]
    t = w["trades"]
    passed = bool(
        w["valid_log_loss"] < 0.6931
        and t.get("trades", 0) >= 60
        and t["net_usd"] > 0
        and w["net_usd_2x"] >= 0
        and t["win_rate"] >= 0.5
        and t["net_usd"] > always_buy.get("net_usd", 0)
        and (
            winner == "v2_news"
            or t["net_usd"] > results["v2_news"]["trades"].get("net_usd", 0)
        )
    )
    payload = {
        "rules": "docs/xauusd-headlines-plan.md",
        "headlines_after_cleaning": len(hl.titles),
        "days_without_headlines": empty_days,
        "rows": {
            "fit_2019_10_2021": int(fit.sum()),
            "valid_2022": int(valid.sum()),
            "test_2023_2024": int(test.sum()),
        },
        "diagnostic_2019_2022": diag,
        "winner": winner,
        "results": results,
        "always_buy_test": always_buy,
        "move_size": move,
        "text_model_words": top_words,
        "top_tuning": tuning[:10],
        "passed": passed,
        "2025_2026": "not loaded",
    }
    OUT.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(payload))
    print("passed", passed)


def render_md(p: dict[str, Any]) -> str:
    d = p["diagnostic_2019_2022"]
    out = [
        "# Gold headlines vs the 08:00-12:00 New York direction",
        "",
        "Rules: `docs/xauusd-headlines-plan.md` (written before running). GDELT gold "
        "headlines (titles exist from 2019-09-22): "
        f"{p['headlines_after_cleaning']:,} after cleaning; "
        f"{p['days_without_headlines']} trading days had none in the 24 h before "
        "08:00. Tuned on 2019-10..2021 -> 2022, looked at once on 2023-2024 (third "
        "look at those years for news models). Log loss 0.693 = coin flip. Expensive "
        "costs. 2025-2026 not loaded.",
        "",
        f"Winner on 2022: **{p['winner']}**. Passed: "
        f"**{'yes' if p['passed'] else 'no'}**.",
        "",
        "## No model: does the headline mood line up with the move? (2019-10 to 2022)",
        "",
        "Share of days a buy won, split by the 24 h up-minus-down headline share:",
        "",
        "| Bottom fifth (most down) | Middle | Top fifth (most up) | All days |",
        "| ---: | ---: | ---: | ---: |",
        f"| {d['bottom_fifth_buy_won']:.1%} | {d['middle_buy_won']:.1%} | "
        f"{d['top_fifth_buy_won']:.1%} | {d['all_buy_won']:.1%} |",
        "",
        "## Direction",
        "",
        "| Candidate | 2022 log loss | 2022 right | 2023-24 log loss | "
        "2023-24 right | Trades | Win % | Net $ | Net $ at 2x |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for c, r in p["results"].items():
        t = r["trades"]
        out.append(
            f"| {c} | {r['valid_log_loss']:.4f} | {r['valid_accuracy']:.1%} | "
            f"{r['test_log_loss']:.4f} | {r['test_accuracy']:.1%} | "
            f"{t.get('trades', 0)} | {t.get('win_rate', 0):.0%} | "
            f"{t.get('net_usd', 0):.0f} | {r['net_usd_2x']:.0f} |"
        )
    ab = p["always_buy_test"]
    out += [
        f"| always buy (2023-24) | | | | | {ab['trades']} | {ab['win_rate']:.0%} | "
        f"{ab['net_usd']:.0f} | |",
        "",
        "## Move size 2023-2024 (range in ADR units)",
        "",
        "| Inputs | 2022 R-squared | 2023-24 R-squared | 2023-24 rank corr |",
        "| --- | ---: | ---: | ---: |",
    ]
    for c, r in p["move_size"].items():
        out.append(
            f"| {c} | {r['valid_r2']:+.3f} | {r['test_r2']:+.3f} | "
            f"{r['test_rank_corr']:+.3f} |"
        )
    tw = p["text_model_words"]
    if tw:
        out += [
            "",
            "## What the headline text model learned (fitted on 2019-10..2022)",
            "",
            "Words before gold rose: " + ", ".join(tw["before_gold_rose"]),
            "",
            "Words before gold fell: " + ", ".join(tw["before_gold_fell"]),
        ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
