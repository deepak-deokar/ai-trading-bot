"""Requests, quality findings, and durable report schemas."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from trading_bot.domain.market import AdjustmentType, Exchange, Segment, Timeframe, utc
from trading_bot.domain.models import DomainModel, Symbol


class HistoryRequest(DomainModel):
    exchange: Exchange = Exchange.NSE
    segment: Segment = Segment.CASH
    symbols: tuple[Symbol, ...] = Field(min_length=1)
    timeframe: Timeframe = Timeframe.MIN_5
    start: datetime
    end: datetime
    adjustment_type: AdjustmentType = AdjustmentType.RAW

    @field_validator("start", "end")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.start >= self.end:
            raise ValueError("start must precede end (exclusive)")
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("symbols must be unique")
        return self


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class IssueType(StrEnum):
    INVALID_BAR = "INVALID_BAR"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    MISSING_BAR = "MISSING_BAR"
    LARGE_GAP = "LARGE_GAP"
    UNEXPECTED_TIMESTAMP = "UNEXPECTED_TIMESTAMP"
    EMPTY_DATASET = "EMPTY_DATASET"
    MISSING_SYMBOL = "MISSING_SYMBOL"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    CALENDAR_FAILURE = "CALENDAR_FAILURE"


class DataQualityIssue(DomainModel):
    type: IssueType
    severity: Severity
    symbol: str | None = None
    timestamp: datetime | None = None
    row_number: int | None = None
    message: str
    details: dict[str, str | int] = Field(default_factory=dict)


class RunStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"


class IngestionReport(DomainModel):
    run_id: UUID = Field(default_factory=uuid4)
    provider: str
    status: RunStatus = RunStatus.CREATED
    rows_received: int = 0
    rows_valid: int = 0
    rows_inserted: int = 0
    rows_skipped: int = 0
    rows_rejected: int = 0
    duplicates: int = 0
    conflicts: int = 0
    issues: tuple[DataQualityIssue, ...] = ()

    @property
    def missing_expected_bars(self) -> int:
        return sum(i.type == IssueType.MISSING_BAR for i in self.issues)
