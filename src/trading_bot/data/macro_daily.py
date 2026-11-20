"""Daily closes of the markets that drive gold, for model inputs.

US dollar index (DX-Y.NYB), US 10-year and 3-month Treasury yields (^TNX, ^IRX),
S&P 500 (^GSPC) and the VIX volatility index (^VIX), from Yahoo Finance via
yfinance. Stored outside the repo next to the gold bars. Downloads stop at
2024-12-31: 2025 and 2026 stay unseen until a strategy has passed on 2014-2024.

A day's close is only known after that day ends, so ``closes_before`` returns
values strictly from earlier dates.
"""

from __future__ import annotations

import csv
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from trading_bot.data.histdata_bulk import DATA_DIR

SYMBOLS = {
    "usd": "DX-Y.NYB",
    "us10y": "^TNX",
    "us3m": "^IRX",
    "spx": "^GSPC",
    "vix": "^VIX",
}
LAST_DAY = date(2024, 12, 31)
MACRO_CSV = DATA_DIR.parent / "macro" / "daily_2013_2024.csv"


def download(path: Path = MACRO_CSV, start: str = "2013-06-01") -> Path:
    """Fetch the daily closes and write one CSV (date + one column per series)."""
    import yfinance as yf

    columns: dict[str, dict[date, float]] = {}
    for name, ticker in SYMBOLS.items():
        frame = yf.download(
            ticker, start=start, end="2025-01-01", progress=False, auto_adjust=False
        )
        close = frame["Close"].squeeze("columns").dropna()
        columns[name] = {
            ts.date(): float(v) for ts, v in close.items() if ts.date() <= LAST_DAY
        }
    days = sorted(set().union(*[set(c) for c in columns.values()]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", *SYMBOLS])
        for d in days:
            w.writerow([d.isoformat(), *(columns[n].get(d, "") for n in SYMBOLS)])
    return path


@dataclass(frozen=True)
class MacroHistory:
    days: list[date]
    values: dict[str, list[float | None]]

    def closes_before(self, day: date, name: str, count: int) -> list[float]:
        """The last `count` known closes of `name` from dates strictly before
        `day`, oldest first (fewer if history is short)."""
        end = bisect_left(self.days, day)
        out: list[float] = []
        for i in range(end - 1, -1, -1):
            v = self.values[name][i]
            if v is not None:
                out.append(v)
                if len(out) == count:
                    break
        return out[::-1]


def load(path: Path = MACRO_CSV) -> MacroHistory:
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    days = [date.fromisoformat(r["date"]) for r in rows]
    if days and days[-1] > LAST_DAY:
        raise ValueError("macro history must stop at 2024-12-31")
    values = {n: [float(r[n]) if r[n] else None for r in rows] for n in SYMBOLS}
    return MacroHistory(days, values)
