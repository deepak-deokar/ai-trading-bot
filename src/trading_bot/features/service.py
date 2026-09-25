"""Historical query -> pure engine -> validated atomic persistence."""

import logging
from time import perf_counter

from sqlalchemy import Engine

from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.query import HistoryQuery
from trading_bot.features.definitions import FeatureConfig, FeatureReport
from trading_bot.features.engine import FeatureCalendar, FeatureEngine
from trading_bot.features.repository import FeatureRepository

logger = logging.getLogger(__name__)


class FeatureService:
    def __init__(self, engine: Engine, calendar: FeatureCalendar) -> None:
        self.history = HistoryQuery(engine)
        self.calculator = FeatureEngine(calendar)
        self.repository = FeatureRepository(engine)

    def generate(
        self, request: HistoryRequest, *, source: str, config: FeatureConfig
    ) -> FeatureReport:
        started = perf_counter()
        snapshot = self.history.get_snapshot(request, source=source)
        result = self.calculator.generate(
            snapshot, request, source=source, config=config
        )
        inserted = self.repository.save(result)
        report = FeatureReport(
            dataset_key=result.dataset_key,
            feature_set_key=result.feature_set_key,
            feature_set=config.name,
            symbols=tuple(sorted(request.symbols)),
            timeframe=request.timeframe,
            range=(request.start, request.end),
            features_requested=len(config.features),
            bars_loaded=len(snapshot.bars),
            rows_generated=len(result.rows),
            rows_inserted=inserted,
            warmup_rows=sum("WARMUP" in r.unavailable.values() for r in result.rows),
            gap_affected_rows=sum(
                "GAP_WARMUP" in r.unavailable.values() for r in result.rows
            ),
            missing_bars=result.missing_bars,
            duration=perf_counter() - started,
            status=(
                "COMPLETED_WITH_WARNINGS"
                if result.missing_bars
                or any(
                    i.manifest.get("calendar", {}).get("authority") != "REVIEWED_POLICY"
                    or i.manifest.get("provider") == "groww"
                    for i in snapshot.identities
                )
                else "COMPLETED"
            ),
        )
        logger.info(
            "Feature generation completed", extra=report.model_dump(mode="json")
        )
        return report
