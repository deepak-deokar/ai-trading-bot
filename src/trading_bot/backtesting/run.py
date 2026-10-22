"""Historical simulator CLI: scripted tests or registered strategies, no broker."""

import argparse
from decimal import Decimal
from pathlib import Path

import yaml

from trading_bot.backtesting.config import BacktestConfig
from trading_bot.backtesting.costs import (
    ReferenceCostModel,
    TradingCostModel,
    ZeroCostModel,
)
from trading_bot.backtesting.decisions import ScriptedDecisionSource
from trading_bot.backtesting.report import render
from trading_bot.backtesting.service import BacktestFailure, BacktestService
from trading_bot.backtesting.slippage import BasisPointsSlippageModel
from trading_bot.config.settings import load_settings
from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.import_history import parse_time
from trading_bot.database.session import build_engine
from trading_bot.domain.market import AdjustmentType, Timeframe
from trading_bot.monitoring.logging import configure_logging
from trading_bot.strategies.registry import StrategyConfig, builtin_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--feature-set-key", required=True)
    parser.add_argument("--timeframe", choices=list(Timeframe), required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--adjustment", choices=list(AdjustmentType), required=True)
    parser.add_argument("--starting-capital", type=Decimal, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--decision-script", type=Path)
    selection.add_argument("--strategy", choices=("noop", "baseline_trend_momentum_v1"))
    selection.add_argument("--strategy-config", type=Path)
    parser.add_argument(
        "--cost-model",
        choices=("zero", "groww_nse_intraday_reference_v1"),
        required=True,
    )
    parser.add_argument(
        "--cost-profile",
        type=Path,
        default=Path("config/groww_nse_intraday_reference_v1.yaml"),
    )
    parser.add_argument("--slippage-bps", type=Decimal, default=Decimal(5))
    parser.add_argument("--participation-rate", type=Decimal, default=Decimal("0.1"))
    parser.add_argument("--disable-participation", action="store_true")
    parser.add_argument("--exit-minutes-before-close", type=int, default=10)
    parser.add_argument(
        "--calendar", type=Path, default=Path("config/calendar_nse.yaml")
    )
    parser.add_argument("--allow-unverified-calendar", action="store_true")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        config = BacktestConfig(
            history=HistoryRequest(
                symbols=tuple(args.symbol),
                timeframe=args.timeframe,
                start=parse_time(args.start),
                end=parse_time(args.end),
                adjustment_type=args.adjustment,
            ),
            source=args.source,
            feature_set_key=args.feature_set_key,
            starting_capital=args.starting_capital,
            participation_rate=(
                None if args.disable_participation else args.participation_rate
            ),
            exit_minutes_before_close=args.exit_minutes_before_close,
        )
        strategy = None
        if args.strategy or args.strategy_config:
            strategy_config = (
                StrategyConfig.model_validate(
                    yaml.safe_load(args.strategy_config.read_text())
                )
                if args.strategy_config
                else StrategyConfig(name=args.strategy, version="1")
            )
            strategy = builtin_registry().resolve(strategy_config)
        script = (
            ScriptedDecisionSource.load(args.decision_script)
            if args.decision_script
            else ScriptedDecisionSource()
        )
        costs: TradingCostModel = (
            ZeroCostModel()
            if args.cost_model == "zero"
            else ReferenceCostModel.load(args.cost_profile)
        )
        slippage = BasisPointsSlippageModel(args.slippage_bps)
        calendar = NSECalendar(
            args.calendar, allow_unverified_history=args.allow_unverified_calendar
        )
        engine = build_engine(settings)
        try:
            result = BacktestService(engine, calendar).run(
                config, script, costs, slippage, strategy
            )
        finally:
            engine.dispose()
        print(render(result))
        if args.json_output:
            args.json_output.write_text(result.model_dump_json(indent=2) + "\n")
        return 0
    except BacktestFailure as error:
        print(f"Backtest FAILED: {error}")
        return 1
    except Exception:
        print(
            "Backtest rejected before execution; check configuration/script/database. "
            "No success result claimed."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
