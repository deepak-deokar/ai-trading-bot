from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from trading_bot.data.providers.histdata import (
    CANONICAL_SYMBOL,
    PROVIDER_SYMBOL,
    five_minute_view,
    parse_tick,
    parse_timestamp,
    quality_statistics,
    read_pilot_day,
)


def test_mapping_and_decimal_and_volume():
    tick = parse_tick("20240116 120000123,2020.123456789,2020.223456789,000.00")
    assert CANONICAL_SYMBOL == "XAUUSD" and PROVIDER_SYMBOL == "XAU/USD"
    assert tick.quote.canonical_symbol == CANONICAL_SYMBOL
    assert tick.quote.bid == Decimal("2020.123456789")
    assert isinstance(tick.quote.ask, Decimal)
    assert tick.source_volume == "000.00"
    assert tick.quote.timestamp == datetime(2024, 1, 16, 17, 0, 0, 123000, tzinfo=UTC)


@pytest.mark.parametrize("stamp", ["20240116 120000000", "20240716 120000000"])
def test_fixed_est_not_dst(stamp):
    assert parse_timestamp(stamp).hour == 17
    assert parse_timestamp(stamp).tzinfo is UTC


@pytest.mark.parametrize(
    "line",
    [
        "20240116 120000000,2,1,0",
        "20240116 120000000,0,1,0",
        "20240116 120000000,-1,1,0",
        "20240116 120000000,NaN,1,0",
        "20240116 120000000,1,Infinity,0",
        "20240116 120000000,no,2,0",
        "20240116 120000,1,2,0",
        "20240116 250000000,1,2,0",
        "20240116 120000000,1,2",
        "20240116 120000000,1,2,0,extra",
    ],
)
def test_invalid_records(line):
    with pytest.raises(ValueError):
        parse_tick(line)


def test_order_duplicates_rejections_and_bars():
    lines = [
        "20240116 120500000,12,14,0",
        "20240116 120000000,10,11,0",
        "20240116 120000000,11,13,0",
        "20240116 120459999,9,12,0",
        "20240116 120200000,3,2,0",
        "20240116 120300000,0,2,0",
        "20240117 120000000,1,2,0",
    ]
    pilot = read_pilot_day(lines, date(2024, 1, 16))
    assert (pilot.raw_count, len(pilot.ticks), pilot.invalid_count) == (6, 4, 2)
    assert pilot.crossed_count == 1 and pilot.duplicate_timestamp_count == 1
    assert pilot.rejected_lines == (5, 6)
    assert [t.quote.bid for t in pilot.ticks] == list(map(Decimal, [10, 11, 9, 12]))
    bars = five_minute_view(pilot.ticks)
    assert len(bars) == 2
    assert bars[0]["timestamp"] == "2024-01-16T17:00:00+00:00"
    assert bars[0]["bid"] == dict(open=10, high=11, low=9, close=9)
    assert bars[0]["ask"] == dict(open=11, high=13, low=11, close=12)
    assert bars[1]["timestamp"] == "2024-01-16T17:05:00+00:00"
    stats = quality_statistics(pilot)
    assert (stats["spread_min"], stats["spread_median"], stats["spread_max"]) == (
        "1",
        "2",
        "3",
    )
    assert stats["maximum_tick_gap_ms"] == 299999


def test_empty_and_weekend():
    with pytest.raises(ValueError):
        read_pilot_day([], date(2024, 1, 20))
    with pytest.raises(ValueError):
        quality_statistics(read_pilot_day([], date(2024, 1, 16)))
    assert five_minute_view([]) == []
