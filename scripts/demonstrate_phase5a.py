"""Fresh deterministic simulator demonstration in a disposable PostgreSQL schema."""

import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from trading_bot.backtesting.config import BacktestConfig
from trading_bot.backtesting.costs import ZeroCostModel
from trading_bot.backtesting.decisions import ScriptedDecisionSource
from trading_bot.backtesting.repository import BacktestRepository
from trading_bot.backtesting.service import BacktestService
from trading_bot.backtesting.slippage import BasisPointsSlippageModel
from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.local import LocalCSVProvider
from trading_bot.features.definitions import FeatureConfig
from trading_bot.features.service import FeatureService
from trading_bot.strategies.registry import StrategyConfig, builtin_registry


def demonstrate(engine):
    calendar = NSECalendar()
    request = HistoryRequest(
        symbols=("RELIANCE",),
        start=datetime.fromisoformat("2026-01-05T09:15:00+05:30"),
        end=datetime.fromisoformat("2026-01-05T15:30:00+05:30"),
    )
    imported = IngestionService(engine, calendar).ingest(
        LocalCSVProvider(Path("tests/fixtures/reliance_backtest.csv")), request
    )
    features = FeatureService(engine, calendar).generate(
        request, source="local", config=FeatureConfig.load(Path("config/features.yaml"))
    )
    config = BacktestConfig(
        history=request,
        source="local",
        feature_set_key=features.feature_set_key,
        starting_capital="200000",
    )
    strategy = builtin_registry().resolve(StrategyConfig(name="noop", version="1"))
    service = BacktestService(engine, calendar)
    first, second = [
        service.run(
            config,
            ScriptedDecisionSource(),
            ZeroCostModel(),
            BasisPointsSlippageModel(Decimal(5)),
            strategy,
        )
        for _ in range(2)
    ]
    assert imported.rows_inserted == features.rows_generated == 75
    assert first.deterministic_payload() == second.deterministic_payload()
    assert first.run_id != second.run_id
    assert not first.orders and not first.fills and not first.trades
    assert first.metrics["ending_equity"] == Decimal(200000)
    evaluations = [e for e in first.events if e.kind == "STRATEGY"]
    assert len(evaluations) == 75
    assert all(e.details["intent_count"] == 0 for e in evaluations)
    assert all(
        datetime.fromisoformat(e.details["available_at"]) <= e.timestamp
        for e in evaluations
    )
    loaded = BacktestRepository(engine).get_result(first.run_id)
    assert loaded.deterministic_payload() == first.deterministic_payload()
    evidence = {
        "label": "NoOp framework verification; no trading performance claim",
        "bars_loaded": imported.rows_inserted,
        "features_loaded": features.rows_generated,
        "evaluations": len(evaluations),
        "strategy": first.manifest["strategy"],
        "config_key": first.config_key,
        "run_ids": [str(first.run_id), str(second.run_id)],
        "deterministic_rerun": True,
        "intents": 0,
        "orders": 0,
        "fills": 0,
        "starting_capital": "200000",
        "ending_capital": "200000",
        "first_evaluation": evaluations[0].model_dump(mode="json"),
        "last_evaluation": evaluations[-1].model_dump(mode="json"),
    }
    Path("docs/phase5a-demonstration.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )
    print(json.dumps(evidence, indent=2))


def main():
    url = os.environ["DATABASE_URL"]
    schema = "phase5a_demo_" + uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url,
        connect_args={"options": f"-c search_path={schema} -c timezone=UTC"},
        hide_parameters=True,
    )
    try:
        with engine.begin() as conn:
            config = Config("alembic.ini")
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
        demonstrate(engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


if __name__ == "__main__":
    main()
