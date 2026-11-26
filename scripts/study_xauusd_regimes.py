"""How gold behaved inside the trading day, year by year and by trend state.

Descriptive only (no trading rule, no costs). For every New York trading day
(17:00-17:00) 2014-2024, mid-price moves in four sessions (New York time):
  asia     18:00-03:00
  london   03:00-08:00
  ny_am    08:00-12:00
  ny_pm    12:00-16:45
Moves are in units of the 20-day average daily range (ADR) known before the day.
Trend state uses only past daily closes: yesterday's close vs its 50-day average,
and the 20-day change. 2025-2026 are never loaded.

Writes docs/xauusd-regimes.{json,md}.
Usage: PYTHONPATH=src .venv/bin/python scripts/study_xauusd_regimes.py
"""

import json
from datetime import datetime, time
from pathlib import Path
from typing import Any

import numpy as np

from trading_bot.backtesting.news_day import NY
from trading_bot.backtesting.session_window import load_bars
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.data.histdata_bulk import BARS_DIR

OUT = Path("docs/xauusd-regimes")
SESSIONS = {
    "asia": (time(18), time(3)),
    "london": (time(3), time(8)),
    "ny_am": (time(8), time(12)),
    "ny_pm": (time(12), time(16, 45)),
}


def stats(v: list[float]) -> dict[str, float]:
    a = np.array(v)
    if len(a) < 2:
        return {"n": len(a)}
    return {
        "n": len(a),
        "avg_adr": round(float(a.mean()), 4),
        "t": round(float(a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))), 2),
        "up_share": round(float(np.mean(a > 0)), 3),
    }


def main() -> None:
    bars = load_bars(BARS_DIR, 201401, 202412)
    days = build_days(bars)
    m = bars["minute_utc"]
    mo = (bars["bid_open"] + bars["ask_open"]) / 2
    rows: list[dict[str, Any]] = []
    closes = [d.close for d in days]
    ranges = [d.high - d.low for d in days]
    for k, d in enumerate(days):
        if k < 50:
            continue
        adr = float(np.mean(ranges[k - 20 : k]))
        ma50 = float(np.mean(closes[k - 50 : k]))
        prev = closes[k - 1]
        chg20 = (prev - closes[k - 21]) / adr
        moves: dict[str, float] = {}
        for name, (a, b) in SESSIONS.items():
            start_day = d.day if a < time(17) else None
            ta = _ts(d.day, a, prev_evening=start_day is None)
            tb = _ts(d.day, b, prev_evening=False)
            i = int(np.searchsorted(m, ta))
            j = int(np.searchsorted(m, tb))
            if i < d.i0 or j >= d.i1 or j <= i:
                break
            moves[name] = (float(mo[j]) - float(mo[i])) / adr
        else:
            rows.append(
                {
                    "year": d.day.year,
                    "adr": adr,
                    "above_ma50": prev > ma50,
                    "chg20": chg20,
                    "day_move": (d.close - d.open) / adr,
                    "big_day": (d.high - d.low) / adr > 2.0,
                    **moves,
                }
            )
    cols = [*SESSIONS, "day_move"]

    def group(sel: list[dict[str, Any]]) -> dict[str, Any]:
        return {c: stats([r[c] for r in sel]) for c in cols}

    by_year: dict[str, Any] = {}
    for y in range(2014, 2025):
        sel = [r for r in rows if r["year"] == y]
        first = next(d for d in days if d.day.year == y)
        last = [d for d in days if d.day.year == y][-1]
        by_year[str(y)] = {
            "year_change_pct": round(100 * (last.close / first.open - 1), 1),
            "avg_adr_usd": round(float(np.mean([r["adr"] for r in sel])), 2),
            "big_range_days_pct": round(
                100 * float(np.mean([r["big_day"] for r in sel])), 1
            ),
            **group(sel),
        }
    q = np.quantile([r["chg20"] for r in rows], [1 / 3, 2 / 3])
    trend = {
        "above_50d_average": group([r for r in rows if r["above_ma50"]]),
        "below_50d_average": group([r for r in rows if not r["above_ma50"]]),
        "20d_change_top_third": group([r for r in rows if r["chg20"] >= q[1]]),
        "20d_change_middle": group([r for r in rows if q[0] < r["chg20"] < q[1]]),
        "20d_change_bottom_third": group([r for r in rows if r["chg20"] <= q[0]]),
    }
    periods = {
        "2014-2018": [r for r in rows if r["year"] <= 2018],
        "2019-2022": [r for r in rows if 2019 <= r["year"] <= 2022],
        "2023-2024": [r for r in rows if r["year"] >= 2023],
    }
    trend_by_period = {
        p: {
            "above_50d_average": group([r for r in sel if r["above_ma50"]]),
            "below_50d_average": group([r for r in sel if not r["above_ma50"]]),
        }
        for p, sel in periods.items()
    }
    payload = {
        "days": len(rows),
        "by_year": by_year,
        "by_trend_state": trend,
        "trend_by_period": trend_by_period,
        "2025_2026": "not loaded",
    }
    OUT.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    OUT.with_suffix(".md").write_text(render_md(payload))
    print(OUT.with_suffix(".md").read_text())


def _ts(day: Any, at: time, prev_evening: bool) -> int:
    from datetime import timedelta

    base = day - timedelta(days=1) if prev_evening else day
    return int(datetime.combine(base, at, tzinfo=NY).timestamp())


def cell(s: dict[str, Any]) -> str:
    if "avg_adr" not in s:
        return "-"
    return f"{s['avg_adr']:+.3f} (t {s['t']:+.1f}, {s['up_share']:.0%} up)"


def render_md(p: dict[str, Any]) -> str:
    cols = [*SESSIONS, "day_move"]
    head = "| Asia 18-03 | London 03-08 | NY 08-12 | NY 12-16:45 | Whole day |"
    sep = "| ---: | ---: | ---: | ---: | ---: |"
    out = [
        "# Gold inside the day: by year and by trend state (2014-2024)",
        "",
        f"Descriptive, no trading rule, no costs. {p['days']} New York trading days. "
        "Session moves are mid-price changes in units of the 20-day average daily "
        "range (ADR) known before the day; t = average / standard error. Trend "
        "state uses only closes before the day. 2025-2026 not loaded.",
        "",
        "## By year",
        "",
        "| Year | Gold % | ADR $ | Days > 2 ADR % " + head,
        "| --- | ---: | ---: | ---: " + sep,
    ]
    for y, r in p["by_year"].items():
        out.append(
            f"| {y} | {r['year_change_pct']:+.1f} | {r['avg_adr_usd']:.1f} | "
            f"{r['big_range_days_pct']:.1f} | "
            + " | ".join(cell(r[c]) for c in cols)
            + " |"
        )
    out += [
        "",
        "## By trend state known before the day (all years)",
        "",
        "| State " + head,
        "| --- " + sep,
    ]
    for name, r in p["by_trend_state"].items():
        out.append(f"| {name} | " + " | ".join(cell(r[c]) for c in cols) + " |")
    out += [
        "",
        "## Above / below the 50-day average, by period",
        "",
        "| Period | State " + head,
        "| --- | --- " + sep,
    ]
    for per, g in p["trend_by_period"].items():
        for name, r in g.items():
            out.append(
                f"| {per} | {name} | " + " | ".join(cell(r[c]) for c in cols) + " |"
            )
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
