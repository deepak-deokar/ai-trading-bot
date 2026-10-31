from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from trading_bot.domain.models import Side
from trading_bot.domain.positions import (
    PositionDirection,
    PositionSnapshot,
    raw_price_movement,
)

START = datetime(2026, 1, 5, 12, tzinfo=UTC)


def sample(**changes):
    return PositionSnapshot.model_validate(
        {
            "canonical_symbol": "XAUUSD",
            "direction": "LONG",
            "volume": Decimal("0.7"),
            "entry_price": Decimal("4100.50"),
            "opened_at": START,
        }
        | changes
    )


@pytest.mark.parametrize(
    "direction,exit_price,expected",
    [
        ("LONG", "4102.75", "2.25"),
        ("LONG", "4098.25", "-2.25"),
        ("SHORT", "4098.25", "2.25"),
        ("SHORT", "4102.75", "-2.25"),
        ("LONG", "4100.50", "0"),
        ("SHORT", "4100.50", "0"),
    ],
)
def test_directional_movement(direction, exit_price, expected):
    assert raw_price_movement(
        PositionDirection(direction), Decimal("4100.50"), Decimal(exit_price)
    ) == Decimal(expected)


def test_buy_sell_relationships_reuse_generic_side():
    assert PositionDirection.LONG.opening_side is Side.BUY
    assert PositionDirection.LONG.closing_side is Side.SELL
    assert PositionDirection.SHORT.opening_side is Side.SELL
    assert PositionDirection.SHORT.closing_side is Side.BUY


@pytest.mark.parametrize("direction", list(PositionDirection))
@pytest.mark.parametrize("symbol", ["XAUUSD", "RELIANCE"])
def test_open_closed_and_market_independence(direction, symbol):
    opened = sample(direction=direction, canonical_symbol=symbol)
    assert opened.volume > 0
    assert opened.closed_at is None and opened.exit_price is None
    assert "exchange" not in opened.model_dump()
    closed = sample(
        direction=direction,
        canonical_symbol=symbol,
        closed_at=START + timedelta(minutes=5),
        exit_price=Decimal("4101"),
    )
    assert closed.closed_at > closed.opened_at
    with pytest.raises(ValidationError):
        opened.direction = PositionDirection.SHORT
    assert closed.model_dump(mode="json")["entry_price"] == "4100.50"


@pytest.mark.parametrize("field", ["volume", "entry_price", "exit_price"])
@pytest.mark.parametrize(
    "value",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        1.5,
        1,
        "1.5",
        True,
    ],
)
def test_exact_positive_values(field, value):
    changes = {field: value}
    if field == "exit_price":
        changes["closed_at"] = START
    with pytest.raises(ValidationError):
        sample(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"closed_at": START},
        {"exit_price": Decimal("4100")},
        {"closed_at": START - timedelta(seconds=1), "exit_price": Decimal("4100")},
        {"opened_at": START.replace(tzinfo=None)},
        {"closed_at": START.replace(tzinfo=None), "exit_price": Decimal("4100")},
        {"direction": "SELL"},
        {"opened_at": None},
    ],
)
def test_invalid_states(changes):
    with pytest.raises(ValidationError):
        sample(**changes)


def test_normalizes_utc_and_allows_equal_close_instant():
    offset = datetime.fromisoformat("2026-01-05T17:30:00+05:30")
    position = sample(opened_at=offset, closed_at=offset, exit_price=Decimal("4100"))
    assert position.opened_at == START and position.closed_at == START
    assert position.opened_at.tzinfo is UTC
    assert position.closed_at.tzinfo is UTC


@pytest.mark.parametrize(
    "value", [1.5, "1.5", Decimal("0"), Decimal("-1"), Decimal("NaN")]
)
def test_movement_rejects_invalid_prices(value):
    for entry, exit_price in [(value, Decimal("1")), (Decimal("1"), value)]:
        with pytest.raises(ValueError):
            raw_price_movement(PositionDirection.LONG, entry, exit_price)


def test_movement_exact_under_low_precision_and_bad_direction():
    with localcontext() as context:
        context.prec = 2
        assert raw_price_movement(
            PositionDirection.LONG,
            Decimal("12345678901234567890.123"),
            Decimal("12345678901234567891.124"),
        ) == Decimal("1.001")
    with pytest.raises(ValueError):
        raw_price_movement("INVALID", Decimal("1"), Decimal("2"))
