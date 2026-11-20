"""Build a candle-by-candle replay page of every news-day trade in one year.

Uses the rules in trading_bot.backtesting.news_day. Only 2014-2024 can be
replayed; 2025 and 2026 stay unseen.

Usage:
  PYTHONPATH=src .venv/bin/python scripts/replay_xauusd_news.py \
      [--year 2024] [--side momentum|fade] [--target 2]
Writes docs/replays/xauusd-news-<side>-<exit>-<year>.html
"""

import argparse
from pathlib import Path

import numpy as np

from trading_bot.backtesting.news_day import NewsRule, load_events, run_news
from trading_bot.backtesting.session_window import CostModel, Sizing, load_bars
from trading_bot.backtesting.trade_replay import (
    Highlight,
    ReplayContext,
    render_page,
    replay_record,
)
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT_DIR = Path("docs/replays")
LAST_DEV_YEAR = 2024
BEFORE_MIN = 90
AFTER_MIN = 30
LABEL = {"nfp": "jobs report", "cpi": "inflation (CPI)", "fomc": "Fed decision"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=LAST_DEV_YEAR)
    ap.add_argument("--side", choices=("momentum", "fade"), default="momentum")
    ap.add_argument("--target", type=float, default=None)
    a = ap.parse_args()
    if not 2014 <= a.year <= LAST_DEV_YEAR:
        raise SystemExit("only development years 2014-2024 can be replayed")

    rule = NewsRule(a.side, a.target)
    costs = CostModel.from_yaml(COSTS_YAML)
    bars = load_bars(BARS_DIR, a.year * 100 + 1, a.year * 100 + 12)
    events = load_events()
    kind = {e.day: e for e in events}
    trades, _ = run_news(bars, events, rule, costs, Sizing(), range(a.year, a.year + 1))
    n = len(bars["minute_utc"])

    records = []
    for t in trades:
        ev = kind[t.day]
        release_first = int(np.searchsorted(bars["minute_utc"], ev.utc()))
        ctx = ReplayContext(
            highlights=(
                Highlight(
                    release_first,
                    t.entry_minute - 1,
                    "NEWS",
                    f"The {LABEL[ev.kind]} came out at {ev.at:%H:%M}. This 15-minute "
                    "candle sets the direction; entry is at the next candle's open.",
                ),
            )
        )
        records.append(
            replay_record(
                bars,
                t,
                costs,
                exit_at_close=t.exit_reason == "time_exit",
                window=(
                    max(0, release_first - BEFORE_MIN),
                    min(n, t.exit_bar + AFTER_MIN),
                ),
                context=ctx,
            )
        )

    stop_text = (
        "Stop just past the news candle's other end (its low for a buy, high for a "
        "sell)."
        if a.side == "momentum"
        else "Stop just past the news candle's extreme (its high for a sell, low for a "
        "buy)."
    )
    exit_text = (
        "Exit only at the time limit: 12:00 New York for 08:30 news, 16:45 for the Fed."
        if a.target is None
        else f"Exit at {a.target:g} times the risk, or at the time limit (12:00 New "
        "York for 08:30 news, 16:45 for the Fed)."
    )
    html = render_page(
        title=f"News-Day Replay {a.year}",
        subtitle=(
            f"Gold traded only on big US news days, at most once a day ({rule.name}). "
            f"All {len(trades)} trades in {a.year}. 5-minute mid-price candles, New "
            "York time. $3,000 account, $30 risk per trade, expensive costs."
        ),
        rules=[
            "Only days with the US jobs report or inflation (CPI) at 08:30 New York, "
            "or a scheduled Fed decision at 14:00.",
            "The 15-minute candle that starts at the release sets the direction: up if "
            "it closes higher than it opened, down if lower.",
            (
                "Trade in that direction"
                if a.side == "momentum"
                else "Trade against that direction"
            )
            + " at the next candle's open (08:45 or 14:15).",
            stop_text + " The stop is a normal stop order that fills on touch.",
            exit_text,
        ],
        records=records,
        all_trades=trades,
        note="Account starts at $3,000.",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"xauusd-news-{rule.name.replace('/', '-')}-{a.year}.html"
    out.write_text(html)
    print(f"wrote {out} ({len(records)} trades)")


if __name__ == "__main__":
    main()
