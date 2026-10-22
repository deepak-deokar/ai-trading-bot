"""Five finalized RELIANCE sessions only; no strategy or broker invocation."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_bot.config.settings import load_settings
from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.base import ProviderError
from trading_bot.data.providers.yahoo import YahooHistoricalDataProvider
from trading_bot.database.session import build_engine
from trading_bot.domain.market import AdjustmentType


def main():
    settings = load_settings()  # Check local configuration before requesting data.
    now = datetime.now(UTC)
    calendar = NSECalendar()
    sessions = [
        s
        for s in calendar.sessions(now - timedelta(days=20), now)
        if s.closes <= now - timedelta(minutes=30)
    ][-5:]
    if len(sessions) != 5:
        raise RuntimeError("Five supported completed sessions unavailable")
    request = HistoryRequest(
        symbols=("RELIANCE",),
        start=sessions[0].opens,
        end=sessions[-1].closes,
        adjustment_type=AdjustmentType.YAHOO_NATIVE,
    )
    provider = YahooHistoricalDataProvider(calendar)
    output = {
        "status": "YAHOO RELIANCE PILOT BLOCKED",
        "request": request.model_dump(mode="json"),
        "provider_symbol": "RELIANCE.NS",
        "selected_sessions": len(sessions),
        "calendar": calendar.provenance(request.start, request.end),
        "first_timestamp": None,
        "last_timestamp": None,
        "dataset_key": None,
        "ingestion": None,
        "timestamp_semantics": "UNVERIFIED",
        "adjustment_semantics": "YAHOO_NATIVE / UNVERIFIED",
    }
    try:
        provider.prepare(request)
    except ProviderError as error:
        output["failure"] = str(error)
    else:
        output["timestamp_semantics"] = provider.evidence["opening_labels"]
        output["first_timestamp"] = provider.evidence["first_open"]
        output["last_timestamp"] = provider.evidence["last_open"]
        engine = build_engine(settings)
        try:
            report = IngestionService(engine, calendar).ingest(provider, request)
        finally:
            engine.dispose()
        output["ingestion"] = report.model_dump(mode="json")
        output["dataset_key"] = report.dataset_key
        if (
            report.status in ("COMPLETED", "COMPLETED_WITH_WARNINGS")
            and report.rows_valid > 0
            and report.rows_rejected == 0
            and report.conflicts == 0
            and report.missing_expected_bars == 0
        ):
            output["status"] = "YAHOO RELIANCE PILOT VERIFIED"
    output["provider_semantics"] = provider.semantics_manifest()
    Path("docs/yahoo-pilot.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
