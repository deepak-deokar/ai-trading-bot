"""Candle patterns at every hour, with 30-minute to 4-hour holds.

Inputs and labels: trading_bot.backtesting.candle_dataset (last 24 five-minute
candles, last 24 hourly candles with what happened inside each hour, time of
day, weekday, volatility). One gradient-boosted tree model per holding time
(30, 60, 120, 240 minutes) over all decision hours together.

Fixed before running:
* fit on 2014..2020, choose on 2021..2022, look once at 2023..2024 (model
  refitted on 2014..2022);
* settings per holding time chosen by 2021-22 log loss from: depth 3/5, at
  least 300/1500 rows per leaf, 200/500 rounds (learning rate 0.05, 30% of
  inputs per split, L2 1);
* trade: buy if P(buy wins) >= 0.55, sell if <= 0.45, 1:1 stop/target R =
  0.5 x ADR x sqrt(hold / 240), normal stops, closed at the end of the hold;
* hour + hold cells kept for 2023-24: at least 20 trades, profitable and at
  least 50% winners on 2021-22.
Pass: the kept cells together are profitable on 2023-24 after expensive costs,
also at 2x costs, with at least 50% winners. 2025-2026 never loaded.

Writes docs/xauusd-candle-ml.{json,md} and docs/xauusd-candle-ml-heatmap.html.
Usage: PYTHONPATH=src:scripts .venv/bin/python scripts/study_xauusd_candles.py
"""

import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss
from study_xauusd_news_model import summary  # type: ignore[import-not-found]

from trading_bot.backtesting.candle_dataset import (
    DECISION_HOURS,
    HOLDS,
    CandleRows,
    build,
)
from trading_bot.backtesting.news_day import execute
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, Sizing, load_bars
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-candle-ml")
HEATMAP = Path("docs/xauusd-candle-ml-heatmap.html")
FIT_LAST, VALID = 2020, (2021, 2022)
TRAIN_LAST, TEST = 2022, (2023, 2024)
MARGIN = 0.05
SEED = 7
GRID = {"max_depth": (3, 5), "min_samples_leaf": (300, 1500), "max_iter": (200, 500)}
MIN_CELL_TRADES = 20
HOUR_ORDER = list(DECISION_HOURS)


def clf(params: dict[str, Any]) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_features=0.3,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=SEED,
        **params,
    )


def simulate(
    bars: dict[str, Array],
    rows: CandleRows,
    sel: Array,
    p: Array,
    hold: int,
    costs: CostModel,
) -> list[tuple[int, HoldTrade]]:
    """(decision hour, trade) for each selected row the model is confident on."""
    out = []
    for i, q in zip(np.flatnonzero(sel), p, strict=True):
        d = 1 if q >= 0.5 + MARGIN else -1 if q <= 0.5 - MARGIN else 0
        if not d:
            continue
        t = execute(
            bars,
            rows.day[i],
            int(rows.entry_minute[i]),
            int(rows.last_minute[hold][i]),
            d,
            costs,
            Sizing(),
            risk=float(rows.risk[hold][i]),
            target_r=1.0,
        )
        if t is not None:
            out.append((int(rows.hour[i]), t))
    return out


def by_cell(trades: list[tuple[int, HoldTrade]]) -> dict[int, dict[str, Any]]:
    cells: dict[int, list[HoldTrade]] = {}
    for h, t in trades:
        cells.setdefault(h, []).append(t)
    return {h: summary(v) for h, v in cells.items()}


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    stress = CostModel.from_yaml(COSTS_YAML, multiplier=2.0)
    bars = load_bars(BARS_DIR, 201401, 202412)
    days = build_days(bars)
    rows = build(bars, days, range(2014, 2025))
    yr = rows.year
    print("rows", rows.x.shape, flush=True)
    report: dict[str, Any] = {"holds": {}}
    kept_test: list[HoldTrade] = []
    kept_test_2x: list[HoldTrade] = []
    kept_valid: list[HoldTrade] = []
    heat: dict[str, dict[str, Any]] = {"valid": {}, "test": {}}
    for hold in HOLDS:
        ok = rows.label[hold] >= 0
        y = rows.label[hold]
        fit, valid = ok & (yr <= FIT_LAST), ok & np.isin(yr, VALID)
        train, test = ok & (yr <= TRAIN_LAST), ok & np.isin(yr, TEST)
        tuning = []
        for combo in itertools.product(*GRID.values()):
            params = dict(zip(GRID, combo, strict=True))
            mdl = clf(params).fit(rows.x[fit], y[fit])
            pv = mdl.predict_proba(rows.x[valid])[:, 1]
            pf = mdl.predict_proba(rows.x[fit])[:, 1]
            tuning.append(
                {
                    "params": params,
                    "valid_log_loss": float(log_loss(y[valid], pv)),
                    "valid_accuracy": float(np.mean((pv > 0.5) == (y[valid] == 1))),
                    "fit_accuracy": float(np.mean((pf > 0.5) == (y[fit] == 1))),
                    "_pv": pv,
                }
            )
        best = min(tuning, key=lambda d: d["valid_log_loss"])
        cells_v = by_cell(simulate(bars, rows, valid, best["_pv"], hold, costs))
        kept = [
            h
            for h, v in cells_v.items()
            if v["trades"] >= MIN_CELL_TRADES
            and v["net_usd"] > 0
            and v["win_rate"] >= 0.5
        ]
        for h, t in simulate(bars, rows, valid, best["_pv"], hold, costs):
            if h in kept:
                kept_valid.append(t)
        # one look at 2023-2024
        mdl = clf(best["params"]).fit(rows.x[train], y[train])
        pt = mdl.predict_proba(rows.x[test])[:, 1]
        trades_t = simulate(bars, rows, test, pt, hold, costs)
        trades_t2 = simulate(bars, rows, test, pt, hold, stress)
        cells_t = by_cell(trades_t)
        kept_test += [t for h, t in trades_t if h in kept]
        kept_test_2x += [t for h, t in trades_t2 if h in kept]
        heat["valid"][str(hold)] = {str(h): v for h, v in cells_v.items()}
        heat["test"][str(hold)] = {str(h): v for h, v in cells_t.items()}
        report["holds"][str(hold)] = {
            "params": best["params"],
            "fit_accuracy": round(best["fit_accuracy"], 4),
            "valid_accuracy": round(best["valid_accuracy"], 4),
            "valid_log_loss": round(best["valid_log_loss"], 5),
            "test_accuracy": round(float(np.mean((pt > 0.5) == (y[test] == 1))), 4),
            "test_log_loss": round(float(log_loss(y[test], pt)), 5),
            "valid_all": summary(
                [t for _, t in simulate(bars, rows, valid, best["_pv"], hold, costs)]
            ),
            "test_all": summary([t for _, t in trades_t]),
            "kept_hours": sorted(kept, key=HOUR_ORDER.index),
        }
        r = report["holds"][str(hold)]
        print(
            hold,
            r["params"],
            "fit",
            r["fit_accuracy"],
            "valid",
            r["valid_accuracy"],
            "test",
            r["test_accuracy"],
            "kept",
            r["kept_hours"],
            "test all net",
            r["test_all"].get("net_usd"),
            flush=True,
        )
    report["kept_cells_2021_2022"] = summary(kept_valid)
    report["kept_cells_2023_2024"] = summary(kept_test)
    report["kept_cells_2023_2024_at_2x"] = summary(kept_test_2x)
    kt = report["kept_cells_2023_2024"]
    k2 = report["kept_cells_2023_2024_at_2x"]
    report["passed"] = bool(
        kt.get("trades", 0) > 0
        and kt["net_usd"] > 0
        and k2["net_usd"] > 0
        and kt["win_rate"] >= 0.5
    )
    report["heat"] = heat
    report["2025_2026"] = "not loaded"
    print(
        "kept cells test",
        kt.get("trades"),
        kt.get("win_rate"),
        kt.get("net_usd"),
        "2x",
        k2.get("net_usd"),
        "passed",
        report["passed"],
        flush=True,
    )
    OUT.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(report))
    HEATMAP.write_text(render_heatmap(report))
    print("wrote", OUT, HEATMAP)


def fmt(x: float) -> str:
    return f"{x:,.0f}"


def render_md(r: dict[str, Any]) -> str:
    L = [
        "# Candle patterns at every hour (train 2014-2020, choose 2021-22, test "
        "2023-24)",
        "",
        "Inputs: last 24 five-minute candles and last 24 hourly candles (with the "
        "share of green 5-minute candles and choppiness inside each hour), time of "
        "day, weekday, volatility; all in units of the 20-day average daily range. "
        "Decision every hour 18:00-15:00 New York; 1:1 trade with R = 0.5 x ADR x "
        "sqrt(hold/240), out at the end of the hold (by 16:45). Trade when the "
        "model gives >= 55% to one side. Expensive costs, $30 risk on $3,000. "
        "2025-2026 not loaded.",
        "",
        "## Direction right, by holding time",
        "",
        "| Hold | Settings (depth / rows per leaf / rounds) | Fit years | 2021-22 | "
        "2023-24 | 2021-22 net $ (all hours) | 2023-24 net $ (all hours) | "
        "Hours kept from 2021-22 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for h, v in r["holds"].items():
        p = v["params"]
        L.append(
            f"| {h} min | {p['max_depth']} / {p['min_samples_leaf']} / "
            f"{p['max_iter']} | {v['fit_accuracy']:.1%} | {v['valid_accuracy']:.1%} | "
            f"{v['test_accuracy']:.1%} | {fmt(v['valid_all'].get('net_usd', 0))} | "
            f"{fmt(v['test_all'].get('net_usd', 0))} | "
            f"{', '.join(f'{x:02d}:00' for x in v['kept_hours']) or 'none'} |"
        )
    kv, kt, k2 = (
        r["kept_cells_2021_2022"],
        r["kept_cells_2023_2024"],
        r["kept_cells_2023_2024_at_2x"],
    )
    L += [
        "",
        "## Kept hour + hold cells together",
        "",
        "| Period | Trades | Win % | Net $/trade | Net $ |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, v in (
        ("2021-22 (where they were chosen)", kv),
        ("2023-24", kt),
        ("2023-24 at 2x costs", k2),
    ):
        if v.get("trades"):
            L.append(
                f"| {name} | {v['trades']} | {v['win_rate']:.0%} | "
                f"{v['avg_per_trade']:.2f} | {fmt(v['net_usd'])} |"
            )
        else:
            L.append(f"| {name} | 0 | | | |")
    L += [
        "",
        f"Passed: **{'yes' if r['passed'] else 'no'}**. Heat map: "
        "`docs/xauusd-candle-ml-heatmap.html`.",
        "",
    ]
    return "\n".join(L)


def render_heatmap(r: dict[str, Any]) -> str:
    data = json.dumps(
        {
            "heat": r["heat"],
            "hours": HOUR_ORDER,
            "holds": list(HOLDS),
            "holdsInfo": r["holds"],
        }
    )
    return HEAT_TEMPLATE.replace("__DATA__", data)


HEAT_TEMPLATE = (Path(__file__).parent / "candle_heatmap_template.html").read_text()


if __name__ == "__main__":
    main()
