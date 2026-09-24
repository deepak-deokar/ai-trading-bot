from datetime import datetime

import pytest

from trading_bot.data.calendar import CalendarError, NSECalendar
from trading_bot.data.quality import gap_issues
from trading_bot.domain.market import Timeframe


def dt(value):
    return datetime.fromisoformat(value + "+05:30")


@pytest.fixture(scope="module")
def calendar():
    return NSECalendar()


def test_regular_session(calendar):
    bars = calendar.expected_bars(
        dt("2026-01-05T00:00"), dt("2026-01-06T00:00"), Timeframe.MIN_5
    )
    assert len(bars) == 75
    assert min(bars) == dt("2026-01-05T09:15")
    assert max(bars) == dt("2026-01-05T15:25")
    assert max(bars.values()) == dt("2026-01-05T15:30")


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-01-05T15:25", "2026-01-06T09:20"),
        ("2026-01-09T15:25", "2026-01-12T09:20"),
        ("2026-01-23T15:25", "2026-01-27T09:20"),
    ],
)
def test_no_overnight_weekend_or_holiday_phantom_gaps(calendar, start, end):
    expected = calendar.expected_bars(dt(start), dt(end), Timeframe.MIN_5)
    assert len(expected) == 2
    assert gap_issues("RELIANCE", expected, set(expected)) == []


def test_intraday_missing_and_next_session(calendar):
    expected = calendar.expected_bars(
        dt("2026-01-05T09:15"), dt("2026-01-05T09:30"), Timeframe.MIN_5
    )
    observed = set(expected) - {dt("2026-01-05T09:20")}
    assert len(gap_issues("RELIANCE", expected, observed)) == 1
    assert calendar.next_bar(dt("2026-01-09T15:25"), Timeframe.MIN_5) == dt(
        "2026-01-12T09:15"
    )


def test_holiday_override_and_budget_sunday(calendar):
    assert not calendar.expected_bars(
        dt("2026-01-15T00:00"), dt("2026-01-16T00:00"), Timeframe.MIN_5
    )
    assert (
        len(
            calendar.expected_bars(
                dt("2026-02-01T00:00"), dt("2026-02-02T00:00"), Timeframe.MIN_5
            )
        )
        == 75
    )


def test_unsupported_calendar_year_fails_closed(calendar):
    with pytest.raises(CalendarError):
        calendar.expected_bars(
            dt("2027-01-04T09:15"), dt("2027-01-04T15:30"), Timeframe.MIN_5
        )


def test_daily_and_clipped_hourly_availability(calendar):
    start, end = dt("2026-01-05T09:15"), dt("2026-01-05T15:30")
    daily = calendar.expected_bars(start, end, Timeframe.DAY_1)
    assert daily == {start: end}
    hours = calendar.expected_bars(start, end, Timeframe.HOUR_1)
    assert len(hours) == 7 and hours[dt("2026-01-05T15:15")] == end
    assert not calendar.expected_bars(start, dt("2026-01-05T09:19"), Timeframe.MIN_5)
