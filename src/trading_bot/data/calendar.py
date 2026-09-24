"""Replaceable, bounded NSE calendar with reviewed exceptional-session overrides."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Protocol, Self
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from trading_bot.domain.market import Timeframe, utc

IST = ZoneInfo("Asia/Kolkata")


class CalendarError(Exception):
    """Calendar cannot safely describe the requested range."""


@dataclass(frozen=True)
class Session:
    opens: datetime
    closes: datetime


class MarketCalendar(Protocol):
    version: str

    def expected_bars(
        self, start: datetime, end: datetime, timeframe: Timeframe
    ) -> dict[datetime, datetime]:
        """Map expected opening timestamps to availability/closing timestamps."""
        ...


class Closure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    source: str = Field(min_length=1)


class SpecialSession(Closure):
    open: time
    close: time

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.open >= self.close or self.open.tzinfo or self.close.tzinfo:
            raise ValueError("session requires ordered local wall times")
        return self


class CalendarPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    coverage_start: date
    coverage_end: date
    closed: tuple[Closure, ...] = ()
    sessions: tuple[SpecialSession, ...] = ()

    @model_validator(mode="after")
    def valid_dates(self) -> Self:
        dates = [x.date for x in (*self.closed, *self.sessions)]
        if self.coverage_start > self.coverage_end or len(set(dates)) != len(dates):
            raise ValueError("invalid calendar coverage or duplicate overrides")
        if any(not self.coverage_start <= d <= self.coverage_end for d in dates):
            raise ValueError("calendar override outside coverage")
        return self


class NSECalendar:
    """PMC supplies holidays; unsupported dates fail closed instead of guessing."""

    def __init__(self, policy_path: Path = Path("config/calendar_nse.yaml")) -> None:
        raw = policy_path.read_bytes()
        self.policy = CalendarPolicy.model_validate(yaml.safe_load(raw))
        self.version = (
            f"pmc-{mcal.__version__}:{self.policy.version}:"
            f"{sha256(raw).hexdigest()[:16]}"
        )
        self._calendar = mcal.get_calendar("NSE")

    def sessions(self, start: datetime, end: datetime) -> tuple[Session, ...]:
        """Return regular/specially configured sessions touching [start,end)."""
        start, end = utc(start), utc(end)
        if start >= end:
            raise CalendarError("invalid calendar range")
        first = start.astimezone(IST).date()
        last = (end - timedelta(microseconds=1)).astimezone(IST).date()
        if first < self.policy.coverage_start or last > self.policy.coverage_end:
            raise CalendarError("requested dates exceed reviewed calendar coverage")
        schedule = self._calendar.schedule(start_date=first, end_date=last)
        sessions = {
            stamp.date(): Session(
                row.market_open.to_pydatetime().astimezone(UTC),
                row.market_close.to_pydatetime().astimezone(UTC),
            )
            for stamp, row in schedule.iterrows()
        }
        for closure in self.policy.closed:
            sessions.pop(closure.date, None)
        for special in self.policy.sessions:
            if first <= special.date <= last:
                sessions[special.date] = Session(
                    datetime.combine(special.date, special.open, IST).astimezone(UTC),
                    datetime.combine(special.date, special.close, IST).astimezone(UTC),
                )
        return tuple(sessions[d] for d in sorted(sessions))

    def expected_bars(
        self, start: datetime, end: datetime, timeframe: Timeframe
    ) -> dict[datetime, datetime]:
        """Anchor intervals at session open; clip the final interval to close."""
        start, end = utc(start), utc(end)
        result = {}
        for session in self.sessions(start, end):
            current = session.opens
            while current < session.closes:
                closes = (
                    session.closes
                    if timeframe == Timeframe.DAY_1
                    else min(current + timeframe.duration, session.closes)
                )
                if start <= current < end and closes <= end:
                    result[current] = closes
                current = closes
        return result

    def next_bar(self, timestamp: datetime, timeframe: Timeframe) -> datetime:
        """Next session-aware opening, including weekends and holiday transitions."""
        timestamp = utc(timestamp)
        limit = datetime.combine(
            self.policy.coverage_end + timedelta(days=1), time(), IST
        ).astimezone(UTC)
        for opening in self.expected_bars(timestamp, limit, timeframe):
            if opening > timestamp:
                return opening
        raise CalendarError("no next bar within reviewed coverage")
