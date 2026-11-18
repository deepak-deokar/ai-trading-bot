"""Download HistData XAUUSD monthly tick archives (skips months already present).

Usage: PYTHONPATH=src .venv/bin/python scripts/fetch_xauusd_history.py \
    --start 2014-01 --end 2026-10
"""

import argparse
import sys
from pathlib import Path

from trading_bot.data.histdata_bulk import RAW_DIR, download_month, polite_pause


def month_range(start: str, end: str) -> list[tuple[int, int]]:
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    months = []
    while (y, m) <= (ey, em):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2014-01")
    parser.add_argument("--end", default="2026-10")
    parser.add_argument("--dest", type=Path, default=RAW_DIR)
    parser.add_argument("--pause", type=float, default=3.0)
    args = parser.parse_args()
    failures = []
    for year, month in month_range(args.start, args.end):
        try:
            path = download_month(year, month, args.dest)
            print(f"{year}-{month:02d} ok {path.stat().st_size:,} bytes", flush=True)
        except Exception as exc:  # report and continue; rerun retries missing months
            failures.append(f"{year}-{month:02d}")
            print(f"{year}-{month:02d} FAILED {exc}", flush=True)
        polite_pause(args.pause)
    print(f"done; failures: {failures or 'none'}", flush=True)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
