import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

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

pytestmark = pytest.mark.integration


@pytest.fixture
def baseline_config(history_engine):
    request = HistoryRequest(
        symbols=("RELIANCE",),
        start=datetime.fromisoformat("2026-01-05T09:15:00+05:30"),
        end=datetime.fromisoformat("2026-01-05T15:30:00+05:30"),
    )
    calendar = NSECalendar()
    report = IngestionService(history_engine, calendar).ingest(
        LocalCSVProvider(Path("tests/fixtures/reliance_baseline.csv")), request
    )
    assert report.rows_inserted == 75
    features = FeatureService(history_engine, calendar).generate(
        request, source="local", config=FeatureConfig.load(Path("config/features.yaml"))
    )
    return BacktestConfig(
        history=request,
        source="local",
        feature_set_key=features.feature_set_key,
        starting_capital="200000",
    )


def test_real_features_baseline_persistence_and_repeat(history_engine, baseline_config):
    plan = builtin_registry().resolve(
        StrategyConfig(name="baseline_trend_momentum_v1", version="1")
    )
    service = BacktestService(history_engine, NSECalendar())
    a, b = [
        service.run(
            baseline_config,
            ScriptedDecisionSource(),
            ReferenceCostModel.load(
                Path("config/groww_nse_intraday_reference_v1.yaml")
            ),
            BasisPointsSlippageModel(Decimal(5)),
            plan,
        )
        for _ in range(2)
    ]
    assert a.deterministic_payload() == b.deterministic_payload()
    assert len(a.trades) == 1
    assert sum(o.intent.side == "BUY" for o in a.orders) == 1
    loaded = BacktestRepository(history_engine).get_result(a.run_id)
    assert loaded.deterministic_payload() == a.deterministic_payload()
    assert loaded.manifest["strategy"] == plan.manifest()
    assert loaded.orders[1].intent.metadata["fill_basis"] == str(a.fills[0].price)
    assert (
        loaded.orders[1].intent.metadata["entry_atr"]
        == a.orders[0].intent.metadata["atr_14"]
    )
    assert a.fills[0].bar_open > a.orders[0].intent.created_at
    assert (
        a.metrics["net_pnl"]
        == a.metrics["gross_pnl"]
        - a.metrics["estimated_slippage_cost"]
        - a.metrics["total_costs"]
    )


def test_baseline_cli_config(
    history_engine, baseline_config, monkeypatch, tmp_path, settings
):
    from trading_bot.backtesting import run as cli

    cfg = baseline_config
    output = tmp_path / "baseline.json"
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
            cfg.history.start.isoformat(),
            "--end",
            cfg.history.end.isoformat(),
            "--adjustment",
            "RAW",
            "--starting-capital",
            "200000",
            "--feature-set-key",
            cfg.feature_set_key,
            "--strategy-config",
            "config/strategy_baseline_trend_momentum_v1.yaml",
            "--cost-model",
            "zero",
            "--json-output",
            str(output),
        ],
    )
    assert cli.main() == 0
    payload = json.loads(output.read_text())
    assert payload["manifest"]["strategy"]["name"] == "baseline_trend_momentum_v1"
    assert len(payload["trades"]) == 1
