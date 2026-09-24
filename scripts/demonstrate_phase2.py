"""Deterministic synthetic data demonstration against a migrated development DB.

Run: PYTHONPATH=src .venv/bin/python scripts/demonstrate_phase2.py
Writes synthetic RELIANCE/TCS fixture candles; reruns preserve existing rows.
"""

import json
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from trading_bot.config.settings import Settings, load_settings
from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.import_history import parse_time
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.local import LocalCSVProvider
from trading_bot.data.query import HistoryQuery
from trading_bot.database.session import build_engine


def main() -> None:
    settings = load_settings()
    engine = build_engine(settings)
    service = IngestionService(engine, NSECalendar())
    request = HistoryRequest(
        symbols=("RELIANCE",),
        start=parse_time("2026-01-05 09:15"),
        end=parse_time("2026-01-05 09:30"),
    )
    results = {}
    try:
        for name, file, req in [
            ("first_import", "reliance_valid.csv", request),
            ("second_import", "reliance_valid.csv", request),
            ("conflict", "reliance_conflict.csv", request),
            ("invalid", "reliance_invalid.csv", request),
            (
                "intraday_gap",
                "tcs_gap.csv",
                HistoryRequest(symbols=("TCS",), start=request.start, end=request.end),
            ),
            (
                "weekend",
                "tcs_weekend.csv",
                HistoryRequest(
                    symbols=("TCS",),
                    start=parse_time("2026-01-09 15:25"),
                    end=parse_time("2026-01-12 09:20"),
                ),
            ),
            (
                "overnight",
                "tcs_overnight.csv",
                HistoryRequest(
                    symbols=("TCS",),
                    start=parse_time("2026-01-06 15:25"),
                    end=parse_time("2026-01-07 09:20"),
                ),
            ),
        ]:
            report = service.ingest(
                LocalCSVProvider(Path("tests/fixtures") / file), req
            )
            assert report.status != "FAILED"
            results[name] = {
                **report.model_dump(mode="json", exclude={"issues"}),
                "missing_expected_bars": report.missing_expected_bars,
            }
        bars = HistoryQuery(engine).get_bars(request, source="local")
        results["chronological_candles"] = [
            {"timestamp": b.timestamp.isoformat(), "close": str(b.close)} for b in bars
        ]
        assert len(bars) == 3 and bars[0].close == Decimal("1501.10")
        assert results["second_import"]["rows_inserted"] == 0
        assert results["conflict"]["conflicts"] == 1
        assert results["invalid"]["rows_rejected"] == 1
        assert results["intraday_gap"]["missing_expected_bars"] == 1
        assert results["weekend"]["missing_expected_bars"] == 0
        assert results["overnight"]["missing_expected_bars"] == 0
        try:
            Settings(database_url=settings.database_url, trading_mode="live")
        except ValidationError:
            results["live_mode"] = "REJECTED"
        else:
            raise AssertionError("live mode unexpectedly accepted")
        results["groww_external_verification"] = "UNVERIFIED"
        print(json.dumps(results, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
