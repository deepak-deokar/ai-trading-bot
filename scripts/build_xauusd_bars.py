"""Convert downloaded XAUUSD tick archives to 1-minute bid/ask bars and audit quality.

Writes ~/TradingData/xauusd/bars_1m/XAUUSD_YYYYMM.npz (outside the repo) and a
quality report to docs/xauusd-12yr-data-quality.{json,md}.

Usage: PYTHONPATH=src .venv/bin/python scripts/build_xauusd_bars.py
"""

import argparse
import json
import statistics
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from trading_bot.data.histdata_bulk import BARS_DIR, RAW_DIR, convert_archive

GAP_MINUTES = 15  # report unexplained gaps longer than this
JUMP_FRACTION = 0.01  # flag 1-minute mid moves larger than 1%


def convert_one(args: tuple[Path, Path]) -> dict[str, object]:
    archive, out_dir = args
    month = archive.stem.rsplit("_", 1)[-1]
    out = out_dir / f"XAUUSD_{month}.npz"
    q = convert_archive(archive, out)
    spreads = sorted(q.spreads_sample)
    return {
        "month": f"{month[:4]}-{month[4:]}",
        "raw_rows": q.raw_rows,
        "valid_ticks": q.valid_ticks,
        "malformed": q.malformed,
        "nonpositive": q.nonpositive,
        "crossed": q.crossed,
        "out_of_order": q.out_of_order,
        "spread_median": round(statistics.median(spreads), 4) if spreads else None,
        "spread_p95": round(spreads[int(len(spreads) * 0.95)], 4) if spreads else None,
    }


def is_expected_gap(start: int, end: int) -> str | None:
    """Classify a gap between two observed bars (UTC epoch seconds of bar opens)."""
    s = datetime.fromtimestamp(start, UTC)
    e = datetime.fromtimestamp(end, UTC)
    minutes = (end - start) // 60
    # Weekend: market closes Friday ~21-22 UTC, reopens Sunday ~22-23 UTC.
    if s.weekday() == 4 and s.hour >= 19 and e.weekday() in (6, 0):
        return "weekend"
    if s.weekday() in (5, 6) or e.weekday() == 5:
        return "weekend"
    # Daily maintenance break around 21:00-23:00 UTC (shifts with US DST).
    if 20 <= s.hour <= 22 and minutes <= 125:
        return "daily_break"
    return None


def audit_bars(files: list[Path]) -> dict[str, object]:
    minutes = np.concatenate([np.load(f)["minute_utc"] for f in files])
    bid_c = np.concatenate([np.load(f)["bid_close"] for f in files])
    ask_c = np.concatenate([np.load(f)["ask_close"] for f in files])
    dupes = int(np.sum(np.diff(minutes) <= 0))
    gaps = []
    deltas = np.diff(minutes)
    for i in np.nonzero(deltas > GAP_MINUTES * 60)[0]:
        kind = is_expected_gap(int(minutes[i]), int(minutes[i + 1]))
        if kind is None:
            gaps.append((int(minutes[i]), int(deltas[i] // 60)))
    mid = (bid_c + ask_c) / 2
    jumps = np.nonzero(np.abs(np.diff(mid)) / mid[:-1] > JUMP_FRACTION)[0]
    by_year: dict[int, list[int]] = {}
    for start, length in gaps:
        by_year.setdefault(datetime.fromtimestamp(start, UTC).year, []).append(length)
    largest = sorted(gaps, key=lambda g: -g[1])[:15]
    return {
        "total_minute_bars": int(len(minutes)),
        "first_bar_utc": datetime.fromtimestamp(int(minutes[0]), UTC).isoformat(),
        "last_bar_utc": datetime.fromtimestamp(int(minutes[-1]), UTC).isoformat(),
        "non_increasing_minutes": dupes,
        "unexplained_gaps_over_15m": len(gaps),
        "unexplained_gaps_by_year": {
            str(y): {"count": len(v), "total_minutes": sum(v)}
            for y, v in sorted(by_year.items())
        },
        "largest_unexplained_gaps": [
            {"start_utc": datetime.fromtimestamp(s, UTC).isoformat(), "minutes": m}
            for s, m in largest
        ],
        "one_minute_jumps_over_1pct": [
            {
                "utc": datetime.fromtimestamp(int(minutes[i + 1]), UTC).isoformat(),
                "from_mid": round(float(mid[i]), 3),
                "to_mid": round(float(mid[i + 1]), 3),
            }
            for i in jumps[:30]
        ],
        "one_minute_jump_count": int(len(jumps)),
    }


def write_markdown(report: dict, path: Path) -> None:
    a = report["audit"]
    first, last = report["months"][0]["month"], report["months"][-1]["month"]
    lines = [
        "# XAUUSD 12-year data quality (HistData ticks → 1-minute bid/ask bars)",
        "",
        f"Source: HistData free monthly tick archives, {first} to {last} "
        f"({len(report['months'])} months). Raw archives and bars live in "
        "`~/TradingData/xauusd/` (outside the repo). Timestamps: source EST "
        "fixed UTC−05:00 → UTC.",
        "",
        f"- Valid ticks: **{report['total_valid_ticks']:,}**; rejected rows: "
        f"**{report['total_rejected']:,}**",
        f"- 1-minute bars: **{a['total_minute_bars']:,}** "
        f"({a['first_bar_utc']} → {a['last_bar_utc']})",
        "- Non-increasing minute keys across months: "
        f"**{a['non_increasing_minutes']}**",
        f"- Unexplained gaps > 15 min (not weekend / daily break): "
        f"**{a['unexplained_gaps_over_15m']}**",
        f"- 1-minute mid moves > 1%: **{a['one_minute_jump_count']}**",
        "",
        "## Per year",
        "",
        "| Year | Ticks | Median spread | p95 spread | Unexplained gaps "
        "| Gap minutes |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    years: dict[str, list[dict]] = {}
    for m in report["months"]:
        years.setdefault(m["month"][:4], []).append(m)
    for year, months in sorted(years.items()):
        meds = [m["spread_median"] for m in months if m["spread_median"] is not None]
        p95 = [m["spread_p95"] for m in months if m["spread_p95"] is not None]
        g = a["unexplained_gaps_by_year"].get(year, {"count": 0, "total_minutes": 0})
        lines.append(
            f"| {year} | {sum(m['valid_ticks'] for m in months):,} | "
            f"{statistics.median(meds):.3f} | {statistics.median(p95):.3f} | "
            f"{g['count']} | {g['total_minutes']:,} |"
        )
    lines += [
        "",
        "## Largest unexplained gaps",
        "",
        "| Start (UTC) | Minutes |",
        "| --- | ---: |",
    ]
    lines += [
        f"| {g['start_utc']} | {g['minutes']:,} |"
        for g in a["largest_unexplained_gaps"]
    ]
    lines += [
        "",
        "## 1-minute moves over 1% (first 30)",
        "",
        "| UTC | From | To |",
        "| --- | ---: | ---: |",
    ]
    lines += [
        f"| {j['utc']} | {j['from_mid']} | {j['to_mid']} |"
        for j in a["one_minute_jumps_over_1pct"]
    ]
    lines += [
        "",
        "Spread figures are this feed's quotes (USD per ounce), "
        "sampled every 50th tick.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_DIR)
    parser.add_argument("--bars", type=Path, default=BARS_DIR)
    parser.add_argument(
        "--report", type=Path, default=Path("docs/xauusd-12yr-data-quality")
    )
    args = parser.parse_args()
    archives = sorted(args.raw.glob("HISTDATA_COM_ASCII_XAUUSD_T_*.zip"))
    with ProcessPoolExecutor() as pool:
        months = list(pool.map(convert_one, [(a, args.bars) for a in archives]))
    months.sort(key=lambda m: m["month"])
    for m in months:
        print(m, flush=True)
    files = sorted(args.bars.glob("XAUUSD_*.npz"))
    report = {
        "months": months,
        "total_valid_ticks": sum(m["valid_ticks"] for m in months),
        "total_rejected": sum(
            m["malformed"] + m["nonpositive"] + m["crossed"] + m["out_of_order"]
            for m in months
        ),
        "audit": audit_bars(files),
    }
    args.report.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    write_markdown(report, args.report.with_suffix(".md"))
    print("report written", flush=True)


if __name__ == "__main__":
    main()
