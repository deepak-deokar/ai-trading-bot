from datetime import datetime, timedelta

import pandas as pd
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.yahoo import YahooHistoricalDataProvider
from trading_bot.data.query import HistoryQuery
from trading_bot.database.models import MarketBar
from trading_bot.domain.market import AdjustmentType

pytestmark = pytest.mark.integration


@pytest.fixture
def sample():
    start = datetime.fromisoformat("2026-10-19T09:15:00+05:30")
    request = HistoryRequest(
        symbols=("RELIANCE",),
        start=start,
        end=start.replace(hour=15, minute=30),
        adjustment_type=AdjustmentType.YAHOO_NATIVE,
    )
    frame = pd.DataFrame(
        {
            "Open": [1500.0] * 75,
            "High": [1502.0] * 75,
            "Low": [1498.0] * 75,
            "Close": [1501.0] * 75,
            "Volume": [1000] * 75,
        },
        index=pd.date_range(start, periods=75, freq="5min").tz_convert("Asia/Kolkata"),
    )
    metadata = dict(
        symbol="RELIANCE.NS",
        exchangeName="NSI",
        instrumentType="EQUITY",
        currency="INR",
        dataGranularity="5m",
        exchangeTimezoneName="Asia/Kolkata",
    )

    def make(data=frame):
        return YahooHistoricalDataProvider(
            NSECalendar(),
            loader=lambda *args: (data, metadata),
            now=lambda: request.end + timedelta(days=1),
        )

    return request, frame, make


def test_ingestion_isolation_identity_and_duplicates(history_engine, sample):
    request, frame, make = sample
    provider = make()
    provider.prepare(request)
    service = IngestionService(history_engine, NSECalendar())
    result = service.ingest(provider, request)
    assert result.rows_inserted == 75 and result.rows_rejected == 0
    assert result.status == "COMPLETED_WITH_WARNINGS"
    assert any(i.type == "PROVIDER_SEMANTICS_UNVERIFIED" for i in result.issues)
    query = HistoryQuery(history_engine)
    assert query.get_bar_count(request, source="yahoo_finance") == 75
    raw = request.model_copy(update={"adjustment_type": AdjustmentType.RAW})
    assert query.get_bar_count(raw, source="yahoo_finance") == 0
    assert query.get_bars(raw, source="yahoo_finance") == []
    assert query.get_latest_bar(raw, source="yahoo_finance") is None
    assert query.get_available_range(raw, source="yahoo_finance") == (None, None)
    bars = query.get_bars(request, source="yahoo_finance")
    assert len(bars) == 75
    assert query.get_latest_bar(request, source="yahoo_finance") == bars[-1]
    assert query.get_available_range(request, source="yahoo_finance") == (
        bars[0].timestamp,
        bars[-1].timestamp,
    )

    identity = query.get_dataset_identity(result.run_id)
    assert identity.manifest["selection"]["adjustment_type"] == "YAHOO_NATIVE"
    assert identity.manifest["provider_semantics"]["adjustment_status"] == "UNVERIFIED"
    repeated = service.ingest(provider, request)
    assert repeated.rows_inserted == 0 and repeated.duplicates == 75
    assert result.dataset_key == repeated.dataset_key
    with pytest.raises(IntegrityError), history_engine.begin() as conn:
        conn.execute(update(MarketBar).values(adjustment_type="RAW"))


def test_quality_duplicates_gaps_conflicts_invalid_rows(history_engine, sample):
    request, frame, make = sample
    service = IngestionService(history_engine, NSECalendar())
    altered = frame.drop(frame.index[2]).copy()
    altered.iloc[3, altered.columns.get_loc("Low")] = 1600
    altered = pd.concat([altered.iloc[[1]], altered])
    report = service.ingest(make(altered), request)
    assert report.rows_rejected == 1 and report.duplicates == 1
    assert report.missing_expected_bars == 2
    assert any(i.type == "OUT_OF_ORDER" for i in report.issues)
    revised = frame.copy()
    revised.iloc[0, revised.columns.get_loc("Close")] = 1501.5
    conflict = service.ingest(make(revised), request)
    assert conflict.conflicts == 1


def test_native_migration_guard_and_roundtrip(history_engine, sample):
    request, frame, make = sample
    with history_engine.begin() as conn:
        config = Config("alembic.ini")
        config.attributes["connection"] = conn
        command.downgrade(config, "0004")
        command.upgrade(config, "head")
        command.check(config)
    IngestionService(history_engine, NSECalendar()).ingest(make(), request)
    with (
        pytest.raises(RuntimeError, match="YAHOO_NATIVE"),
        history_engine.begin() as conn,
    ):
        config = Config("alembic.ini")
        config.attributes["connection"] = conn
        command.downgrade(config, "0004")
    with history_engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
    with Session(history_engine) as session:
        assert len(session.scalars(select(MarketBar)).all()) == 75
