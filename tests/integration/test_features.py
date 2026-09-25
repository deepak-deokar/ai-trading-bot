from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, event, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trading_bot.data.calendar import NSECalendar
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.base import RawCandle
from trading_bot.data.query import HistoryQuery
from trading_bot.database.models import FeatureSet, FeatureValue, MarketBar, SystemEvent
from trading_bot.features.definitions import FeatureError
from trading_bot.features.repository import FeatureRepository
from trading_bot.features.service import FeatureService

pytestmark = pytest.mark.integration


def load(engine, inputs):
    request, snapshot, config = inputs

    class FixtureProvider:
        name = "local"

        def fetch_bars(self, request):
            return [
                RawCandle(x.bar.model_dump(mode="json"), i + 1)
                for i, x in enumerate(snapshot.bars)
            ]

    report = IngestionService(engine, NSECalendar()).ingest(FixtureProvider(), request)
    assert report.rows_inserted == len(snapshot.bars)
    return request, config


def generate(engine, request, config):
    return FeatureService(engine, NSECalendar()).generate(
        request, source="local", config=config
    )


def query(engine, report, request, **changes):
    return FeatureRepository(engine).get_features(
        **(
            dict(
                feature_set_key=report.feature_set_key,
                symbol="RELIANCE",
                start=request.start,
                end=request.end,
                as_of=request.end,
            )
            | changes
        )
    )


def test_persist_rerun_order_exact_prices_and_availability(
    history_engine, feature_inputs
):
    request, config = load(history_engine, feature_inputs())
    first = generate(history_engine, request, config)
    again = generate(history_engine, request, config)
    assert first.rows_inserted == 40 and again.rows_inserted == 0
    assert first.feature_set_key == again.feature_set_key
    assert first.feature_run_id != again.feature_run_id
    assert first.warmup_rows == 20 and first.invalid_outputs == 0
    rows = query(history_engine, first, request)
    assert len(rows) == 40 and rows == sorted(rows, key=lambda x: x.timestamp)
    assert isinstance(rows[0].close, Decimal) and rows[0].close == Decimal("100")
    assert (
        query(
            history_engine,
            first,
            request,
            as_of=request.start + timedelta(minutes=4, seconds=59),
        )
        == []
    )
    assert (
        len(
            query(
                history_engine,
                first,
                request,
                as_of=request.start + timedelta(minutes=5),
            )
        )
        == 1
    )
    assert (
        query(history_engine, first, request, end=request.start + timedelta(minutes=4))
        == []
    )
    manifest = FeatureRepository(history_engine).get_manifest(first.feature_set_key)
    assert manifest["historical_identities"][0]["dataset_key"]
    assert manifest["dataset"]["calendar"]["authority"] == "REVIEWED_POLICY"
    assert manifest["dataset"]["selection"]["adjustment_type"] == "RAW"


def test_adjustments_and_sources_stay_isolated(history_engine, feature_inputs):
    keys = []
    for adjustment, price in [
        ("RAW", 100),
        ("SPLIT_ADJUSTED", 50),
        ("FULLY_ADJUSTED", 25),
    ]:
        req, cfg = load(
            history_engine,
            feature_inputs(
                count=30, adjustment=adjustment, closes=[price + i for i in range(30)]
            ),
        )
        report = generate(history_engine, req, cfg)
        rows = query(history_engine, report, req)
        assert rows[0].close == price
        assert rows[1].values["return_1"] == pytest.approx(1 / price)
        keys.append(report.feature_set_key)
    assert len(set(keys)) == 3
    with pytest.raises(FeatureError, match="no completed"):
        FeatureService(history_engine, NSECalendar()).generate(
            req, source="groww", config=cfg
        )


def test_changed_stored_candle_produces_new_feature_identity(
    history_engine, feature_inputs
):
    request, config = load(history_engine, feature_inputs())
    first = generate(history_engine, request, config)
    with history_engine.begin() as conn:
        conn.execute(
            update(MarketBar)
            .where(MarketBar.timestamp == request.start + timedelta(minutes=150))
            .values(close=Decimal("131"))
        )
    changed = generate(history_engine, request, config)
    assert first.feature_set_key != changed.feature_set_key
    assert changed.rows_inserted == 40
    old = query(history_engine, first, request)
    new = query(history_engine, changed, request)
    assert old[:30] == new[:30]
    assert old[30].close == 130 and new[30].close == 131


def test_gap_warnings_and_parameter_identity(history_engine, feature_inputs):
    req, cfg = load(history_engine, feature_inputs(count=60, missing=(25,)))
    report = generate(history_engine, req, cfg)
    assert report.missing_bars == 1 and report.gap_affected_rows == 20
    assert report.status == "COMPLETED_WITH_WARNINGS"
    changed = cfg.model_copy(
        update={
            "features": tuple(
                (
                    s.model_copy(update={"params": {"period": 10}})
                    if s.name == "rsi"
                    else s
                )
                for s in cfg.features
            )
        }
    )
    assert (
        generate(history_engine, req, changed).feature_set_key != report.feature_set_key
    )


def test_multi_symbol_persistence(history_engine, feature_inputs):
    req, cfg = load(history_engine, feature_inputs(symbols=("RELIANCE", "TCS")))
    report = generate(history_engine, req, cfg)
    assert report.rows_generated == 80
    assert query(history_engine, report, req)[0].close == 100
    assert query(history_engine, report, req, symbol="TCS")[0].close == 1100


def test_database_feature_uniqueness_and_availability(history_engine, feature_inputs):
    req, cfg = load(history_engine, feature_inputs())
    report = generate(history_engine, req, cfg)
    with Session(history_engine) as session:
        row = session.scalar(select(FeatureValue))
        values = {c.name: getattr(row, c.name) for c in FeatureValue.__table__.columns}
    with pytest.raises(IntegrityError), history_engine.begin() as conn:
        conn.execute(insert(FeatureValue).values(values))
    with pytest.raises(IntegrityError), history_engine.begin() as conn:
        conn.execute(
            update(FeatureValue)
            .where(FeatureValue.feature_set_key == report.feature_set_key)
            .values(available_at=FeatureValue.timestamp)
        )


def test_concurrent_identical_generation(history_engine, feature_inputs):
    req, cfg = load(history_engine, feature_inputs())
    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(lambda _: generate(history_engine, req, cfg), range(2)))
    assert sorted(r.rows_inserted for r in reports) == [0, 40]
    assert reports[0].feature_set_key == reports[1].feature_set_key


def test_persistence_failure_is_atomic(history_engine, feature_inputs):
    req, cfg = load(history_engine, feature_inputs())

    def fail(conn, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO feature_values"):
            raise RuntimeError("simulated batch failure")

    event.listen(history_engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError):
            generate(history_engine, req, cfg)
    finally:
        event.remove(history_engine, "before_cursor_execute", fail)
    with Session(history_engine) as session:
        assert session.scalar(select(func.count()).select_from(FeatureSet)) == 0
        assert session.scalar(select(func.count()).select_from(FeatureValue)) == 0


def test_partial_cache_rejected(history_engine, feature_inputs):
    req, cfg = load(history_engine, feature_inputs())
    generate(history_engine, req, cfg)
    with history_engine.begin() as conn:
        conn.execute(delete(FeatureValue).where(FeatureValue.timestamp == req.start))
    with pytest.raises(FeatureError, match="incomplete"):
        generate(history_engine, req, cfg)


def test_legacy_provenance_rejected_and_snapshot_bounded(
    history_engine, feature_inputs
):
    req, cfg = load(history_engine, feature_inputs())
    with pytest.raises(ValueError, match="limit"):
        HistoryQuery(history_engine).get_snapshot(req, source="local", max_rows=5)
    with history_engine.begin() as conn:
        conn.execute(
            delete(SystemEvent).where(
                SystemEvent.event_type == "historical_dataset_identity"
            )
        )
    with pytest.raises(ValueError, match="identity"):
        generate(history_engine, req, cfg)


def test_feature_migration_roundtrip_retains_candles(history_engine, feature_inputs):
    req, cfg = load(history_engine, feature_inputs())
    generate(history_engine, req, cfg)
    with history_engine.begin() as conn:
        config = Config("alembic.ini")
        config.attributes["connection"] = conn
        command.downgrade(config, "0002")
        assert conn.scalar(text("SELECT to_regclass('feature_values')")) is None
        assert conn.scalar(text("SELECT count(*) FROM market_bars")) == 40
        command.upgrade(config, "head")
        command.check(config)
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
    assert generate(history_engine, req, cfg).rows_inserted == 40


def test_queries_require_aware_cutoff(history_engine, feature_inputs):
    req, cfg = load(history_engine, feature_inputs())
    report = generate(history_engine, req, cfg)
    with pytest.raises(TypeError):
        FeatureRepository(history_engine).get_features(
            feature_set_key=report.feature_set_key,
            symbol="RELIANCE",
            start=req.start,
            end=req.end,
        )
    with pytest.raises(ValueError):
        query(history_engine, report, req, as_of=req.end.replace(tzinfo=None))
    with pytest.raises(FeatureError):
        query(history_engine, report, req, end=req.start)


def test_batch_query_count_not_per_candle(history_engine, feature_inputs):
    req, cfg = load(history_engine, feature_inputs(count=75))
    statements = []

    def track(conn, cursor, statement, parameters, context, many):
        statements.append(statement)

    event.listen(history_engine, "before_cursor_execute", track)
    try:
        generate(history_engine, req, cfg)
    finally:
        event.remove(history_engine, "before_cursor_execute", track)
    assert len(statements) < 15


def test_cli_generation(history_engine, feature_inputs, monkeypatch, capsys, settings):
    from trading_bot.features import generate as cli

    req, cfg = load(history_engine, feature_inputs())
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(cli, "build_engine", lambda _: history_engine)
    monkeypatch.setattr(
        "sys.argv",
        [
            "features",
            "--source",
            "local",
            "--symbol",
            "RELIANCE",
            "--timeframe",
            "5minute",
            "--start",
            req.start.isoformat(),
            "--end",
            req.end.isoformat(),
            "--adjustment",
            "RAW",
        ],
    )
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert '"rows_inserted": 40' in output and '"status": "COMPLETED"' in output
