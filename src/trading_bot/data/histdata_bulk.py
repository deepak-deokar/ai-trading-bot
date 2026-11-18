"""Bulk HistData XAUUSD tick download and 1-minute bid/ask bar building.

The pilot parser in ``providers/histdata.py`` validates each tick with Decimal and
pydantic, which is far too slow for 12 years (~1.5 billion ticks). This module uses
plain floats and fixed-width parsing to build compact 1-minute bars per month.

Source timestamps are EST without DST (fixed UTC-05:00) per the HistData spec; bars
are keyed by UTC minute (epoch seconds of the bar open).
"""

from __future__ import annotations

import io
import os
import re
import time
import urllib.parse
import urllib.request
from calendar import timegm
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import numpy as np

SYMBOL = "XAUUSD"
# Market data lives outside the repo: the repo sits in an iCloud-synced Desktop, and
# gigabytes of archives there would upload to iCloud and be evicted (slow reads).
DATA_DIR = (
    Path(os.environ.get("TRADING_DATA_DIR", Path.home() / "TradingData")) / "xauusd"
)
RAW_DIR = DATA_DIR / "raw" / "histdata_xauusd"
BARS_DIR = DATA_DIR / "bars_1m"
PAGE_URL = (
    "https://www.histdata.com/download-free-forex-historical-data/"
    "?/ascii/tick-data-quotes/xauusd/{year}/{month}"
)
POST_URL = "https://www.histdata.com/get.php"
USER_AGENT = "Mozilla/5.0 (research data client)"
SOURCE_OFFSET_SECONDS = 5 * 3600  # source clock is UTC-05:00 fixed

BAR_FIELDS = (
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
    "spread_max",
)


def archive_name(year: int, month: int) -> str:
    return f"HISTDATA_COM_ASCII_{SYMBOL}_T_{year}{month:02d}.zip"


def download_month(year: int, month: int, dest_dir: Path, timeout: float = 120) -> Path:
    """Download one monthly tick archive through HistData's normal free form."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / archive_name(year, month)
    if target.exists() and is_valid_zip(target):
        return target
    page_url = PAGE_URL.format(year=year, month=month)
    request = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        page = response.read().decode("utf-8", errors="replace")
    token = re.search(r'name="tk" id="tk" value="([0-9a-f]+)"', page)
    if token is None:
        raise RuntimeError(f"no download token on page for {year}-{month:02d}")
    form = urllib.parse.urlencode(
        {
            "tk": token.group(1),
            "date": str(year),
            "datemonth": f"{year}{month:02d}",
            "platform": "ASCII",
            "timeframe": "T",
            "fxpair": SYMBOL,
        }
    ).encode()
    post = urllib.request.Request(
        POST_URL,
        data=form,
        headers={"User-Agent": USER_AGENT, "Referer": page_url},
    )
    with urllib.request.urlopen(post, timeout=timeout) as response:
        payload = response.read()
    partial = target.with_suffix(".part")
    partial.write_bytes(payload)
    if not is_valid_zip(partial):
        partial.unlink()
        raise RuntimeError(f"downloaded file for {year}-{month:02d} is not a valid zip")
    partial.rename(target)
    return target


def is_valid_zip(path: Path) -> bool:
    try:
        with ZipFile(path) as zipped:
            return any(name.endswith(".csv") for name in zipped.namelist())
    except (BadZipFile, OSError):
        return False


@dataclass
class MonthQuality:
    raw_rows: int = 0
    valid_ticks: int = 0
    malformed: int = 0
    nonpositive: int = 0
    crossed: int = 0
    out_of_order: int = 0
    spreads_sample: list[float] = field(default_factory=list)


def parse_epoch(stamp: str) -> int:
    """'YYYYMMDD HHMMSSNNN' in fixed UTC-05:00 -> UTC epoch seconds (whole)."""
    return (
        timegm(
            (
                int(stamp[0:4]),
                int(stamp[4:6]),
                int(stamp[6:8]),
                int(stamp[9:11]),
                int(stamp[11:13]),
                int(stamp[13:15]),
                0,
                0,
                0,
            )
        )
        + SOURCE_OFFSET_SECONDS
    )


def build_minute_bars(
    lines: io.TextIOBase,
) -> tuple[dict[str, np.ndarray], MonthQuality]:
    """Aggregate ticks into UTC 1-minute bid/ask OHLC bars; empty minutes omitted."""
    quality = MonthQuality()
    minutes: list[int] = []
    ticks: list[int] = []
    cols: dict[str, list[float]] = {name: [] for name in BAR_FIELDS}
    current = -1
    bo = bh = bl = bc = ao = ah = al = ac = smax = 0.0
    count = 0
    last_epoch = -1
    # Cached date part: the date prefix changes rarely, so cache its midnight epoch.
    cached_day = ""
    day_epoch = 0

    def flush() -> None:
        minutes.append(current)
        ticks.append(count)
        for name, value in zip(
            BAR_FIELDS, (bo, bh, bl, bc, ao, ah, al, ac, smax), strict=True
        ):
            cols[name].append(value)

    for line in lines:
        quality.raw_rows += 1
        parts = line.rstrip("\r\n").split(",")
        if len(parts) != 4 or len(parts[0]) != 18 or parts[0][8] != " ":
            quality.malformed += 1
            continue
        stamp = parts[0]
        try:
            bid = float(parts[1])
            ask = float(parts[2])
            if stamp[:8] != cached_day:
                cached_day = stamp[:8]
                day_epoch = parse_epoch(cached_day + " 000000000")
            epoch = (
                day_epoch
                + int(stamp[9:11]) * 3600
                + int(stamp[11:13]) * 60
                + int(stamp[13:15])
            )
        except ValueError:
            quality.malformed += 1
            continue
        if not (bid > 0 and ask > 0) or bid != bid or ask != ask:
            quality.nonpositive += 1
            continue
        if ask < bid:
            quality.crossed += 1
            continue
        if epoch < last_epoch:
            quality.out_of_order += 1
            continue
        last_epoch = epoch
        quality.valid_ticks += 1
        spread = ask - bid
        if quality.valid_ticks % 50 == 0:
            quality.spreads_sample.append(spread)
        minute = epoch - epoch % 60
        if minute != current:
            if current >= 0:
                flush()
            current = minute
            bo = bh = bl = bc = bid
            ao = ah = al = ac = ask
            smax = spread
            count = 1
            continue
        count += 1
        bc, ac = bid, ask
        if bid > bh:
            bh = bid
        elif bid < bl:
            bl = bid
        if ask > ah:
            ah = ask
        elif ask < al:
            al = ask
        if spread > smax:
            smax = spread
    if current >= 0:
        flush()
    arrays: dict[str, np.ndarray] = {
        "minute_utc": np.asarray(minutes, dtype=np.int64),
        "tick_count": np.asarray(ticks, dtype=np.int32),
    }
    for name in BAR_FIELDS:
        arrays[name] = np.asarray(cols[name], dtype=np.float64)
    return arrays, quality


def convert_archive(archive: Path, out_path: Path) -> MonthQuality:
    with ZipFile(archive) as zipped:
        members = [n for n in zipped.namelist() if n.endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV in {archive.name}, found {members}")
        with zipped.open(members[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="ascii", errors="replace")
            arrays, quality = build_minute_bars(text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, **arrays)
    return quality


def polite_pause(seconds: float) -> None:
    time.sleep(seconds)
