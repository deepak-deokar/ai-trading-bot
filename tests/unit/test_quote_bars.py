from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trading_bot.domain.quote_bars import QuoteBar


def bar(**changes):
    return QuoteBar.model_validate(
        dict(
            opening_timestamp=datetime(2024, 1, 16, 10, tzinfo=UTC),
            tick_count=2,
            bid_open=Decimal("10"),
            bid_high=Decimal("12"),
            bid_low=Decimal("9"),
            bid_close=Decimal("11"),
            ask_open=Decimal("10.5"),
            ask_high=Decimal("12.5"),
            ask_low=Decimal("9.5"),
            ask_close=Decimal("11.5"),
        )
        | changes
    )


def test_opening_semantics_and_decimal():
    b = bar()
    assert b.closing_timestamp == b.opening_timestamp + timedelta(minutes=5)
    assert isinstance(b.bid_open, Decimal) and b.ask_open != b.bid_open
    with pytest.raises(ValidationError):
        b.tick_count = 3


@pytest.mark.parametrize(
    "changes",
    [
        {"bid_open": 10.0},
        {"ask_open": Decimal("0")},
        {"bid_high": Decimal("9")},
        {"ask_close": Decimal("10")},
        {"tick_count": 0},
        {"interval": "1minute"},
        {"opening_timestamp": datetime(2024, 1, 16)},
        {"opening_timestamp": datetime(2024, 1, 16, 10, 1, tzinfo=UTC)},
        {"bid_open": Decimal("10.00000000001")},
    ],
)
def test_invalid_bars(changes):
    with pytest.raises(ValidationError):
        bar(**changes)
