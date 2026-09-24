"""Foundation and historical-data persistence; no execution tables."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint("length(symbol) > 0", name="symbol_nonempty"),
        UniqueConstraint(
            "exchange", "segment", "symbol", name="uq_instruments_identity"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16), default="NSE")
    segment: Mapped[str] = mapped_column(String(16), default="CASH")
    asset_class: Mapped[str] = mapped_column(String(32), default="indian_equity")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    run_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(String(1000))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class IngestionRun(Base):
    """Separate committed audit row survives a rolled-back data transaction."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint("requested_start < requested_end", name="ordered_range"),
        CheckConstraint(
            "status IN ('CREATED','RUNNING','COMPLETED',"
            "'COMPLETED_WITH_WARNINGS','FAILED')",
            name="valid_status",
        ),
    )
    run_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16))
    segment: Mapped[str] = mapped_column(String(16))
    symbols: Mapped[list[str]] = mapped_column(JSON)
    timeframe: Mapped[str] = mapped_column(String(16))
    adjustment_type: Mapped[str] = mapped_column(String(32))
    requested_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    calendar_version: Mapped[str] = mapped_column(String(160))
    rows_received: Mapped[int] = mapped_column(Integer, default=0)
    rows_valid: Mapped[int] = mapped_column(Integer, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    conflicts: Mapped[int] = mapped_column(Integer, default=0)
    quality_issues: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)


class MarketBar(Base):
    """Opening timestamp plus explicit session-aware availability time."""

    __tablename__ = "market_bars"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "timeframe",
            "timestamp",
            "source",
            "adjustment_type",
            name="uq_market_bars_identity",
        ),
        Index(
            "ix_market_bars_lookup",
            "instrument_id",
            "timeframe",
            "source",
            "adjustment_type",
            "timestamp",
        ),
        CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0 "
            "AND open < 'Infinity'::numeric AND high < 'Infinity'::numeric "
            "AND low < 'Infinity'::numeric AND close < 'Infinity'::numeric "
            "AND high >= open AND high >= close AND high >= low "
            "AND low <= open AND low <= close",
            name="valid_ohlc",
        ),
        CheckConstraint(
            "volume >= 0 AND (open_interest IS NULL OR open_interest >= 0) "
            "AND (trade_count IS NULL OR trade_count >= 0)",
            name="quantities",
        ),
        CheckConstraint("available_at > timestamp", name="availability"),
        CheckConstraint(
            "timeframe IN ('1minute','5minute','10minute','15minute',"
            "'30minute','1hour','1day')",
            name="timeframe",
        ),
        CheckConstraint(
            "adjustment_type IN ('RAW','SPLIT_ADJUSTED','FULLY_ADJUSTED')",
            name="adjustment",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id"))
    ingestion_run_id: Mapped[UUID] = mapped_column(ForeignKey("ingestion_runs.run_id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timeframe: Mapped[str] = mapped_column(String(16))
    open: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    high: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    low: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    close: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    volume: Mapped[int] = mapped_column(BigInteger)
    open_interest: Mapped[int | None] = mapped_column(BigInteger)
    trade_count: Mapped[int | None] = mapped_column(BigInteger)
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    source: Mapped[str] = mapped_column(String(32))
    adjustment_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
