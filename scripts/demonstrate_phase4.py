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
from trading_bot.backtesting.costs import ReferenceCostModel, ZeroCostModel
from trading_bot.backtesting.decisions import ScriptedDecisionSource
from trading_bot.backtesting.report import render
from trading_bot.backtesting.repository import BacktestRepository
from trading_bot.backtesting.service import BacktestService
from trading_bot.backtesting.slippage import BasisPointsSlippageModel
from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.local import LocalCSVProvider
from trading_bot.features.definitions import FeatureConfig
from trading_bot.features.service import FeatureService


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
    assert imported.rows_inserted == 75
    features = FeatureService(engine, calendar).generate(
        request, source="local", config=FeatureConfig.load(Path("config/features.yaml"))
    )
    config = BacktestConfig(
        history=request,
        source="local",
        feature_set_key=features.feature_set_key,
        starting_capital="200000",
    )
    script = ScriptedDecisionSource.load(Path("tests/fixtures/backtest_decisions.yaml"))
    fees = ReferenceCostModel.load(Path("config/groww_nse_intraday_reference_v1.yaml"))
    service = BacktestService(engine, calendar)
    baseline = service.run(config, script, fees, BasisPointsSlippageModel(Decimal(5)))
    repeated = service.run(config, script, fees, BasisPointsSlippageModel(Decimal(5)))
    larger = service.run(config, script, fees, BasisPointsSlippageModel(Decimal(10)))
    zero = service.run(
        config, script, ZeroCostModel(), BasisPointsSlippageModel(Decimal(5))
    )
    assert baseline.deterministic_payload() == repeated.deterministic_payload()
    assert baseline.run_id != repeated.run_id
    assert (
        larger.fills[0].price >= baseline.fills[0].price
        and larger.fills[1].price <= baseline.fills[1].price
    )
    assert larger.metrics["net_pnl"] <= baseline.metrics["net_pnl"]
    assert zero.metrics["gross_pnl"] == baseline.metrics["gross_pnl"]
    assert (
        zero.metrics["net_pnl"] - baseline.metrics["net_pnl"]
        == baseline.metrics["total_costs"]
    )
    assert baseline.fills[0].bar_open > script.intents[0].created_at
    assert baseline.fills[0].timestamp > baseline.fills[0].bar_open
    assert len(baseline.trades) == 1
    assert (
        BacktestRepository(engine).get_result(baseline.run_id).deterministic_payload()
        == baseline.deterministic_payload()
    )
    output = {
        "label": "SIMULATED TEST OUTPUT; no evidence of strategy profitability",
        "dataset_key": features.dataset_key,
        "feature_set_key": features.feature_set_key,
        "identical_rerun": True,
        "distinct_run_ids": True,
        "baseline": baseline.model_dump(mode="json"),
        "larger_slippage": {
            "config_key": larger.config_key,
            "metrics": larger.model_dump(mode="json")["metrics"],
            "fills": [f.model_dump(mode="json") for f in larger.fills],
        },
        "zero_cost": {
            "config_key": zero.config_key,
            "metrics": zero.model_dump(mode="json")["metrics"],
        },
    }
    # Keep evidence compact: event/curve samples and the complete trade ledger.
    output["baseline"]["events"] = [
        e
        for e in output["baseline"]["events"]
        if e["kind"] in {"DECISION", "ORDER", "FILL"}
    ]
    output["baseline"]["equity"] = (
        output["baseline"]["equity"][:5]
        + output["baseline"]["equity"][15:19]
        + output["baseline"]["equity"][-1:]
    )
    Path("docs/phase4-demonstration.json").write_text(
        json.dumps(output, indent=2, allow_nan=False) + "\n"
    )
    print(render(baseline))
    print("Identical rerun:", True)
    print("10 bps net P&L:", larger.metrics["net_pnl"])
    print("Zero-cost net P&L:", zero.metrics["net_pnl"])
    print("First fill:", baseline.fills[0].model_dump_json())
    print("Exit fill:", baseline.fills[1].model_dump_json())


def main():
    url = os.environ["DATABASE_URL"]
    schema = "phase4_demo_" + uuid4().hex
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
