"""Persist only the checksum-verified January 16 pilot, twice to verify idempotency."""

import argparse
import hashlib
import io
import json
from datetime import date, datetime
from pathlib import Path
from zipfile import ZipFile

from trading_bot.config.settings import load_settings
from trading_bot.data.providers.histdata import five_minute_view, read_pilot_day
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.database.session import build_engine
from trading_bot.domain.quote_bars import QuoteBar


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    expected = "5b73733b7e1fcc5f10943602d83e54396338f7e106a2f80f03605eabf37a8990"
    digest = hashlib.sha256()
    with args.archive.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError("archive is not the verified bounded pilot")
    with ZipFile(args.archive) as archive:
        with archive.open("DAT_ASCII_XAUUSD_T_202401.csv") as stream:
            pilot = read_pilot_day(
                io.TextIOWrapper(stream, encoding="ascii"), date(2024, 1, 16)
            )
    bars = []
    for item in five_minute_view(pilot.ticks):
        fields = {
            f"{side}_{key}": value
            for side in ("bid", "ask")
            for key, value in item[side].items()
        }
        bars.append(
            QuoteBar(
                opening_timestamp=item["timestamp"], tick_count=item["ticks"], **fields
            )
        )
    start = datetime.fromisoformat("2024-01-16T05:00:00+00:00")
    end = datetime.fromisoformat("2024-01-17T05:00:00+00:00")
    dataset = QuoteDataset(
        provider="HISTDATA",
        provider_symbol="XAU/USD",
        source_archive="HISTDATA_COM_ASCII_XAUUSD_T_202401.zip",
        source_sha256=expected,
        source_month="2024-01",
        selected_source_date="2024-01-16",
        start=start,
        end=end,
        source_timezone="UTC-05:00 fixed; no DST",
        normalization_version="histdata-ticks-v1",
        aggregation_version="bid-ask-utc-5minute-v1",
    )
    if len(bars) != 276 or pilot.raw_count != 177064 or pilot.invalid_count != 0:
        raise ValueError("pilot counts differ from verified source")
    engine = build_engine(load_settings())
    try:
        repo = QuoteBarRepository(engine)
        reports = [
            repo.import_bars(
                dataset,
                tuple(bars),
                raw_ticks=pilot.raw_count,
                invalid_ticks=pilot.invalid_count,
            )
            for _ in range(2)
        ]
        stored = repo.get_bars(
            dataset_key=dataset.dataset_key,
            symbol="XAUUSD",
            interval="5minute",
            start=start,
            end=end,
        )
        assert stored == tuple(bars)
        assert len(reports[0].missing_openings) == 12 and reports[1].inserted == 0
        output = {
            "imports": [r.model_dump(mode="json") for r in reports],
            "stored_count": len(stored),
            "provenance": repo.get_run(reports[0].run_id),
            "first_bar": stored[0].model_dump(mode="json"),
            "last_bar": stored[-1].model_dump(mode="json"),
        }
        Path("docs/quote-bar-persistence.json").write_text(
            json.dumps(output, indent=2) + "\n"
        )
        print(
            json.dumps(
                {
                    "imports": [r.inserted for r in reports],
                    "stored": len(stored),
                    "missing": len(reports[0].missing_openings),
                }
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
