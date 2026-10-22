"""Audited orchestration, with wall time used only for operational audit metadata."""

import logging
from uuid import UUID, uuid4

from sqlalchemy import Engine

from trading_bot.backtesting.config import BacktestConfig
from trading_bot.backtesting.costs import TradingCostModel
from trading_bot.backtesting.decisions import ScriptedDecisionSource
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.backtesting.inputs import load_inputs
from trading_bot.backtesting.orders import BacktestError
from trading_bot.backtesting.repository import BacktestRepository
from trading_bot.backtesting.results import BacktestResult
from trading_bot.backtesting.slippage import SlippageModel
from trading_bot.features.engine import FeatureCalendar

logger = logging.getLogger(__name__)


class BacktestFailure(BacktestError):
    def __init__(self, run_id: UUID, message: str) -> None:
        super().__init__(f"{message}; simulated run_id={run_id}")
        self.run_id = run_id


class BacktestService:
    def __init__(self, engine: Engine, calendar: FeatureCalendar) -> None:
        self.database = engine
        self.calendar = calendar
        self.repository = BacktestRepository(engine)

    def run(
        self,
        config: BacktestConfig,
        script: ScriptedDecisionSource,
        costs: TradingCostModel,
        slippage: SlippageModel,
    ) -> BacktestResult:
        run_id = uuid4()
        started = False
        try:
            self.repository.start(
                run_id,
                {
                    "config": config.model_dump(mode="json"),
                    "script": script.model_dump(mode="json"),
                    "costs": costs.manifest(),
                    "slippage": slippage.manifest(),
                },
            )
            started = True
            inputs = load_inputs(self.database, config, self.calendar)
            result = BacktestEngine(self.calendar, costs, slippage).run(
                run_id, inputs, config, script
            )
            self.repository.save(result)
            logger.info(
                "Simulated backtest completed",
                extra={
                    "run_id": str(run_id),
                    "status": result.status,
                    "event_type": "backtest_completed",
                },
            )
            return result
        except Exception as error:
            reason = (
                str(error)
                if type(error) is BacktestError
                else "BACKTEST_VALIDATION_OR_PERSISTENCE_FAILURE"
            )
            if started:
                try:
                    self.repository.fail(run_id, reason)
                except Exception:
                    logger.error(
                        "Backtest audit update unavailable",
                        extra={"run_id": str(run_id), "status": "FAILED"},
                    )
            logger.error(
                "Simulated backtest failed",
                extra={"run_id": str(run_id), "status": "FAILED"},
            )
            raise BacktestFailure(run_id, reason) from None
