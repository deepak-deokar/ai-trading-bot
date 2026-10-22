from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, event, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trading_bot.backtesting.config import BacktestConfig
from trading_bot.backtesting.costs import ZeroCostModel
from trading_bot.backtesting.decisions import ScriptedDecisionSource
from trading_bot.backtesting.repository import BacktestRepository
from trading_bot.backtesting.service import BacktestFailure, BacktestService
from trading_bot.backtesting.slippage import ZeroSlippageModel
from trading_bot.data.calendar import NSECalendar
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.base import RawCandle
from trading_bot.database.models import (
    BacktestEquityPoint,
    BacktestFill,
    BacktestOrder,
    BacktestRun,
    BacktestTrade,
    FeatureValue,
    MarketBar,
)
from trading_bot.features.service import FeatureService

pytestmark = pytest.mark.integration


@pytest.fixture
def prepared(history_engine, feature_inputs):
    request, snapshot, config = feature_inputs(count=75)

    class Rows:
        name = "local"

        def fetch_bars(self, request):
            return [
                RawCandle(r.bar.model_dump(mode="json"), i + 1)
                for i, r in enumerate(snapshot.bars)
            ]

    assert (
        IngestionService(history_engine, NSECalendar())
        .ingest(Rows(), request)
        .rows_inserted
        == 75
    )
    features = FeatureService(history_engine, NSECalendar()).generate(
        request, source="local", config=config
    )
    btconfig = BacktestConfig(
        history=request,
        source="local",
        feature_set_key=features.feature_set_key,
        starting_capital="200000",
        participation_rate=None,
    )
    return btconfig


def script(config):
    from datetime import timedelta

    from trading_bot.backtesting.orders import TradeIntent

    return ScriptedDecisionSource(
        intents=tuple(
            TradeIntent(
                reference=side,
                symbol="RELIANCE",
                side=side,
                quantity=10,
                created_at=config.history.start + timedelta(minutes=minute),
                feature_timestamp=config.history.start + timedelta(minutes=minute - 5),
            )
            for side, minute in (("BUY", 5), ("SELL", 30))
        )
    )


def simulate(engine, config):
    return BacktestService(engine, NSECalendar()).run(
        config, script(config), ZeroCostModel(), ZeroSlippageModel()
    )


def test_persist_all_ledgers_reruns_and_chronological_queries(history_engine, prepared):
    first = simulate(history_engine, prepared)
    second = simulate(history_engine, prepared)
    assert first.run_id != second.run_id and first.config_key == second.config_key
    assert first.deterministic_payload() == second.deterministic_payload()
    repository = BacktestRepository(history_engine)
    loaded = repository.get_result(first.run_id)
    assert loaded.deterministic_payload() == first.deterministic_payload()
    assert loaded.metrics == first.metrics
    assert isinstance(loaded.metrics["net_pnl"], Decimal)
    assert [p.timestamp for p in loaded.equity] == sorted(
        p.timestamp for p in loaded.equity
    )
    with Session(history_engine) as session:
        for model, count in (
            (BacktestOrder, 2),
            (BacktestFill, 2),
            (BacktestTrade, 1),
            (BacktestEquityPoint, len(first.equity)),
        ):
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.run_id == first.run_id)
                )
                == count
            )
        assert session.get(BacktestRun, first.run_id).completed_at is not None


def test_fill_order_and_run_foreign_keys(history_engine, prepared):
    result = simulate(history_engine, prepared)
    with pytest.raises(IntegrityError), history_engine.begin() as conn:
        conn.execute(
            insert(BacktestFill).values(
                run_id=result.run_id,
                sequence=999,
                order_id="missing",
                timestamp=prepared.history.start,
                payload={},
            )
        )
    with pytest.raises(IntegrityError), history_engine.begin() as conn:
        conn.execute(
            insert(BacktestOrder).values(run_id=uuid4(), order_id="orphan", payload={})
        )


def test_result_write_failure_rolls_back_and_preserves_failed_audit(
    history_engine, prepared
):
    def fail(conn, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO backtest_fills"):
            raise RuntimeError("private database error")

    event.listen(history_engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(BacktestFailure) as error:
            simulate(history_engine, prepared)
    finally:
        event.remove(history_engine, "before_cursor_execute", fail)
    assert "private database error" not in str(error.value)
    repository = BacktestRepository(history_engine)
    assert repository.get_result(error.value.run_id) is None
    assert repository.get_audit(error.value.run_id)["status"] == "FAILED"
    with Session(history_engine) as session:
        for model in (BacktestOrder, BacktestFill, BacktestTrade, BacktestEquityPoint):
            assert session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize(
    "failure",
    [
        "missing_feature_set",
        "adjustment",
        "source",
        "changed_bar",
        "invalid_feature",
        "missing_bar",
    ],
)
def test_incompatible_inputs_audited_without_partial_success(
    history_engine, prepared, failure
):
    config = prepared
    if failure == "missing_feature_set":
        config = config.model_copy(update={"feature_set_key": "0" * 64})
    if failure == "adjustment":
        from trading_bot.domain.market import AdjustmentType

        config = config.model_copy(
            update={
                "history": config.history.model_copy(
                    update={"adjustment_type": AdjustmentType.SPLIT_ADJUSTED}
                )
            }
        )
    if failure == "source":
        config = config.model_copy(update={"source": "groww"})
    with history_engine.begin() as conn:
        if failure == "changed_bar":
            conn.execute(
                update(MarketBar)
                .where(MarketBar.timestamp == config.history.start)
                .values(close=Decimal("101"))
            )
        if failure == "invalid_feature":
            conn.execute(
                update(FeatureValue)
                .where(FeatureValue.timestamp == config.history.start)
                .values(values={"bad": 1})
            )
        if failure == "missing_bar":
            conn.execute(
                delete(MarketBar).where(MarketBar.timestamp == config.history.start)
            )
    with pytest.raises(BacktestFailure) as error:
        simulate(history_engine, config)
    audit = BacktestRepository(history_engine).get_audit(error.value.run_id)
    assert audit["status"] == "FAILED"
    assert BacktestRepository(history_engine).get_result(error.value.run_id) is None


def test_backtest_migration_roundtrip_preserves_features(history_engine, prepared):
    simulate(history_engine, prepared)
    with history_engine.begin() as conn:
        config = Config("alembic.ini")
        config.attributes["connection"] = conn
        count = conn.scalar(select(func.count()).select_from(FeatureValue))
        command.downgrade(config, "0003")
        assert conn.scalar(text("SELECT to_regclass('backtest_runs')")) is None
        assert conn.scalar(select(func.count()).select_from(FeatureValue)) == count
        command.upgrade(config, "head")
        command.check(config)
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
    assert simulate(history_engine, prepared).metrics["number_of_trades"] == 1


def test_backtest_cli_real_database(
    history_engine, prepared, monkeypatch, tmp_path, capsys, settings
):
    from trading_bot.backtesting import run as cli

    path = tmp_path / "script.yaml"
    path.write_text(script(prepared).model_dump_json())
    output = tmp_path / "result.json"
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(cli, "build_engine", lambda _: history_engine)
    monkeypatch.setattr(
        "sys.argv",
        [
            "backtest",
            "--source",
            "local",
            "--symbol",
            "RELIANCE",
            "--timeframe",
            "5minute",
            "--start",
            prepared.history.start.isoformat(),
            "--end",
            prepared.history.end.isoformat(),
            "--adjustment",
            "RAW",
            "--starting-capital",
            "200000",
            "--feature-set-key",
            prepared.feature_set_key,
            "--decision-script",
            str(path),
            "--cost-model",
            "zero",
            "--slippage-bps",
            "0",
            "--disable-participation",
            "--json-output",
            str(output),
        ],
    )
    assert cli.main() == 0
    assert "SIMULATED TEST OUTPUT" in capsys.readouterr().out
    assert output.is_file()
