"""Small transactional quote-bar repository with audited, isolated dataset runs."""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator
from sqlalchemy import Engine, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from trading_bot.database.models import BidAskBar, SystemEvent
from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel
from trading_bot.domain.quote_bars import QuoteBar


class QuoteDataset(DomainModel):
    provider: str = Field(min_length=1, max_length=32)
    provider_symbol: str = Field(min_length=1, max_length=128)
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    source_archive: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    selected_source_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start: datetime
    end: datetime
    source_timezone: str = Field(min_length=1)
    normalization_version: str = Field(min_length=1)
    aggregation_version: str = Field(min_length=1)
    interval: Literal["5minute"] = "5minute"

    gap_policy_version: str | None = Field(default=None, min_length=1)
    gap_policy_key: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("start", "end")
    @classmethod
    def bound(cls, value: datetime) -> datetime:
        value = utc(value)
        if value.minute % 5 or value.second or value.microsecond:
            raise ValueError("dataset bounds must align to five minutes")
        return value

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if (self.gap_policy_version is None) != (self.gap_policy_key is None):
            raise ValueError("policy version and content key must be supplied together")
        if not timedelta(0) < self.end - self.start <= timedelta(days=1):
            raise ValueError("research dataset must be positive and at most one day")
        return self

    @property
    def dataset_key(self) -> str:
        data = json.dumps(
            self.model_dump(mode="json", exclude_none=True),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(data.encode()).hexdigest()


class QuoteImportResult(DomainModel):
    run_id: UUID
    dataset_key: str
    inserted: int
    existing: int
    observed: int
    missing_openings: tuple[datetime, ...]


class QuoteBarConflict(ValueError):
    """An existing dataset/bar has different values; transaction is rolled back."""


class QuoteBarRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def import_bars(
        self,
        dataset: QuoteDataset,
        bars: tuple[QuoteBar, ...],
        *,
        raw_ticks: int,
        invalid_ticks: int,
    ) -> QuoteImportResult:
        dataset = QuoteDataset.model_validate(dataset.model_dump())
        bars = tuple(QuoteBar.model_validate(b.model_dump()) for b in bars)
        if not bars or len(bars) > 288:
            raise ValueError("expected 1 through 288 observed pilot bars")
        if type(raw_ticks) is not int or type(invalid_ticks) is not int:
            raise ValueError("tick counts must be integers")
        if (
            invalid_ticks < 0
            or raw_ticks != sum(b.tick_count for b in bars) + invalid_ticks
        ):
            raise ValueError("inconsistent raw/valid/invalid tick counts")
        openings = {b.opening_timestamp for b in bars}
        if len(openings) != len(bars):
            raise ValueError("duplicate opening timestamps in import")
        expected = set()
        t = dataset.start
        while t < dataset.end:
            expected.add(t)
            t += timedelta(minutes=5)
        if not openings <= expected:
            raise ValueError("bar lies outside dataset range")
        missing = tuple(sorted(expected - openings))
        run = uuid4()
        manifest = dataset.model_dump(mode="json", exclude_none=True) | {
            "raw_ticks": raw_ticks,
            "valid_ticks": raw_ticks - invalid_ticks,
            "invalid_ticks": invalid_ticks,
            "observed_bars": len(bars),
            "expected_bins": len(expected),
            "missing_openings": [t.isoformat() for t in missing],
        }
        inserted = 0
        with Session(self._engine) as session, session.begin():
            # Serialize imports of the same dataset, including changed membership.
            session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": int(dataset.dataset_key[:15], 16)},
            )
            previous = session.scalars(
                select(BidAskBar).where(BidAskBar.dataset_key == dataset.dataset_key)
            ).all()
            if previous and {row.opening_timestamp for row in previous} != openings:
                raise QuoteBarConflict("dataset bar membership differs")
            if previous:
                prior = session.scalar(
                    select(SystemEvent.details).where(
                        SystemEvent.run_id == previous[0].run_id,
                        SystemEvent.event_type == "quote_bar_dataset_import",
                    )
                )
                if prior is None or prior.get("manifest") != manifest:
                    raise QuoteBarConflict("dataset provenance or counts differ")
            for bar in sorted(bars, key=lambda b: b.opening_timestamp):
                values = bar.model_dump()
                result = session.execute(
                    insert(BidAskBar)
                    .values(
                        **values,
                        dataset_key=dataset.dataset_key,
                        provider=dataset.provider,
                        provider_symbol=dataset.provider_symbol,
                        run_id=run,
                    )
                    .on_conflict_do_nothing()
                    .returning(BidAskBar.opening_timestamp)
                )
                if result.scalar_one_or_none() is not None:
                    inserted += 1
                else:
                    stored = session.get(
                        BidAskBar, (dataset.dataset_key, bar.opening_timestamp)
                    )
                    assert stored is not None
                    if any(getattr(stored, k) != v for k, v in values.items()):
                        raise QuoteBarConflict("existing bar values differ")
            report = QuoteImportResult(
                run_id=run,
                dataset_key=dataset.dataset_key,
                inserted=inserted,
                existing=len(bars) - inserted,
                observed=len(bars),
                missing_openings=missing,
            )
            session.add(
                SystemEvent(
                    run_id=run,
                    event_type="quote_bar_dataset_import",
                    severity="INFO",
                    message="Research quote-bar import",
                    details={
                        "manifest": manifest,
                        "result": report.model_dump(mode="json"),
                    },
                )
            )
        return report

    def get_bars(
        self,
        *,
        dataset_key: str,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> tuple[QuoteBar, ...]:
        start, end = utc(start), utc(end)
        if start >= end:
            raise ValueError("query start must precede end")
        with Session(self._engine) as session:
            rows = session.scalars(
                select(BidAskBar)
                .where(
                    BidAskBar.dataset_key == dataset_key,
                    BidAskBar.canonical_symbol == symbol,
                    BidAskBar.interval == interval,
                    BidAskBar.opening_timestamp >= start,
                    BidAskBar.opening_timestamp < end,
                )
                .order_by(BidAskBar.opening_timestamp)
            )
            return tuple(
                QuoteBar.model_validate(
                    {k: getattr(row, k) for k in QuoteBar.model_fields}
                )
                for row in rows
            )

    def get_run(self, run_id: UUID) -> dict[str, object] | None:
        with Session(self._engine) as session:
            return session.scalar(
                select(SystemEvent.details).where(
                    SystemEvent.run_id == run_id,
                    SystemEvent.event_type == "quote_bar_dataset_import",
                )
            )
