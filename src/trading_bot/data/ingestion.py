"""Auditable, bounded, all-or-nothing historical data persistence."""

import logging
from datetime import UTC, datetime
from decimal import InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from trading_bot.data.calendar import CalendarError, MarketCalendar
from trading_bot.data.contracts import (
    DataQualityIssue,
    HistoryRequest,
    IngestionReport,
    IssueType,
    RunStatus,
    Severity,
)
from trading_bot.data.identity import dataset_identity
from trading_bot.data.normalize import normalize
from trading_bot.data.providers.base import (
    HistoricalDataProvider,
    ProviderError,
    SemanticsProvider,
)
from trading_bot.data.quality import gap_issues
from trading_bot.database.models import IngestionRun, Instrument, MarketBar, SystemEvent
from trading_bot.domain.models import Bar

VALUES = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_interest",
    "trade_count",
    "vwap",
)
COUNTERS = (
    "rows_received",
    "rows_valid",
    "rows_inserted",
    "rows_skipped",
    "rows_rejected",
    "duplicates",
    "conflicts",
)


def same_values(left: Bar | MarketBar, right: Bar | MarketBar) -> bool:
    return all(getattr(left, key) == getattr(right, key) for key in VALUES)


class IngestionService:
    """Network/file reads occur before a single locked bulk-write transaction."""

    def __init__(
        self, engine: Engine, calendar: MarketCalendar, max_rows: int = 100_000
    ) -> None:
        self.engine = engine
        self.calendar = calendar
        self.max_rows = max_rows
        self.logger = logging.getLogger("trading_bot.data")

    def ingest(
        self, provider: HistoricalDataProvider, request: HistoryRequest
    ) -> IngestionReport:
        """Commit a run first, then commit bars and terminal report atomically."""
        report = IngestionReport(provider=provider.name)
        calendar_provenance = self.calendar.provenance(request.start, request.end)
        provider_semantics = (
            provider.semantics_manifest()
            if isinstance(provider, SemanticsProvider)
            else {
                "timestamp_convention": "open",
                "timezone": "explicit offset required",
                "adjustment_type": request.adjustment_type.value,
            }
        )
        identity = dataset_identity(
            request,
            provider.name,
            report.run_id,
            calendar_provenance,
            provider_semantics,
        )
        report = report.model_copy(
            update={"dataset_key": identity.dataset_key, "run_key": identity.run_key}
        )
        counts = dict.fromkeys(COUNTERS, 0)
        issues: list[DataQualityIssue] = []
        with Session(self.engine) as session, session.begin():
            session.add(
                IngestionRun(
                    run_id=report.run_id,
                    provider=provider.name,
                    exchange=request.exchange,
                    segment=request.segment,
                    symbols=list(request.symbols),
                    timeframe=request.timeframe,
                    adjustment_type=request.adjustment_type,
                    requested_start=request.start,
                    requested_end=request.end,
                    started_at=datetime.now(UTC),
                    status=RunStatus.RUNNING,
                    calendar_version=self.calendar.version,
                )
            )
            session.add(
                SystemEvent(
                    run_id=report.run_id,
                    event_type="historical_dataset_identity",
                    severity="INFO",
                    message="Historical dataset selection identity",
                    details=identity.model_dump(mode="json"),
                )
            )
        stage = IssueType.CALENDAR_FAILURE
        try:
            expected = self.calendar.expected_bars(
                request.start, request.end, request.timeframe
            )
            if calendar_provenance["authority"] == "UNKNOWN":
                issues.append(
                    DataQualityIssue(
                        type=IssueType.CALENDAR_UNVERIFIED,
                        severity=Severity.WARNING,
                        message="Calendar authority UNKNOWN; research opt-in recorded",
                    )
                )
            if provider_semantics.get("real_api_verification") == "UNVERIFIED":
                issues.append(
                    DataQualityIssue(
                        type=IssueType.PROVIDER_SEMANTICS_UNVERIFIED,
                        severity=Severity.WARNING,
                        message="Provider semantics asserted; real API UNVERIFIED",
                    )
                )
            if len(expected) * len(request.symbols) > self.max_rows:
                raise ValueError("request exceeds bounded ingestion size")
            stage = IssueType.PROVIDER_FAILURE
            bars: list[Bar] = []
            observed: dict[str, set[datetime]] = {s: set() for s in request.symbols}
            previous: dict[str, datetime] = {}
            for row in provider.fetch_bars(request):
                counts["rows_received"] += 1
                if counts["rows_received"] > self.max_rows:
                    raise ProviderError("provider exceeds bounded ingestion size")
                try:
                    bar = normalize(row, request, provider.name)
                except (ValueError, TypeError, InvalidOperation, OverflowError):
                    counts["rows_rejected"] += 1
                    issues.append(
                        DataQualityIssue(
                            type=IssueType.INVALID_BAR,
                            severity=Severity.ERROR,
                            row_number=row.row_number,
                            message="Candle schema or values invalid",
                        )
                    )
                    continue
                if bar.timestamp not in expected:
                    counts["rows_rejected"] += 1
                    issues.append(
                        DataQualityIssue(
                            type=IssueType.UNEXPECTED_TIMESTAMP,
                            severity=Severity.ERROR,
                            symbol=bar.symbol,
                            timestamp=bar.timestamp,
                            row_number=row.row_number,
                            message="Outside requested completed session slots",
                        )
                    )
                    continue
                counts["rows_valid"] += 1
                if bar.symbol in previous and bar.timestamp < previous[bar.symbol]:
                    issues.append(
                        DataQualityIssue(
                            type=IssueType.OUT_OF_ORDER,
                            severity=Severity.WARNING,
                            symbol=bar.symbol,
                            timestamp=bar.timestamp,
                            message="Provider timestamps arrived out of order",
                        )
                    )
                previous[bar.symbol] = bar.timestamp
                observed[bar.symbol].add(bar.timestamp)
                bars.append(bar)
            if not counts["rows_received"]:
                issues.append(
                    DataQualityIssue(
                        type=IssueType.EMPTY_DATASET,
                        severity=Severity.WARNING,
                        message="Provider returned no candles",
                    )
                )
            for symbol, timestamps in observed.items():
                if not timestamps:
                    issues.append(
                        DataQualityIssue(
                            type=IssueType.MISSING_SYMBOL,
                            severity=Severity.WARNING,
                            symbol=symbol,
                            message="No valid candles for requested symbol",
                        )
                    )
                issues.extend(gap_issues(symbol, expected, timestamps))
            stage = IssueType.PERSISTENCE_FAILURE
            with Session(self.engine) as session, session.begin():
                # Serializes this service's imports for predictable conflicts, including
                # concurrent first imports. Uniqueness remains the final DB guard.
                session.execute(text("SELECT pg_advisory_xact_lock(72819402)"))
                ids = self._instruments(session, request)
                existing = session.scalars(
                    select(MarketBar).where(
                        MarketBar.instrument_id.in_(ids.values()),
                        MarketBar.timeframe == request.timeframe,
                        MarketBar.source == provider.name,
                        MarketBar.adjustment_type == request.adjustment_type,
                        MarketBar.timestamp >= request.start,
                        MarketBar.timestamp < request.end,
                    )
                ).all()
                known: dict[tuple[UUID, datetime], Bar | MarketBar] = {
                    (b.instrument_id, b.timestamp): b for b in existing
                }
                rows: list[dict[str, Any]] = []
                for bar in bars:
                    key = (ids[bar.symbol], bar.timestamp)
                    prior = known.get(key)
                    if prior is not None:
                        identical = same_values(prior, bar)
                        if identical:
                            counts["duplicates"] += 1
                            counts["rows_skipped"] += 1
                        else:
                            counts["conflicts"] += 1
                            counts["rows_rejected"] += 1
                        issues.append(
                            DataQualityIssue(
                                type=(
                                    IssueType.DUPLICATE
                                    if identical
                                    else IssueType.CONFLICT
                                ),
                                severity=Severity.INFO if identical else Severity.ERROR,
                                symbol=bar.symbol,
                                timestamp=bar.timestamp,
                                message=(
                                    "Identical candle skipped"
                                    if identical
                                    else "Conflict rejected; prior candle preserved"
                                ),
                                details=(
                                    {}
                                    if identical
                                    else {
                                        "existing_close": str(prior.close),
                                        "incoming_close": str(bar.close),
                                        "differing_fields": ",".join(
                                            k
                                            for k in VALUES
                                            if getattr(prior, k) != getattr(bar, k)
                                        ),
                                    }
                                ),
                            )
                        )
                        continue
                    known[key] = bar
                    rows.append(
                        {
                            "instrument_id": key[0],
                            "ingestion_run_id": report.run_id,
                            "timestamp": bar.timestamp,
                            "available_at": expected[bar.timestamp],
                            "timeframe": bar.timeframe,
                            "source": bar.source,
                            "adjustment_type": bar.adjustment_type,
                            **{field: getattr(bar, field) for field in VALUES},
                        }
                    )
                for offset in range(0, len(rows), 1000):
                    session.execute(insert(MarketBar), rows[offset : offset + 1000])
                counts["rows_inserted"] = len(rows)
                status = (
                    RunStatus.COMPLETED_WITH_WARNINGS
                    if any(i.severity != Severity.INFO for i in issues)
                    else RunStatus.COMPLETED
                )
                report = report.model_copy(
                    update={**counts, "issues": tuple(issues), "status": status}
                )
                self._finish(session, report)
        except Exception as error:
            counts["rows_inserted"] = 0
            issues.append(
                DataQualityIssue(
                    type=stage,
                    severity=Severity.CRITICAL,
                    message=(
                        str(error)
                        if isinstance(error, CalendarError)
                        else "Ingestion failed; uncommitted candle writes rolled back"
                    ),
                )
            )
            report = report.model_copy(
                update={**counts, "issues": tuple(issues), "status": RunStatus.FAILED}
            )
            try:
                with Session(self.engine) as session, session.begin():
                    self._finish(session, report)
            except Exception:
                self.logger.critical(
                    "Failed to persist ingestion failure audit",
                    extra={"run_id": str(report.run_id), "event_type": "audit_failure"},
                )
        for issue in report.issues:
            if issue.type == IssueType.CONFLICT:
                self.logger.warning(
                    "Historical candle conflict; see ingestion audit",
                    extra={
                        "run_id": str(report.run_id),
                        "symbol": issue.symbol,
                        "event_type": "historical_conflict",
                    },
                )
        self.logger.info(
            "Historical ingestion finished",
            extra={"run_id": str(report.run_id), "event_type": report.status.value},
        )
        return report

    @staticmethod
    def _instruments(session: Session, request: HistoryRequest) -> dict[str, UUID]:
        session.execute(
            insert(Instrument)
            .values(
                [
                    {
                        "exchange": request.exchange,
                        "segment": request.segment,
                        "symbol": symbol,
                        "asset_class": "indian_equity",
                        "currency": "INR",
                    }
                    for symbol in request.symbols
                ]
            )
            .on_conflict_do_nothing(constraint="uq_instruments_identity")
        )
        instruments = session.scalars(
            select(Instrument).where(
                Instrument.exchange == request.exchange,
                Instrument.segment == request.segment,
                Instrument.symbol.in_(request.symbols),
            )
        ).all()
        return {i.symbol: i.id for i in instruments}

    @staticmethod
    def _finish(session: Session, report: IngestionReport) -> None:
        run = session.get(IngestionRun, report.run_id)
        if run is None:
            raise RuntimeError("ingestion audit row missing")
        run.completed_at = datetime.now(UTC)
        run.status = report.status
        run.quality_issues = [i.model_dump(mode="json") for i in report.issues]
        for field in COUNTERS:
            setattr(run, field, getattr(report, field))
