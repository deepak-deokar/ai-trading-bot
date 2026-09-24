from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trading_bot.data.contracts import HistoryRequest
from trading_bot.domain.market import Timeframe
from trading_bot.domain.models import Bar

VALUES = dict(
    symbol="RELIANCE",
    timestamp="2026-01-05T09:15:00+05:30",
    open="1500.10",
    high="1501.20",
    low="1499.10",
    close="1500.20",
    volume=100,
)


def test_nse_decimal_and_ist():
    bar = Bar(**VALUES)
    assert bar.timestamp == datetime(2026, 1, 5, 3, 45, tzinfo=UTC)
    assert bar.close - bar.open == Decimal("0.10")
    assert bar.exchange == "NSE" and bar.segment == "CASH"
    assert bar.adjustment_type == "RAW"


@pytest.mark.parametrize(
    "change",
    [
        {"exchange": "BSE"},
        {"segment": "FNO"},
        {"timeframe": "2minute"},
        {"volume": -1},
        {"open_interest": -1},
        {"high": "1"},
        {"low": "9999"},
        {"close": "NaN"},
        {"close": "Infinity"},
        {"volume": True},
        {"open": "1.12345678901"},
        {"timestamp": "2026-01-05T09:15:00"},
    ],
)
def test_invalid_nse_bar(change):
    with pytest.raises(ValidationError):
        Bar(**(VALUES | change))


@pytest.mark.parametrize(
    "timeframe,seconds",
    [
        ("1minute", 60),
        ("5minute", 300),
        ("10minute", 600),
        ("15minute", 900),
        ("30minute", 1800),
        ("1hour", 3600),
        ("1day", 86400),
    ],
)
def test_timeframe_duration_and_serialization(timeframe, seconds):
    tf = Timeframe(timeframe)
    bar = Bar(**(VALUES | {"timeframe": tf}))
    assert bar.interval_seconds == seconds
    assert (tf.next_timestamp(bar.timestamp) - bar.timestamp).total_seconds() == seconds
    assert Bar.model_validate_json(bar.model_dump_json()) == bar


def test_request_range_is_explicit_and_aware():
    with pytest.raises(ValidationError):
        HistoryRequest(
            symbols=("RELIANCE",), start=datetime(2026, 1, 5), end=datetime(2026, 1, 6)
        )
