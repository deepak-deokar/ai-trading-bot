from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from trading_bot.domain.sessions import (
    ResearchSessionClassifier,
    SessionConfig,
    SessionLabel,
    UTCWindow,
    WeekdaySchedule,
)


def config(**changes):
    data = SessionConfig.load(Path("config/xauusd_sessions.yaml")).model_dump()
    return SessionConfig.model_validate(data | changes)


def instant(day=5, hour=0, minute=0):
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    "day,expected", [(5, True), (9, True), (10, False), (11, False), (12, True)]
)
def test_week(day, expected):
    assert WeekdaySchedule(config()).is_theoretically_tradable(instant(day)) == expected


@pytest.mark.parametrize("hour", [0, 4, 12, 22, 23])
def test_near_24_hours_not_nse(hour):
    assert WeekdaySchedule(config()).is_theoretically_tradable(instant(hour=hour))


@pytest.mark.parametrize(
    "hour,minute,expected",
    [(21, 59, True), (22, 0, False), (22, 29, False), (22, 30, True)],
)
def test_maintenance(hour, minute, expected):
    schedule = WeekdaySchedule(config(maintenance={"start": "22:00", "end": "22:30"}))
    assert (
        schedule.is_theoretically_tradable(instant(hour=hour, minute=minute))
        == expected
    )


@pytest.mark.parametrize(
    "hour,minute,expected",
    [(23, 29, True), (23, 30, False), (0, 0, False), (0, 29, False), (0, 30, True)],
)
def test_cross_midnight(hour, minute, expected):
    schedule = WeekdaySchedule(config(maintenance={"start": "23:30", "end": "00:30"}))
    assert (
        schedule.is_theoretically_tradable(instant(hour=hour, minute=minute))
        == expected
    )


@pytest.mark.parametrize(
    "hour,minute,label",
    [
        (0, 0, "ASIA"),
        (7, 59, "ASIA"),
        (8, 0, "LONDON"),
        (12, 59, "LONDON"),
        (13, 0, "LONDON_NEW_YORK_OVERLAP"),
        (15, 59, "LONDON_NEW_YORK_OVERLAP"),
        (16, 0, "NEW_YORK"),
        (20, 59, "NEW_YORK"),
        (21, 0, "OFF_SESSION"),
    ],
)
def test_labels(hour, minute, label):
    classifier = ResearchSessionClassifier(config())
    timestamp = instant(hour=hour, minute=minute)
    assert classifier.classify(timestamp) == label
    assert classifier.classify(timestamp) == classifier.classify(timestamp)


def test_labels_independent_of_closures():
    cfg = config(maintenance={"start": "13:00", "end": "14:00"})
    for timestamp in (instant(hour=13), instant(day=10, hour=13)):
        assert not WeekdaySchedule(cfg).is_theoretically_tradable(timestamp)
        assert (
            ResearchSessionClassifier(cfg).classify(timestamp)
            == SessionLabel.LONDON_NEW_YORK_OVERLAP
        )
    assert (
        ResearchSessionClassifier(config(label_windows=[])).classify(instant())
        == SessionLabel.OFF_SESSION
    )


def test_utc_conversion_and_naive_rejection():
    cfg = config()
    schedule = WeekdaySchedule(cfg)
    classifier = ResearchSessionClassifier(cfg)
    # Local Monday is still Sunday UTC.
    offset = datetime.fromisoformat("2026-01-12T00:30:00+05:30")
    assert not schedule.is_theoretically_tradable(offset)
    assert classifier.classify(offset) == classifier.classify(offset.astimezone(UTC))
    for method in (
        schedule.is_theoretically_tradable,
        classifier.classify,
        UTCWindow(start="22:00", end="23:00").contains,
    ):
        with pytest.raises(ValueError, match="timezone-aware"):
            method(datetime(2026, 1, 5))


@pytest.mark.parametrize(
    "changes",
    [
        {"timezone": "Asia/Kolkata"},
        {"trading_weekdays": [7]},
        {"trading_weekdays": [True]},
        {"trading_weekdays": [0, 0]},
        {"trading_weekdays": []},
        {"maintenance": {"start": "22:00", "end": "22:00"}},
        {"maintenance": {"start": "22:00+01:00", "end": "23:00"}},
    ],
)
def test_invalid_configuration(changes):
    with pytest.raises(ValidationError):
        config(**changes)
