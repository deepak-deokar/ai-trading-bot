"""Exact historical prices plus persisted completion and ingestion provenance."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trading_bot.data.identity import DatasetIdentity
from trading_bot.domain.models import Bar


@dataclass(frozen=True)
class SnapshotBar:
    bar: Bar
    available_at: datetime
    instrument_id: UUID
    ingestion_run_id: UUID


@dataclass(frozen=True)
class HistorySnapshot:
    bars: tuple[SnapshotBar, ...]
    identities: tuple[DatasetIdentity, ...]
