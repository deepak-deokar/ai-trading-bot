"""Only January 15–19, from the existing verified local archive. No network."""

import argparse
import hashlib
import io
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

from trading_bot.config.settings import load_settings
from trading_bot.data.providers.histdata import (
    five_minute_view,
    quality_statistics,
    read_pilot_day,
)
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.data.quote_coverage import (
    AcceptedGapPattern,
    coverage_for_run,
    recurring_pattern,
)
from trading_bot.database.session import build_engine
from trading_bot.domain.quote_bars import QuoteBar


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    sha = "5b73733b7e1fcc5f10943602d83e54396338f7e106a2f80f03605eabf37a8990"
    with args.archive.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != sha:
            raise ValueError("not the verified January archive")
    engine = build_engine(load_settings())
    repo = QuoteBarRepository(engine)
    records = []
    summaries = []
    days = tuple(f"2024-01-{day}" for day in range(15, 20))
    try:
        with ZipFile(args.archive) as archive:
            for day in range(15, 20):
                with archive.open("DAT_ASCII_XAUUSD_T_202401.csv") as stream:
                    pilot = read_pilot_day(
                        io.TextIOWrapper(stream, encoding="ascii"), date(2024, 1, day)
                    )
                bars = []
                for item in five_minute_view(pilot.ticks):
                    values = {
                        f"{side}_{k}": v
                        for side in ("bid", "ask")
                        for k, v in item[side].items()
                    }
                    bars.append(
                        QuoteBar(
                            opening_timestamp=item["timestamp"],
                            tick_count=item["ticks"],
                            **values,
                        )
                    )
                start = datetime(2024, 1, day, 5, tzinfo=UTC)
                dataset = QuoteDataset(
                    provider="HISTDATA",
                    provider_symbol="XAU/USD",
                    source_archive="HISTDATA_COM_ASCII_XAUUSD_T_202401.zip",
                    source_sha256=sha,
                    source_month="2024-01",
                    selected_source_date=f"2024-01-{day}",
                    start=start,
                    end=start + timedelta(days=1),
                    source_timezone="UTC-05:00 fixed; no DST",
                    normalization_version="histdata-ticks-v1",
                    aggregation_version="bid-ask-utc-5minute-v1",
                )
                result = repo.import_bars(
                    dataset,
                    tuple(bars),
                    raw_ticks=pilot.raw_count,
                    invalid_ticks=pilot.invalid_count,
                )
                summary = coverage_for_run(repo, result.run_id)
                summaries.append(summary)
                records.append(
                    {
                        "import": result.model_dump(mode="json"),
                        "coverage_unaccepted": summary.model_dump(mode="json"),
                        "tick_statistics": quality_statistics(pilot),
                    }
                )
        indices = tuple(
            range(204, 216)
        )  # 22:00–22:55 UTC within a 05:00 UTC source day.
        recurrence = recurring_pattern(tuple(summaries), indices)
        # Explicit bounded policy; no learning of extra gaps or broker schedules.
        pattern = AcceptedGapPattern(
            pattern_id="histdata-20240115-19-2200utc-research-v1",
            reference=summaries[0].provenance,
            accepted_dates=days,
            missing_bin_indices=indices,
        )
        if recurrence["classification"] != "RECURRING_PROVIDER_GAP_PATTERN":
            pattern = None
        for record in records:
            from uuid import UUID

            run = UUID(record["import"]["run_id"])
            record["coverage"] = coverage_for_run(repo, run, pattern).model_dump(
                mode="json"
            )
        report = {
            "analysis_timestamp": datetime.now(UTC).isoformat(),
            "recurrence": recurrence,
            "accepted_pattern": pattern.model_dump(mode="json") if pattern else None,
            "days": records,
            "research_usable_days": sum(
                r["coverage"]["research_usable"] for r in records
            ),
            "scope": "research feed pattern only; not an MT5 broker schedule",
        }
        Path("docs/histdata-week-coverage.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        for r in records:
            c = r["coverage"]
            print(
                c["provenance"]["selected_source_date"],
                c["observed_bars"],
                len(c["missing_openings"]),
                c["classification"],
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
