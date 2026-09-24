"""Run with python -m trading_bot.data.import_history. Historical data only."""

import argparse
from datetime import datetime
from pathlib import Path

import yaml

from trading_bot.config.settings import load_settings
from trading_bot.data.calendar import IST, NSECalendar
from trading_bot.data.contracts import HistoryRequest, RunStatus
from trading_bot.data.ingestion import IngestionService
from trading_bot.data.providers.base import HistoricalDataProvider
from trading_bot.data.providers.groww import GrowwHTTPClient, GrowwProvider
from trading_bot.data.providers.groww_semantics import (
    GrowwSemantics,
    ProviderSemanticsError,
)
from trading_bot.data.providers.local import LocalCSVProvider
from trading_bot.database.session import build_engine
from trading_bot.domain.market import AdjustmentType, Exchange, Segment, Timeframe
from trading_bot.monitoring.logging import configure_logging


def parse_time(value: str) -> datetime:
    """CLI alone interprets naive dates as exchange-local wall time."""
    result = datetime.fromisoformat(value)
    return result.replace(tzinfo=IST) if result.tzinfo is None else result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("local", "groww"), required=True)
    parser.add_argument("--exchange", choices=list(Exchange), default="NSE")
    parser.add_argument("--segment", choices=list(Segment), default="CASH")
    parser.add_argument("--symbol", action="append", help="Repeat for multiple symbols")
    parser.add_argument("--timeframe", choices=list(Timeframe))
    parser.add_argument("--start", required=True)
    parser.add_argument(
        "--end", required=True, help="Exclusive range end / knowledge cutoff"
    )
    parser.add_argument("--file", type=Path)
    parser.add_argument(
        "--calendar", type=Path, default=Path("config/calendar_nse.yaml")
    )
    parser.add_argument("--adjustment", choices=list(AdjustmentType))
    parser.add_argument("--confirm-groww-opening-timestamps", action="store_true")
    parser.add_argument(
        "--groww-semantics",
        type=Path,
        help="Explicit YAML mappings; contains no credentials",
    )
    parser.add_argument(
        "--allow-unverified-calendar",
        action="store_true",
        help="Accept UNKNOWN historical calendar authority for research",
    )
    args = parser.parse_args()
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        if args.provider == "groww" and (
            not args.adjustment
            or not args.confirm_groww_opening_timestamps
            or not args.groww_semantics
            or not settings.groww_access_token
        ):
            parser.error(
                "Groww requires token, semantics file and explicit confirmations"
            )
        request = HistoryRequest(
            exchange=args.exchange,
            segment=args.segment,
            symbols=tuple(args.symbol or settings.universe),
            timeframe=args.timeframe or settings.timeframe,
            start=parse_time(args.start),
            end=parse_time(args.end),
            adjustment_type=args.adjustment or AdjustmentType.RAW,
        )
        provider: HistoricalDataProvider
        if args.provider == "local":
            if args.file is None:
                parser.error("local provider requires --file")
            provider = LocalCSVProvider(args.file)
        else:
            assert settings.groww_access_token is not None
            provider = GrowwProvider(
                GrowwHTTPClient(settings.groww_access_token),
                adjustment_type=request.adjustment_type,
                timestamp_convention="open",
                semantics=GrowwSemantics.model_validate(
                    yaml.safe_load(args.groww_semantics.read_text())
                ),
            )
        calendar = NSECalendar(
            args.calendar, allow_unverified_history=args.allow_unverified_calendar
        )
        engine = build_engine(settings)
        try:
            report = IngestionService(engine, calendar).ingest(provider, request)
        finally:
            engine.dispose()
        print(report.model_dump_json(indent=2))
        print(f"Missing expected bars: {report.missing_expected_bars}")
        return 1 if report.status == RunStatus.FAILED else 0
    except ProviderSemanticsError as error:
        print(f"Provider semantics error: {error}")
        return 1
    except Exception:
        # Never interpolate settings, local raw data, driver or vendor exceptions.
        print("Import failed; check configuration/database and the ingestion audit.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
