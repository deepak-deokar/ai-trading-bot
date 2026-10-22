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
from trading_bot.backtesting.costs import ReferenceCostModel
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
        LocalCSVProvider(Path("tests/fixtures/reliance_baseline.csv")), request
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
    strategy = builtin_registry().resolve(
        StrategyConfig(name="baseline_trend_momentum_v1", version="1")
    )
    service = BacktestService(engine, calendar)
    first, second = [
        service.run(
            config,
            ScriptedDecisionSource(),
            ReferenceCostModel.load(
                Path("config/groww_nse_intraday_reference_v1.yaml")
            ),
            BasisPointsSlippageModel(Decimal(5)),
            strategy,
        )
        for _ in range(2)
    ]
    assert imported.rows_inserted == features.rows_generated == 75
    assert first.deterministic_payload() == second.deterministic_payload()
    assert first.run_id != second.run_id
    entries = [o for o in first.orders if o.intent.side == "BUY"]
    assert len(entries) == 1
    assert len(first.trades) == 1
    entry = entries[0]
    stop = next(o for o in first.orders if ":STOP:" in o.intent.reference)
    target = next(o for o in first.orders if ":TARGET:" in o.intent.reference)
    fill = first.fills[0]
    assert fill.bar_open > entry.intent.created_at
    assert stop.intent.metadata["entry_atr"] == entry.intent.metadata["atr_14"]
    assert Decimal(stop.intent.metadata["fill_basis"]) == fill.price
    assert stop.intent.trigger_price < fill.price < target.intent.limit_price
    loaded = BacktestRepository(engine).get_result(first.run_id)
    assert loaded.deterministic_payload() == first.deterministic_payload()
    evidence = {
        "label": "SIMULATED BASELINE TEST OUTPUT — NOT PROFITABILITY EVIDENCE",
        "bars_loaded": imported.rows_inserted,
        "feature_rows": features.rows_generated,
        "strategy": first.manifest["strategy"],
        "config_key": first.config_key,
        "run_ids": [str(first.run_id), str(second.run_id)],
        "deterministic_rerun": True,
        "signal_time": entry.intent.created_at.isoformat(),
        "fill_bar_open": fill.bar_open.isoformat(),
        "fill_time": fill.timestamp.isoformat(),
        "fill_price": str(fill.price),
        "atr_used": entry.intent.metadata["atr_14"],
        "stop": str(stop.intent.trigger_price),
        "target": str(target.intent.limit_price),
        "exit_reason": first.trades[0].exit_reason,
        "metrics": first.model_dump(mode="json")["metrics"],
        "orders": [o.model_dump(mode="json") for o in first.orders],
        "fills": [f.model_dump(mode="json") for f in first.fills],
        "warnings": first.warnings,
    }
    Path("docs/phase5b1-demonstration.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )
    print(
        json.dumps(
            {k: v for k, v in evidence.items() if k not in {"orders", "fills"}},
            indent=2,
        )
    )


def main():
    url = os.environ["DATABASE_URL"]
    schema = "phase5b1_demo_" + uuid4().hex
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
