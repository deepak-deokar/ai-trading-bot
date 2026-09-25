"""Explicit source/adjustment selection and completion-aware historical queries."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Engine, Select, func, select
from sqlalchemy.orm import Session

from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.identity import DatasetIdentity
from trading_bot.data.snapshot import HistorySnapshot, SnapshotBar
from trading_bot.database.models import Instrument, MarketBar, SystemEvent
from trading_bot.domain.models import Bar


class HistoryQuery:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get_dataset_identity(self, run_id: UUID) -> DatasetIdentity | None:
        """Fetch persisted semantics/selection identity; legacy imports return None."""
        with Session(self.engine) as session:
            event = session.scalar(
                select(SystemEvent).where(
                    SystemEvent.run_id == run_id,
                    SystemEvent.event_type == "historical_dataset_identity",
                )
            )
            return DatasetIdentity.model_validate(event.details) if event else None

    @staticmethod
    def _statement(
        request: HistoryRequest, source: str
    ) -> Select[tuple[MarketBar, Instrument]]:
        return (
            select(MarketBar, Instrument)
            .join(Instrument)
            .where(
                Instrument.exchange == request.exchange,
                Instrument.segment == request.segment,
                Instrument.symbol.in_(request.symbols),
                MarketBar.timeframe == request.timeframe,
                MarketBar.timestamp >= request.start,
                MarketBar.timestamp < request.end,
                MarketBar.available_at <= request.end,
                MarketBar.source == source,
                MarketBar.adjustment_type == request.adjustment_type,
            )
        )

    @staticmethod
    def _bar(row: MarketBar, instrument: Instrument) -> Bar:
        return Bar.model_validate(
            {
                "exchange": instrument.exchange,
                "segment": instrument.segment,
                "symbol": instrument.symbol,
                "timestamp": row.timestamp,
                "timeframe": row.timeframe,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
                "source": row.source,
                "adjustment_type": row.adjustment_type,
                "open_interest": row.open_interest,
                "trade_count": row.trade_count,
                "vwap": row.vwap,
            }
        )

    def get_bars(self, request: HistoryRequest, *, source: str) -> list[Bar]:
        """Completed candles ordered by opening time, then symbol for ties."""
        with Session(self.engine) as session:
            rows = session.execute(
                self._statement(request, source).order_by(
                    MarketBar.timestamp,
                    Instrument.symbol,
                )
            )
            return [self._bar(row, instrument) for row, instrument in rows]

    def get_snapshot(
        self, request: HistoryRequest, *, source: str, max_rows: int = 100_000
    ) -> HistorySnapshot:
        """Bounded, repeatable-read snapshot in two bulk queries; no float prices."""
        if max_rows < 1:
            raise ValueError("max_rows must be positive")
        with (
            self.engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            Session(connection) as session,
        ):
            rows = session.execute(
                self._statement(request, source)
                .order_by(MarketBar.timestamp, Instrument.symbol)
                .limit(max_rows + 1)
            ).all()
            if len(rows) > max_rows:
                raise ValueError("historical snapshot exceeds row limit")
            bars = tuple(
                SnapshotBar(
                    self._bar(row, instrument),
                    row.available_at,
                    instrument.id,
                    row.ingestion_run_id,
                )
                for row, instrument in rows
            )
            run_ids = {row.ingestion_run_id for row in bars}
            events = (
                session.scalars(
                    select(SystemEvent).where(
                        SystemEvent.run_id.in_(run_ids),
                        SystemEvent.event_type == "historical_dataset_identity",
                    )
                ).all()
                if run_ids
                else []
            )
            identities = tuple(
                DatasetIdentity.model_validate(e.details) for e in events
            )
            if {i.run_id for i in identities} != run_ids or len(identities) != len(
                run_ids
            ):
                raise ValueError(
                    "missing or ambiguous historical dataset identity; "
                    "legacy bars require reviewed provenance"
                )
            return HistorySnapshot(bars, identities)

    def get_latest_bar(self, request: HistoryRequest, *, source: str) -> Bar | None:
        """Latest completed candle within explicit historical cutoff request.end."""
        if len(request.symbols) != 1:
            raise ValueError("latest-bar query requires one symbol")
        with Session(self.engine) as session:
            row = session.execute(
                self._statement(request, source)
                .order_by(MarketBar.timestamp.desc())
                .limit(1)
            ).first()
            return self._bar(*row) if row else None

    def get_bar_count(self, request: HistoryRequest, *, source: str) -> int:
        with Session(self.engine) as session:
            return (
                session.scalar(
                    select(func.count()).select_from(
                        self._statement(request, source).subquery()
                    )
                )
                or 0
            )

    def get_available_range(
        self, request: HistoryRequest, *, source: str
    ) -> tuple[datetime | None, datetime | None]:
        with Session(self.engine) as session:
            subquery = self._statement(request, source).subquery()
            row = session.execute(
                select(func.min(subquery.c.timestamp), func.max(subquery.c.timestamp))
            ).one()
            return row[0], row[1]
