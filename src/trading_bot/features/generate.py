"""Generate numerical features only: python -m trading_bot.features.generate."""

import argparse
from pathlib import Path

from trading_bot.config.settings import load_settings
from trading_bot.data.calendar import CalendarError, NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.import_history import parse_time
from trading_bot.database.session import build_engine
from trading_bot.domain.market import AdjustmentType, Exchange, Segment, Timeframe
from trading_bot.features.definitions import FeatureConfig, FeatureError
from trading_bot.features.service import FeatureService
from trading_bot.monitoring.logging import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--exchange", choices=list(Exchange), default="NSE")
    parser.add_argument("--segment", choices=list(Segment), default="CASH")
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--timeframe", choices=list(Timeframe), required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--adjustment", choices=list(AdjustmentType), required=True)
    parser.add_argument("--feature-set", default="baseline_v1")
    parser.add_argument("--config", type=Path, default=Path("config/features.yaml"))
    parser.add_argument(
        "--calendar", type=Path, default=Path("config/calendar_nse.yaml")
    )
    parser.add_argument("--allow-unverified-calendar", action="store_true")
    args = parser.parse_args()
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        config = FeatureConfig.load(args.config, args.feature_set)
        request = HistoryRequest(
            exchange=args.exchange,
            segment=args.segment,
            symbols=tuple(args.symbol),
            timeframe=args.timeframe,
            start=parse_time(args.start),
            end=parse_time(args.end),
            adjustment_type=args.adjustment,
        )
        calendar = NSECalendar(
            args.calendar, allow_unverified_history=args.allow_unverified_calendar
        )
        engine = build_engine(settings)
        try:
            report = FeatureService(engine, calendar).generate(
                request, source=args.source, config=config
            )
        finally:
            engine.dispose()
        print(report.model_dump_json(indent=2))
        return 0
    except (FeatureError, CalendarError) as error:
        print(f"Feature generation rejected: {error}")
        return 1
    except Exception:
        print(
            "Feature generation failed; check configuration, historical provenance "
            "and database. No partial feature set was committed."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
