"""Build a candle-by-candle replay page for the YouTube sweep strategy.

Picks trades at random from one development year (so wins and losses appear about
as often as they really did) and writes a self-contained HTML page with Play /
Step controls, the zone, sweep and confirmation candles, entry / stop / target /
exit, a live profit-or-loss, a cost breakdown per trade, and the running total of
every trade that year. Only 2014-2024 can be replayed; 2025 and 2026 stay unseen.

Usage:
  PYTHONPATH=src .venv/bin/python scripts/replay_xauusd_sweep.py \
      [--year 2024] [--target 2] [--stop close|touch] [--trend] [--trail]
      [--count 30] [--seed 7]
Writes docs/replays/xauusd-sweep-<rule name>-<year>.html
"""

import argparse
import random
from pathlib import Path

from trading_bot.backtesting.session_window import CostModel, Sizing, load_bars
from trading_bot.backtesting.sweep_strategy import SweepRule, build_days, run_sweep
from trading_bot.backtesting.trade_replay import (
    render_page,
    replay_record,
    sweep_context,
)
from trading_bot.data.histdata_bulk import BARS_DIR

COSTS_YAML = Path("config/xauusd_costs_expensive.yaml")
OUT_DIR = Path("docs/replays")
LAST_DEV_YEAR = 2024
BEFORE_MIN = 180  # minutes of chart before the entry
AFTER_MIN = 45  # minutes of chart after the exit


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=LAST_DEV_YEAR)
    ap.add_argument("--target", type=float, default=2.0)
    ap.add_argument("--stop", choices=("close", "touch"), default="close")
    ap.add_argument("--trend", action="store_true", help="20-hour trend filter")
    ap.add_argument("--trail", action="store_true", help="moving stop after 1R")
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    if not 2014 <= a.year <= LAST_DEV_YEAR:
        raise SystemExit("only development years 2014-2024 can be replayed")

    rule = SweepRule(a.target, a.stop, trend_filter=a.trend, trail=a.trail)
    costs = CostModel.from_yaml(COSTS_YAML)
    # one month before the year so the first day has a previous day for its zones
    bars = load_bars(BARS_DIR, (a.year - 1) * 100 + 12, a.year * 100 + 12)
    days = build_days(bars)
    index = {d.day: k for k, d in enumerate(days)}
    trades, _ = run_sweep(bars, days, rule, costs, Sizing(), range(a.year, a.year + 1))
    rng = random.Random(a.seed)
    picked = sorted(
        rng.sample(trades, min(a.count, len(trades))), key=lambda t: t.entry_minute
    )

    records = []
    for t in picked:
        k = index[t.day]
        day = days[k]
        window = (
            max(day.i0, t.entry_minute - BEFORE_MIN),
            min(day.i1, t.exit_bar + AFTER_MIN),
        )
        at_close = t.exit_reason == "time_exit" or (
            t.exit_reason == "stop" and rule.stop_mode == "close"
        )
        records.append(
            replay_record(
                bars,
                t,
                costs,
                exit_at_close=at_close,
                window=window,
                context=sweep_context(bars, days, k, t),
            )
        )

    stop_text = (
        "The stop only counts when a 15-minute candle closes past it."
        if rule.stop_mode == "close"
        else "The stop is a normal stop order that fills when price touches it."
    )
    html = render_page(
        title=f"Sweep Replay {a.year}",
        subtitle=(
            f"YouTube liquidity-sweep strategy, {rule.name}. {len(picked)} trades "
            f"picked at random from all {len(trades)} trades in {a.year}. "
            "5-minute mid-price candles, New York time. $3,000 account, $30 risk "
            "per trade, expensive costs."
        ),
        rules=[
            "Yesterday's upper wick is the sell zone; the lower wick is the buy zone.",
            "A 15-minute candle pokes past the previous candle's high (sells) or "
            "low (buys) inside the zone and closes back (the sweep).",
            "Within 4 candles, a candle closes beyond the sweep candle's other end "
            "(the confirmation). Entry is at the next candle's open.",
            f"Stop just beyond the sweep candle's extreme; target {a.target:g} times "
            f"the risk. {stop_text}",
            "No new trades after 16:00 New York; anything open is closed at 16:45.",
        ]
        + (
            [
                "Trend filter: sell only if the confirmation candle closes below the "
                "20-hour moving average of hourly closes; buy only if above it."
            ]
            if rule.trend_filter
            else []
        )
        + (
            [
                "Moving stop: once the trade is 1R in profit, a normal stop follows "
                "price 1R behind the best level reached."
            ]
            if rule.trail
            else []
        ),
        records=records,
        all_trades=trades,
        note="Account starts at $3,000.",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = rule.name.replace("/", "-").replace("+", "-")
    out = OUT_DIR / f"xauusd-sweep-{slug}-{a.year}.html"
    out.write_text(html)
    print(f"wrote {out} ({len(records)} trades replayed, {len(trades)} in year)")


if __name__ == "__main__":
    main()
