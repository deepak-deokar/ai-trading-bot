"""UTC research schedules and independent analytical labels; no execution rights."""

from datetime import datetime, time
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, Self

import yaml
from pydantic import Field, field_validator, model_validator

from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel


class SessionLabel(StrEnum):
    ASIA = "ASIA"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    LONDON_NEW_YORK_OVERLAP = "LONDON_NEW_YORK_OVERLAP"
    OFF_SESSION = "OFF_SESSION"


class UTCWindow(DomainModel):
    """Daily UTC [start, end); start > end crosses midnight; equal ends rejected."""

    start: time
    end: time

    @field_validator("start", "end")
    @classmethod
    def clock_only(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("window clocks must omit offsets; configuration is UTC")
        return value

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if self.start == self.end:
            raise ValueError("equal endpoints are ambiguous; omit an unused window")
        return self

    def contains(self, timestamp: datetime) -> bool:
        clock = utc(timestamp).time()
        if self.start < self.end:
            return self.start <= clock < self.end
        return clock >= self.start or clock < self.end


class LabelWindow(UTCWindow):
    label: SessionLabel


class SessionConfig(DomainModel):
    timezone: Literal["UTC"] = "UTC"
    schedule_id: str = Field(min_length=1)
    trading_weekdays: tuple[int, ...] = (0, 1, 2, 3, 4)
    maintenance: UTCWindow | None = None
    label_windows: tuple[LabelWindow, ...] = ()

    @field_validator("trading_weekdays", mode="before")
    @classmethod
    def valid_weekdays(cls, value: object) -> object:
        if not isinstance(value, list | tuple) or not value:
            raise ValueError("at least one weekday required")
        if any(type(day) is not int or day not in range(7) for day in value):
            raise ValueError("weekdays must be integers 0 through 6")
        if len(set(value)) != len(value):
            raise ValueError("weekdays must be unique")
        return value

    @classmethod
    def load(cls, path: Path) -> Self:
        return cls.model_validate(yaml.safe_load(path.read_text()))


class MarketSchedule(Protocol):
    """Future adapters can supply a schedule without changing label classification."""

    def is_theoretically_tradable(self, timestamp: datetime) -> bool: ...


class WeekdaySchedule:
    def __init__(self, config: SessionConfig) -> None:
        self._config = config

    def is_theoretically_tradable(self, timestamp: datetime) -> bool:
        instant = utc(timestamp)
        return instant.weekday() in self._config.trading_weekdays and (
            self._config.maintenance is None
            or not self._config.maintenance.contains(instant)
        )


class ResearchSessionClassifier:
    """First matching configured window wins, even on closed days/maintenance."""

    def __init__(self, config: SessionConfig) -> None:
        self._windows = config.label_windows

    def classify(self, timestamp: datetime) -> SessionLabel:
        instant = utc(timestamp)
        return next(
            (window.label for window in self._windows if window.contains(instant)),
            SessionLabel.OFF_SESSION,
        )
