"""Offline one-day analysis of the single January 2024 HistData tick archive."""

import argparse
import hashlib
import io
import json
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

from trading_bot.data.providers.histdata import (
    CANONICAL_SYMBOL,
    PROVIDER,
    PROVIDER_SYMBOL,
    five_minute_view,
    quality_statistics,
    read_pilot_day,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/histdata-pilot.json"))
    args = parser.parse_args()
    archive = args.archive
    member = "DAT_ASCII_XAUUSD_T_202401.csv"
    if archive.stat().st_size > 200 * 1024 * 1024:
        raise ValueError("archive exceeds pilot size cap")
    with ZipFile(archive) as zipped:
        if zipped.namelist().count(member) != 1:
            raise ValueError("expected exactly one January 2024 XAUUSD tick CSV")
        if zipped.getinfo(member).file_size > 500 * 1024 * 1024:
            raise ValueError("expanded CSV exceeds pilot size cap")
        with zipped.open(member) as stream:
            pilot = read_pilot_day(
                io.TextIOWrapper(stream, encoding="ascii"), date(2024, 1, 16)
            )
    bars = five_minute_view(pilot.ticks)
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    report = {
        "provider": PROVIDER,
        "canonical_symbol": CANONICAL_SYMBOL,
        "provider_symbol": PROVIDER_SYMBOL,
        "provider_filename_symbol": "XAUUSD",
        "source_file": archive.name,
        "source_member": member,
        "source_file_sha256": digest.hexdigest(),
        "source_month": "2024-01",
        "pilot_source_date": "2024-01-16",
        "pilot_utc_range": ["2024-01-16T05:00:00+00:00", "2024-01-17T05:00:00+00:00"],
        "source_timezone": "UTC-05:00 fixed; no DST",
        "normalization": (
            "attach fixed offset to provider timestamp, convert to UTC; "
            "direct Decimal prices; no scaling"
        ),
        "download_method": (
            "normal HistData free monthly ASCII tick form; no paid access"
        ),
        "analysis_timestamp": datetime.now(UTC).isoformat(),
        "statistics": quality_statistics(pilot),
        "rejected_source_lines_first_20": list(pilot.rejected_lines[:20]),
        "volume_values_and_counts": dict(Counter(t.source_volume for t in pilot.ticks)),
        "volume_semantics": "provider-specific/unverified; original field preserved",
        "five_minute_bar_count": len(bars),
        "first_five_minute_bar": bars[0] if bars else None,
        "last_five_minute_bar": bars[-1] if bars else None,
        "limitations": [
            "research feed, not future MT5 broker feed",
            "observed bins only; no gap filling or completeness claim",
            "duplicates retained with stable source order",
            "only selected source-date prefix rows analyzed",
        ],
    }

    def exact_json(value: object) -> str:
        if isinstance(value, Decimal):
            return str(value)
        raise TypeError("unsupported report value")

    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=exact_json) + "\n"
    )
    print(json.dumps(report["statistics"], indent=2))
    print("five_minute_bar_count:", len(bars))


if __name__ == "__main__":
    main()
