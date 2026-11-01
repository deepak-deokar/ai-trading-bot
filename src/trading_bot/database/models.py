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
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    """Candle covers [timestamp, available_at), both UTC; visible at available_at.

    Ingestion verifies session-aligned openings and persists the calendar close.
    Queries must always apply available_at <= the requested knowledge cutoff.
    """

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
            "adjustment_type IN ('RAW','SPLIT_ADJUSTED',"
            "'FULLY_ADJUSTED','YAHOO_NATIVE')",
            name="adjustment",
        ),
        CheckConstraint(
            "(source = 'yahoo_finance') = (adjustment_type = 'YAHOO_NATIVE')",
            name="source_adjustment",
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


class FeatureSet(Base):
    """One immutable selection/content/configuration identity."""

    __tablename__ = "feature_sets"
    feature_set_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_key: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(64))
    manifest: Mapped[dict[str, object]] = mapped_column(JSON)
    row_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (CheckConstraint("row_count > 0", name="nonempty"),)


class FeatureValue(Base):
    """Float64-derived JSON numbers/nulls; exact close remains Numeric(28,10)."""

    __tablename__ = "feature_values"
    feature_set_key: Mapped[str] = mapped_column(
        ForeignKey("feature_sets.feature_set_key"), primary_key=True
    )
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    close: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    values: Mapped[dict[str, float | None]] = mapped_column(JSON)
    unavailable: Mapped[dict[str, str]] = mapped_column(JSON)
    sufficient_history: Mapped[bool]
    gap_before: Mapped[bool]
    __table_args__ = (
        CheckConstraint("available_at > timestamp", name="availability"),
        Index("ix_feature_values_available", "feature_set_key", "available_at"),
    )


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    run_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    config_key: Mapped[str | None] = mapped_column(String(64), index=True)
    manifest: Mapped[dict[str, object]] = mapped_column(JSON)
    summary: Mapped[dict[str, object]] = mapped_column(JSON)
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING','COMPLETED','COMPLETED_WITH_WARNINGS','FAILED')",
            name="status",
        ),
    )


class BacktestOrder(Base):
    __tablename__ = "backtest_orders"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("backtest_runs.run_id"), primary_key=True
    )
    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)


class BacktestFill(Base):
    __tablename__ = "backtest_fills"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("backtest_runs.run_id"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "order_id"],
            ["backtest_orders.run_id", "backtest_orders.order_id"],
        ),
    )


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("backtest_runs.run_id"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)


class BacktestEquityPoint(Base):
    __tablename__ = "backtest_equity_points"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("backtest_runs.run_id"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)


class BacktestEvent(Base):
    __tablename__ = "backtest_events"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("backtest_runs.run_id"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)


class DecisionEventRecord(Base):
    """Business audit journal, separate from SystemEvent technical records."""

    __tablename__ = "decision_events"
    __table_args__ = (
        Index("ix_decision_events_chronology", "timestamp", "event_id"),
        *(
            Index(f"ix_decision_events_{name}", name, "timestamp", "event_id")
            for name in (
                "canonical_symbol",
                "event_type",
                "reason_code",
                "trade_id",
                "strategy_id",
            )
        ),
        CheckConstraint("schema_version = 1", name="schema_version"),
    )
    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    canonical_symbol: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(64))
    reason_code: Mapped[str] = mapped_column(String(64))
    strategy_id: Mapped[str | None] = mapped_column(String(128))
    trade_id: Mapped[UUID | None] = mapped_column(Uuid)
    evaluation_id: Mapped[UUID | None] = mapped_column(Uuid)
    order_id: Mapped[UUID | None] = mapped_column(Uuid)
    position_id: Mapped[UUID | None] = mapped_column(Uuid)
    strategy_run_id: Mapped[UUID | None] = mapped_column(Uuid)
    source: Mapped[str] = mapped_column(String(128))
    schema_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)


class BidAskBar(Base):
    """Independent research quotes, with original successful import provenance."""

    __tablename__ = "bid_ask_bars"
    __table_args__ = (
        Index(
            "ix_bid_ask_bars_selection",
            "canonical_symbol",
            "interval",
            "opening_timestamp",
            "provider",
        ),
        CheckConstraint("interval = '5minute'", name="interval"),
        CheckConstraint("canonical_symbol = 'XAUUSD'", name="symbol"),
        CheckConstraint("tick_count > 0", name="tick_count"),
        CheckConstraint(
            "mod(extract(epoch from opening_timestamp),300)=0", name="opening"
        ),
        *(
            CheckConstraint(
                f"{side}_low > 0 AND {side}_low <= {side}_open "
                f"AND {side}_low <= {side}_close "
                f"AND {side}_high >= {side}_open AND {side}_high >= {side}_close",
                name=f"{side}_ohlc",
            )
            for side in ("bid", "ask")
        ),
        CheckConstraint(
            "ask_open >= bid_open AND ask_high >= bid_high "
            "AND ask_low >= bid_low AND ask_close >= bid_close",
            name="not_crossed",
        ),
    )
    dataset_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    opening_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    canonical_symbol: Mapped[str] = mapped_column(String(32))
    interval: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32))
    provider_symbol: Mapped[str] = mapped_column(String(128))
    run_id: Mapped[UUID] = mapped_column(Uuid)
    tick_count: Mapped[int] = mapped_column(BigInteger)
    bid_open: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    bid_high: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    bid_low: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    bid_close: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    ask_open: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    ask_high: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    ask_low: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    ask_close: Mapped[Decimal] = mapped_column(Numeric(28, 10))


class ResearchFeatureBar(Base):
    """Exact Decimal strings and explicit JSON nulls; source bar is mandatory."""

    __tablename__ = "research_feature_bars"
    source_dataset_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    opening_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    feature_version: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_symbol: Mapped[str] = mapped_column(String(32))
    interval: Mapped[str] = mapped_column(String(16))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    feature_dataset_key: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_dataset_key", "opening_timestamp"],
            ["bid_ask_bars.dataset_key", "bid_ask_bars.opening_timestamp"],
        ),
        CheckConstraint("available_at > opening_timestamp", name="availability"),
        Index(
            "ix_research_feature_selection",
            "canonical_symbol",
            "feature_version",
            "opening_timestamp",
        ),
    )
