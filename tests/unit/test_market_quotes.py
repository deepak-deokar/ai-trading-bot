from datetime import UTC, datetime
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from trading_bot.domain.contracts import ContractSpecification
from trading_bot.domain.models import Side
from trading_bot.domain.positions import PositionDirection, raw_price_movement
from trading_bot.domain.quotes import MarketQuote, QuoteSource, SpreadAlignmentError


def quote(**changes):
    return MarketQuote.model_validate(
        {
            "canonical_symbol": "XAUUSD",
            "timestamp": datetime(2026, 1, 5, tzinfo=UTC),
            "bid": Decimal("4100.20"),
            "ask": Decimal("4100.70"),
            "source": QuoteSource.TEST_FIXTURE,
        }
        | changes
    )


def synthetic_contract(tick):
    return ContractSpecification(
        contract_size=Decimal("37"),
        minimum_volume=Decimal("2"),
        volume_step=Decimal("1"),
        tick_size=Decimal(tick),
        specification_source="TEST_FIXTURE",
    )


def test_quote_spread_mid_and_immutable():
    value = quote()
    assert value.spread == Decimal("0.50")
    assert value.mid == Decimal("4100.45")
    assert value.source == QuoteSource.TEST_FIXTURE
    assert value.model_dump(mode="json")["bid"] == "4100.20"
    with pytest.raises(ValidationError):
        value.bid = Decimal("1")


@pytest.mark.parametrize("field", ["bid", "ask"])
@pytest.mark.parametrize(
    "value",
    [
        1.2,
        1,
        "1.2",
        True,
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_positive_decimal_only(field, value):
    with pytest.raises(ValidationError):
        quote(**{field: value})


def test_crossed_and_zero_spread():
    with pytest.raises(ValidationError, match="crossed"):
        quote(bid=Decimal("4101"))
    zero = quote(ask=Decimal("4100.20"))
    assert zero.spread == Decimal("0")
    assert zero.mid == zero.bid
    assert zero.spread_in_ticks(synthetic_contract("0.3")) == Decimal(0)


def test_utc():
    timestamp = datetime.fromisoformat("2026-01-05T05:30:00+05:30")
    value = quote(timestamp=timestamp)
    assert value.timestamp == datetime(2026, 1, 5, tzinfo=UTC)
    assert value.timestamp.tzinfo is UTC
    with pytest.raises(ValidationError):
        quote(timestamp=timestamp.replace(tzinfo=None))


def test_side_is_required_and_mid_not_executable():
    value = quote()
    assert value.price_for_side(Side.BUY) == value.ask
    assert value.price_for_side(Side.SELL) == value.bid
    assert value.mid not in (
        value.price_for_side(Side.BUY),
        value.price_for_side(Side.SELL),
    )
    with pytest.raises(TypeError):
        value.price_for_side()
    with pytest.raises(ValueError):
        value.price_for_side("MID")


@pytest.mark.parametrize("direction", list(PositionDirection))
def test_long_short_spread_disadvantage(direction):
    value = quote()
    opening = value.price_for_side(direction.opening_side)
    closing = value.price_for_side(direction.closing_side)
    assert raw_price_movement(direction, opening, closing) == -value.spread


@pytest.mark.parametrize("tick,expected", [("0.25", "2"), ("0.1", "5"), ("0.5", "1")])
def test_explicit_ticks_no_pip_assumption(tick, expected):
    assert quote().spread_in_ticks(synthetic_contract(tick)) == Decimal(expected)


def test_fractional_ticks_and_wrong_symbol_rejected():
    with pytest.raises(SpreadAlignmentError):
        quote().spread_in_ticks(synthetic_contract("0.3"))
    with pytest.raises(ValueError, match="symbols"):
        quote(canonical_symbol="RELIANCE").spread_in_ticks(synthetic_contract("0.25"))


def test_exact_arithmetic_low_context():
    value = quote(
        bid=Decimal("12345678901234567890.001"), ask=Decimal("12345678901234567890.002")
    )
    with localcontext() as context:
        context.prec = 2
        assert value.spread == Decimal("0.001")
        assert value.mid == Decimal("12345678901234567890.0015")
        assert value.spread_in_ticks(synthetic_contract("0.0005")) == Decimal("2")


def test_source_optional_and_not_implicitly_mt5():
    assert quote(source=None).source is None
    with pytest.raises(ValidationError):
        quote(source="UNKNOWN")
