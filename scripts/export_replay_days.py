"""Export random practice days (2014-2022 only) for the replay page.

Each day: 15-minute candles of the previous New York day (context) and 5-minute
candles of the day itself (17:00 -> 16:45 New York), mid prices; times are New York
wall-clock written as UTC seconds so the chart shows New York time. Plus the 20-day
average daily range (ADR), yesterday's high/low and the median recorded spread.
2023-2026 are never loaded. Writes tools/replay/days.json.
Usage: PYTHONPATH=src .venv/bin/python scripts/export_replay_days.py
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from trading_bot.backtesting.news_day import NY
from trading_bot.backtesting.session_window import load_bars
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.data.histdata_bulk import BARS_DIR

OUT = Path("tools/replay/days.json")
N_DAYS, SEED = 80, 2026


def ny_wall(t: int) -> int:
    lt = datetime.fromtimestamp(t, NY).replace(tzinfo=UTC)
    return int(lt.timestamp())


def bucket(m, o, h, lo, c, i0: int, i1: int, minutes: int) -> list[list[float]]:
    keys = np.array([ny_wall(int(t)) // (minutes * 60) for t in m[i0:i1]])
    out = []
    start = 0
    for k in range(1, len(keys) + 1):
        if k == len(keys) or keys[k] != keys[start]:
            a, b = i0 + start, i0 + k
            out.append(
                [
                    int(keys[start]) * minutes * 60,
                    round(float(o[a]), 2),
                    round(float(h[a:b].max()), 2),
                    round(float(lo[a:b].min()), 2),
                    round(float(c[b - 1]), 2),
                ]
            )
            start = k
    return out


def main() -> None:
    bars = load_bars(BARS_DIR, 201401, 202212)
    days = build_days(bars)
    m = bars["minute_utc"]
    mid = {
        p: (bars[f"bid_{p}"] + bars[f"ask_{p}"]) / 2
        for p in ("open", "high", "low", "close")
    }
    spread = bars["ask_open"] - bars["bid_open"]
    rng = np.random.default_rng(SEED)
    pick = sorted(rng.choice(np.arange(21, len(days)), N_DAYS, replace=False))
    out = []
    for k in pick:
        d, y = days[k], days[k - 1]
        if d.i1 - d.i0 < 1000:
            continue
        adr = float(np.mean([x.high - x.low for x in days[k - 20 : k]]))
        args = (m, mid["open"], mid["high"], mid["low"], mid["close"])
        out.append(
            {
                "date": d.day.isoformat(),
                "weekday": d.day.strftime("%A"),
                "adr": round(adr, 2),
                "yHigh": round(y.high, 2),
                "yLow": round(y.low, 2),
                "spread": round(float(np.median(spread[d.i0 : d.i1])), 2),
                "prev": bucket(*args, y.i0, y.i1, 15),
                "day": bucket(*args, d.i0, d.i1, 5),
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(len(out), "days", OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
