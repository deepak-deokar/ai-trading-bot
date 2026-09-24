from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest, IssueType, RunStatus
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.base import ProviderError, RawCandle
from trading_bot.data.providers.groww import GrowwProvider
from trading_bot.data.providers.groww_semantics import GrowwSemantics
from trading_bot.data.providers.local import LocalCSVProvider
from trading_bot.data.query import HistoryQuery
from trading_bot.database.models import IngestionRun, Instrument, MarketBar
from trading_bot.domain.market import AdjustmentType

pytestmark = pytest.mark.integration


def dt(value):
    return datetime.fromisoformat(value + "+05:30")


def request(**changes):
    values = dict(
        symbols=("RELIANCE",), start=dt("2026-01-05T09:15"), end=dt("2026-01-05T09:30")
    )
    return HistoryRequest(**(values | changes))


def candle(time="09:15", **changes):
    return (
        dict(
            symbol="RELIANCE",
            timestamp=f"2026-01-05T{time}:00+05:30",
            open="1500.10",
            high="1502.00",
            low="1499.00",
            close="1501.10",
            volume="100",
        )
        | changes
    )


class Rows:
    name = "local"

    def __init__(self, rows):
        self.rows = rows

    def fetch_bars(self, request):
        return [RawCandle(r, i + 1) for i, r in enumerate(self.rows)]


def ingest(engine, rows, req=None):
    return IngestionService(engine, NSECalendar()).ingest(Rows(rows), req or request())


def test_first_import_rerun_queries_and_audit(history_engine):
    rows = [candle(), candle("09:20"), candle("09:25")]
    first = ingest(history_engine, rows)
    assert first.status == RunStatus.COMPLETED and first.rows_inserted == 3
    second = ingest(history_engine, rows)
    assert second.rows_received == 3 and second.rows_inserted == 0
    assert second.rows_skipped == second.duplicates == 3
    query = HistoryQuery(history_engine)
    bars = query.get_bars(request(), source="local")
    assert [b.timestamp.minute for b in bars] == [45, 50, 55]
    assert all(b.close == Decimal("1501.10") for b in bars)
    assert query.get_bar_count(request(), source="local") == 3
    assert query.get_latest_bar(request(), source="local") == bars[-1]
    assert query.get_available_range(request(), source="local") == (
        bars[0].timestamp,
        bars[-1].timestamp,
    )
    with Session(history_engine) as session:
        run = session.get(IngestionRun, second.run_id)
        assert run.completed_at is not None and run.rows_skipped == 3
        assert len(run.quality_issues) == 3


def test_conflict_is_not_overwritten(history_engine):
    ingest(history_engine, [candle()])
    report = ingest(history_engine, [candle(close="1502")])
    assert report.conflicts == report.rows_rejected == 1 and report.rows_inserted == 0
    assert report.status == RunStatus.COMPLETED_WITH_WARNINGS
    assert HistoryQuery(history_engine).get_bars(request(), source="local")[
        0
    ].close == Decimal("1501.10")
    assert any(i.type == IssueType.CONFLICT for i in report.issues)


def test_input_duplicates_conflicts_invalid_and_gaps(history_engine):
    report = ingest(
        history_engine,
        [
            candle("09:25"),
            candle(),
            candle(),
            candle(close="1502"),
            candle("09:20", high="1"),
            candle("09:20", volume="-2"),
        ],
    )
    assert report.rows_received == 6 and report.rows_inserted == 2
    assert (
        report.duplicates == 1 and report.conflicts == 1 and report.rows_rejected == 3
    )
    assert report.missing_expected_bars == 1
    types = {i.type for i in report.issues}
    assert {
        IssueType.OUT_OF_ORDER,
        IssueType.INVALID_BAR,
        IssueType.MISSING_BAR,
    }.issubset(types)
    assert [
        b.timestamp.minute
        for b in HistoryQuery(history_engine).get_bars(request(), source="local")
    ] == [45, 55]


def test_empty_and_missing_symbol_reports(history_engine):
    req = request(symbols=("RELIANCE", "TCS"))
    report = ingest(history_engine, [], req)
    assert report.status == RunStatus.COMPLETED_WITH_WARNINGS
    assert report.missing_expected_bars == 6
    assert sum(i.type == IssueType.MISSING_SYMBOL for i in report.issues) == 2
    assert any(i.type == IssueType.EMPTY_DATASET for i in report.issues)


def test_unexpected_timestamp_and_incomplete_candle(history_engine):
    report = ingest(history_engine, [candle("09:10"), candle("09:16"), candle("15:30")])
    assert report.rows_rejected == 3 and report.rows_inserted == 0
    ingest(history_engine, [candle()])
    query = HistoryQuery(history_engine)
    early = request(end=dt("2026-01-05T09:19"))
    assert query.get_bars(early, source="local") == []
    assert query.get_latest_bar(early, source="local") is None


def test_source_adjustment_isolation(history_engine):
    ingest(history_engine, [candle()])
    req = request(adjustment_type=AdjustmentType.SPLIT_ADJUSTED)
    adjusted = ingest(history_engine, [candle(close="1502")], req)
    assert adjusted.rows_inserted == 1 and adjusted.conflicts == 0
    query = HistoryQuery(history_engine)
    assert query.get_bar_count(request(), source="local") == 1
    assert query.get_bar_count(request(), source="groww") == 0
    assert query.get_bars(req, source="local")[0].close == Decimal("1502")


def test_database_uniqueness_and_numeric_constraints(history_engine):
    ingest(history_engine, [candle()])
    with Session(history_engine) as session:
        bar = session.scalar(select(MarketBar))
        values = {c.name: getattr(bar, c.name) for c in MarketBar.__table__.columns}
    for change in (
        {"id": uuid4()},
        {"id": uuid4(), "timestamp": dt("2026-01-05T09:16"), "volume": -1},
        {"id": uuid4(), "timestamp": dt("2026-01-05T09:16"), "high": Decimal("NaN")},
    ):
        with pytest.raises(IntegrityError), history_engine.begin() as connection:
            connection.execute(insert(MarketBar).values(values | change))


def test_provider_failure_marks_failed_without_partial_data(history_engine):
    class Broken:
        name = "local"

        def fetch_bars(self, request):
            yield RawCandle(candle(), 1)
            raise ProviderError("private-sensitive-message")

    report = IngestionService(history_engine, NSECalendar()).ingest(Broken(), request())
    assert report.status == RunStatus.FAILED and report.rows_inserted == 0
    assert "private-sensitive-message" not in report.model_dump_json()
    with Session(history_engine) as session:
        assert session.get(IngestionRun, report.run_id).status == "FAILED"
        assert session.scalar(select(func.count()).select_from(MarketBar)) == 0


def test_write_failure_rolls_back_inserted_rows_and_instruments(history_engine):
    def fail_final_report(connection, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE ingestion_runs") and not getattr(
            fail_final_report, "fired", False
        ):
            fail_final_report.fired = True
            raise RuntimeError("simulated commit-stage failure")

    event.listen(history_engine, "before_cursor_execute", fail_final_report)
    try:
        report = ingest(history_engine, [candle()])
    finally:
        event.remove(history_engine, "before_cursor_execute", fail_final_report)
    assert report.status == RunStatus.FAILED and report.rows_inserted == 0
    with Session(history_engine) as session:
        assert session.scalar(select(func.count()).select_from(MarketBar)) == 0
        assert session.scalar(select(func.count()).select_from(Instrument)) == 0
        assert session.get(IngestionRun, report.run_id).status == "FAILED"


def test_local_csv_and_malformed_file(history_engine, tmp_path):
    service = IngestionService(history_engine, NSECalendar())
    report = service.ingest(
        LocalCSVProvider(Path("tests/fixtures/reliance_valid.csv")), request()
    )
    assert report.rows_inserted == 3 and report.status == RunStatus.COMPLETED
    bad = tmp_path / "malformed.csv"
    bad.write_text("wrong,header\n1,2")
    failure = service.ingest(LocalCSVProvider(bad), request())
    assert failure.status == RunStatus.FAILED


def test_migration_downgrade_reupgrade_and_drift(history_engine):
    with history_engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.downgrade(config, "0001")
        assert (
            connection.execute(text("SELECT to_regclass('market_bars')")).scalar()
            is None
        )
        command.upgrade(config, "head")
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            == "0002"
        )
        command.check(config)


def test_mock_groww_chunk_merge_is_idempotent(history_engine):
    client = Mock(spec=["get_historical_candles"])
    candle_row = ["2026-02-04T09:15:00", 1500, 1502, 1499, 1501, 100, None]
    client.get_historical_candles.return_value = {"candles": [candle_row]}
    provider = GrowwProvider(
        client,
        adjustment_type=AdjustmentType.RAW,
        timestamp_convention="open",
        semantics=GrowwSemantics(
            timestamp_meaning="open",
            timezone="Asia/Kolkata",
            adjustment_type="RAW",
            interval_mapping={"5minute": "5minute"},
            instrument_mapping={"NSE:CASH:RELIANCE": "NSE-RELIANCE"},
            acknowledgement="UNVERIFIED_PROVIDER_SEMANTICS_ACCEPTED",
        ),
    )
    req = request(end=dt("2026-02-05T09:20"))
    report = IngestionService(history_engine, NSECalendar()).ingest(provider, req)
    assert client.get_historical_candles.call_count == 2
    assert report.rows_inserted == 1 and report.duplicates == 1
    again = IngestionService(history_engine, NSECalendar()).ingest(provider, req)
    assert again.rows_inserted == 0 and again.duplicates == 2


def test_two_symbols_are_queryable_without_collision(history_engine):
    req = request(symbols=("RELIANCE", "TCS"))
    report = ingest(history_engine, [candle(), candle(symbol="TCS")], req)
    assert report.rows_inserted == 2
    bars = HistoryQuery(history_engine).get_bars(req, source="local")
    assert [b.symbol for b in bars] == ["RELIANCE", "TCS"]


def test_concurrent_imports_do_not_race(history_engine):
    from concurrent.futures import ThreadPoolExecutor

    rows = [candle(), candle("09:20"), candle("09:25")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(lambda _: ingest(history_engine, rows), range(2)))
    assert sorted(r.rows_inserted for r in reports) == [0, 3]
    assert sorted(r.duplicates for r in reports) == [0, 3]
    assert all(r.status == RunStatus.COMPLETED for r in reports)


def test_unknown_calendar_range_is_audited_as_failed(history_engine):
    report = ingest(
        history_engine,
        [],
        request(start=dt("2027-01-04T09:15"), end=dt("2027-01-04T09:30")),
    )
    assert report.status == RunStatus.FAILED
    assert report.issues[-1].type == IssueType.CALENDAR_FAILURE


def test_legacy_instrument_upgrade_preserves_identity(history_engine):
    with history_engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.downgrade(config, "0001")
        connection.execute(
            text(
                "INSERT INTO instruments(id,symbol,asset_class,currency) "
                "VALUES (:id,'SPY','us_equity','USD')"
            ),
            {"id": uuid4()},
        )
        command.upgrade(config, "head")
        row = connection.execute(
            text(
                "SELECT exchange,asset_class,currency FROM instruments "
                "WHERE symbol='SPY'"
            )
        ).one()
        assert tuple(row) == ("LEGACY_US", "us_equity", "USD")
