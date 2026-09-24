"""Typed NSE CASH identities and interval vocabulary."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum


class Exchange(StrEnum):
    NSE = "NSE"


class Segment(StrEnum):
    CASH = "CASH"


class AdjustmentType(StrEnum):
    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    FULLY_ADJUSTED = "FULLY_ADJUSTED"


class Timeframe(StrEnum):
    MIN_1 = "1minute"
    MIN_5 = "5minute"
    MIN_10 = "10minute"
    MIN_15 = "15minute"
    MIN_30 = "30minute"
    HOUR_1 = "1hour"
    DAY_1 = "1day"

    @property
    def duration(self) -> timedelta:
        """Nominal duration; calendar clips terminal bars and daily sessions."""
        return timedelta(
            seconds={
                "1minute": 60,
                "5minute": 300,
                "10minute": 600,
                "15minute": 900,
                "30minute": 1800,
                "1hour": 3600,
                "1day": 86400,
            }[self.value]
        )

    def next_timestamp(self, timestamp: datetime) -> datetime:
        """Nominal next opening; use calendar.next_bar across session boundaries."""
        return utc(timestamp) + self.duration


def utc(value: datetime) -> datetime:
    """Reject naive instants; never infer a timezone in generic domain code."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(UTC)
