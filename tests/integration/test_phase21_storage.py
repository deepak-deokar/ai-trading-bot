from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest, IssueType, RunStatus
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.local import LocalCSVProvider
from trading_bot.data.query import HistoryQuery
from trading_bot.database.models import MarketBar, SystemEvent
from trading_bot.domain.market import AdjustmentType

pytestmark = pytest.mark.integration


def dt(value):
    return datetime.fromisoformat(value + "+05:30")


def request(**updates):
    return HistoryRequest(
        **(
            dict(
                symbols=("RELIANCE",),
                start=dt("2026-01-05T09:15"),
                end=dt("2026-01-05T09:30"),
            )
            | updates
        )
    )


def provider():
    return LocalCSVProvider(Path("tests/fixtures/reliance_valid.csv"))


def test_all_query_methods_enforce_exact_completion_boundary(history_engine):
    service = IngestionService(history_engine, NSECalendar())
    assert service.ingest(provider(), request()).rows_inserted == 3
    query = HistoryQuery(history_engine)
    for cutoff, count in [
        ("09:19:59", 0),
        ("09:20:00", 1),
        ("09:24:59", 1),
        ("09:25:00", 2),
    ]:
        req = request(end=dt(f"2026-01-05T{cutoff}"))
        bars = query.get_bars(req, source="local")
        assert len(bars) == query.get_bar_count(req, source="local") == count
        assert query.get_latest_bar(req, source="local") == (bars[-1] if bars else None)
        assert query.get_available_range(req, source="local") == (
            (bars[0].timestamp, bars[-1].timestamp) if bars else (None, None)
        )
    with Session(history_engine) as session:
        bar = session.scalar(select(MarketBar).order_by(MarketBar.timestamp))
        assert bar.timestamp == dt("2026-01-05T09:15")
        assert bar.available_at == dt("2026-01-05T09:20")


def test_all_adjustments_are_separate_across_all_queries(history_engine, tmp_path):
    service = IngestionService(history_engine, NSECalendar())
    query = HistoryQuery(history_engine)
    for i, adjustment in enumerate(AdjustmentType):
        path = tmp_path / f"{adjustment}.csv"
        path.write_text(
            "symbol,timestamp,open,high,low,close,volume\n"
            f"RELIANCE,2026-01-05T09:15:00+05:30,100,105,99,{101+i},1\n"
        )
        req = request(adjustment_type=adjustment, end=dt("2026-01-05T09:20"))
        report = service.ingest(LocalCSVProvider(path), req)
        assert report.rows_inserted == 1
    for i, adjustment in enumerate(AdjustmentType):
        req = request(adjustment_type=adjustment)
        bars = query.get_bars(req, source="local")
        assert len(bars) == query.get_bar_count(req, source="local") == 1
        assert {b.adjustment_type for b in bars} == {adjustment}
        assert bars[0].close == Decimal(101 + i)
        assert query.get_latest_bar(req, source="local") == bars[0]
        assert query.get_available_range(req, source="local") == (
            bars[0].timestamp,
            bars[0].timestamp,
        )
    # Omitted policy explicitly resolves to RAW, never a wildcard or merged series.
    assert query.get_bars(request(), source="local")[0].adjustment_type == "RAW"


def test_mixed_csv_adjustment_is_rejected_not_relabelled(history_engine, tmp_path):
    path = tmp_path / "mixed.csv"
    path.write_text(
        "symbol,timestamp,open,high,low,close,volume,adjustment_type\n"
        "RELIANCE,2026-01-05T09:15:00+05:30,100,102,99,101,1,RAW\n"
        "RELIANCE,2026-01-05T09:20:00+05:30,100,102,99,101,1,FULLY_ADJUSTED\n"
    )
    report = IngestionService(history_engine, NSECalendar()).ingest(
        LocalCSVProvider(path), request()
    )
    assert report.rows_inserted == 1 and report.rows_rejected == 1


def test_close_timestamp_csv_is_rejected(history_engine, tmp_path):
    path = tmp_path / "close.csv"
    path.write_text(
        "symbol,timestamp,open,high,low,close,volume,timestamp_convention\n"
        "RELIANCE,2026-01-05T09:20:00+05:30,100,102,99,101,1,close\n"
    )
    report = IngestionService(history_engine, NSECalendar()).ingest(
        LocalCSVProvider(path), request()
    )
    assert report.rows_rejected == 1 and report.rows_inserted == 0


def test_dataset_identity_survives_reruns_and_has_persistent_manifest(history_engine):
    service = IngestionService(history_engine, NSECalendar())
    first = service.ingest(provider(), request())
    second = service.ingest(provider(), request())
    assert first.dataset_key == second.dataset_key
    assert first.run_key != second.run_key and second.rows_inserted == 0
    query = HistoryQuery(history_engine)
    identity = query.get_dataset_identity(first.run_id)
    assert identity.run_key == first.run_key
    assert identity.manifest["selection"]["symbols"] == ["RELIANCE"]
    assert identity.manifest["timestamp_convention"] == "open"
    assert identity.manifest["calendar"]["authority"] == "REVIEWED_POLICY"
    assert query.get_dataset_identity(uuid4()) is None
    with Session(history_engine) as session:
        event = session.scalar(
            select(SystemEvent).where(SystemEvent.run_id == first.run_id)
        )
        assert event.event_type == "historical_dataset_identity"


def test_unknown_calendar_authority_requires_opt_in_and_is_persisted(
    history_engine, tmp_path
):
    path = tmp_path / "2020.csv"
    path.write_text(
        "symbol,timestamp,open,high,low,close,volume\n"
        "RELIANCE,2020-01-06T09:15:00+05:30,100,102,99,101,1\n"
    )
    req = request(start=dt("2020-01-06T09:15"), end=dt("2020-01-06T09:20"))
    rejected = IngestionService(history_engine, NSECalendar()).ingest(
        LocalCSVProvider(path), req
    )
    assert rejected.status == RunStatus.FAILED and rejected.rows_inserted == 0
    assert "UNKNOWN" in rejected.issues[-1].message
    accepted = IngestionService(
        history_engine, NSECalendar(allow_unverified_history=True)
    ).ingest(LocalCSVProvider(path), req)
    assert (
        accepted.rows_inserted == 1
        and accepted.status == RunStatus.COMPLETED_WITH_WARNINGS
    )
    assert any(i.type == IssueType.CALENDAR_UNVERIFIED for i in accepted.issues)
    identity = HistoryQuery(history_engine).get_dataset_identity(accepted.run_id)
    assert identity.manifest["calendar"]["authority"] == "UNKNOWN"
    assert identity.manifest["calendar"]["allow_unverified_history"] == "true"
