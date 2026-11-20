"""How do the news-day trades sit against support and resistance?

Levels (trading_bot.backtesting.levels): yesterday's high and low, and today's high
and low before the news. For every news-day trade on 2014-2024 (momentum versions,
corrected clock) this measures:

* room: distance from the entry to the first level ahead, in R (R = entry to stop);
* protected: whether a level sits between the entry and the stop;
* whether price reached the first level ahead and then turned back.

This is a diagnosis on development data only, not a new rule: any rule built from
it must be written down first and then pass the untouched 2025 check.

Writes docs/xauusd-news-levels.{json,md}.
Usage: PYTHONPATH=src .venv/bin/python scripts/study_xauusd_news_levels.py
"""

import json
import statistics
from pathlib import Path
from typing import Any

import numpy as np

from trading_bot.backtesting.levels import key_levels, protected, room
from trading_bot.backtesting.news_day import NewsRule, load_events, run_news
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import (
    Array,
    CostModel,
    Sizing,
    load_bars,
)
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.backtesting.trade_replay import cost_split
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT = Path("docs/xauusd-news-levels")
DEV = range(2014, 2025)
RULES = [NewsRule("momentum", None), NewsRule("momentum", 2.0)]
ROOM_BUCKETS = ["under 1R", "1R to 2R", "2R or more", "no level ahead"]
TURN_BACK_R = 0.5  # "turned back": after touching the level, price fell 0.5R away


def bucket(r: float | None) -> str:
    if r is None:
        return "no level ahead"
    return "under 1R" if r < 1 else "1R to 2R" if r < 2 else "2R or more"


def analyse(
    bars: dict[str, Array],
    trades: list[HoldTrade],
    days: list[Any],
    costs: CostModel,
    release: dict[Any, int],
) -> list[dict[str, Any]]:
    index = {d.day: k for k, d in enumerate(days)}
    mid_h = (bars["bid_high"] + bars["ask_high"]) / 2
    mid_l = (bars["bid_low"] + bars["ask_low"]) / 2
    rows = []
    for t in trades:
        k = index.get(t.day)
        if k is None or k < 1:
            continue
        c = cost_split(bars, t, costs, exit_at_close=t.exit_reason == "time_exit")
        d = t.direction
        risk = abs(c.entry_mid - t.stop)
        # levels known before the news: everything up to the release minute
        at = int(np.searchsorted(bars["minute_utc"], release[t.day]))
        levels = key_levels(bars, days, k, at)
        rm = room(levels, c.entry_mid, d)
        path_hi = mid_h[t.entry_minute : t.exit_bar + 1]
        path_lo = mid_l[t.entry_minute : t.exit_bar + 1]
        fav = (path_hi.max() - c.entry_mid) if d == 1 else (c.entry_mid - path_lo.min())
        reached = rm is not None and fav >= rm
        turned = False
        if reached and rm is not None:
            lvl = c.entry_mid + d * rm
            fav_path = path_hi if d == 1 else path_lo
            first = int(np.argmax((fav_path - lvl) * d >= 0))
            later = (
                path_lo[first:].min() if d == 1 else path_hi[first:].max()
            )  # worst price after touching the level
            turned = (lvl - later) * d >= TURN_BACK_R * risk
        rows.append(
            {
                "day": t.day.isoformat(),
                "room_r": None if rm is None else round(rm / risk, 2),
                "bucket": bucket(None if rm is None else rm / risk),
                "protected": protected(levels, c.entry_mid, t.stop),
                "reached_level": reached,
                "turned_at_level": turned,
                "gross_per_oz": round((c.exit_mid - c.entry_mid) * d, 3),
                "gross_r": round((c.exit_mid - c.entry_mid) * d / risk, 3),
                "net_usd": round(t.pnl_usd, 2),
                "reason": t.exit_reason,
            }
        )
    return rows


def group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"trades": 0}
    g = [r["gross_per_oz"] for r in rows]
    t = (
        statistics.mean(g) / statistics.stdev(g) * len(g) ** 0.5
        if len(g) > 2 and statistics.stdev(g)
        else 0.0
    )
    return {
        "trades": len(rows),
        "win_rate": round(float(np.mean([r["net_usd"] > 0 for r in rows])), 3),
        "gross_per_oz": round(statistics.mean(g), 3),
        "t_stat": round(t, 2),
        "gross_r": round(statistics.mean(r["gross_r"] for r in rows), 3),
        "net_per_trade": round(statistics.mean(r["net_usd"] for r in rows), 2),
        "net_usd": round(sum(r["net_usd"] for r in rows), 2),
        "stopped": round(float(np.mean([r["reason"] == "stop" for r in rows])), 3),
    }


def main() -> None:
    costs = CostModel.from_yaml(COSTS_YAML)
    bars = load_bars(BARS_DIR, 201401, 202412)
    days = build_days(bars)
    events = load_events()
    out: dict[str, Any] = {
        "levels": "yesterday's high/low, today's high/low before " "the news",
        "dev_years": [2014, 2024],
        "rules": {},
    }
    for rule in RULES:
        trades, _ = run_news(bars, events, rule, costs, Sizing(), DEV)
        rows = analyse(bars, trades, days, costs, {e.day: e.utc() for e in events})
        reached = [r for r in rows if r["reached_level"]]
        out["rules"][rule.name] = {
            "all": group(rows),
            "by_room": {
                b: group([r for r in rows if r["bucket"] == b]) for b in ROOM_BUCKETS
            },
            "by_protection": {
                "stop behind a level": group([r for r in rows if r["protected"]]),
                "no level between entry and stop": group(
                    [r for r in rows if not r["protected"]]
                ),
            },
            "reached_first_level": round(len(reached) / len(rows), 3) if rows else 0,
            "turned_back_after_reaching": (
                round(float(np.mean([r["turned_at_level"] for r in reached])), 3)
                if reached
                else 0.0
            ),
            "median_room_r": statistics.median(
                r["room_r"] for r in rows if r["room_r"] is not None
            ),
            "share_no_level_ahead": round(
                float(np.mean([r["room_r"] is None for r in rows])), 3
            ),
        }
        print(rule.name, json.dumps(out["rules"][rule.name]["by_room"]), flush=True)
    OUT.with_suffix(".json").write_text(json.dumps(out, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(out))
    print("wrote", OUT)


def render_md(out: dict[str, Any]) -> str:
    L = [
        "# News-day trades against support and resistance",
        "",
        "Levels: yesterday's high and low, and today's high and low before the news "
        "(17:00-17:00 New York trading day, mid prices). Room = distance from entry "
        "to the first level ahead, in R (R = entry to stop). 2014-2024, corrected "
        "clock, expensive costs. Diagnosis only: no rule here has been tested on "
        "unseen data.",
        "",
    ]
    for name, r in out["rules"].items():
        L += [
            f"## {name}",
            "",
            f"Median room to the first level: {r['median_room_r']:.2f}R; no level "
            f"ahead in {r['share_no_level_ahead']:.0%} of trades. Price reached the "
            f"first level in {r['reached_first_level']:.0%} of trades and, of those, "
            f"turned back by at least {TURN_BACK_R}R in "
            f"{r['turned_back_after_reaching']:.0%}.",
            "",
            "| Group | Trades | Win % | Stopped % | Gross $/oz | t | Gross R | "
            "Net $/trade | Net $ |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        groups = [("All trades", r["all"])]
        groups += [(f"Room: {b}", g) for b, g in r["by_room"].items()]
        groups += [(f"{b[0].upper()}{b[1:]}", g) for b, g in r["by_protection"].items()]
        for label, g in groups:
            if not g["trades"]:
                L.append(f"| {label} | 0 | | | | | | | |")
                continue
            L.append(
                f"| {label} | {g['trades']} | {g['win_rate']:.0%} | "
                f"{g['stopped']:.0%} | {g['gross_per_oz']:+.2f} | {g['t_stat']:+.1f} | "
                f"{g['gross_r']:+.2f} | {g['net_per_trade']:.2f} | "
                f"{g['net_usd']:,.0f} |"
            )
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
