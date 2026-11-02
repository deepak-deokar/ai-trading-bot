from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from trading_bot.domain.positions import PositionDirection as Direction
from trading_bot.domain.quotes import MarketQuote, QuoteSource
from trading_bot.execution.xauusd import ExecutionError, ExecutionFill, XAUUSDExecution

T = datetime(2024, 2, 20, 10, tzinfo=UTC)
SYNTHETIC_VOLUME = Decimal("0.37")


def quote(bid="2000.00", ask="2000.50", timestamp=T):
    return MarketQuote(
        canonical_symbol="XAUUSD",
        timestamp=timestamp,
        bid=Decimal(bid),
        ask=Decimal(ask),
        source=QuoteSource.TEST_FIXTURE,
    )


def flat():
    return XAUUSDExecution(simulation_id=UUID(int=123))


def opened(direction=Direction.LONG):
    return flat().open(
        direction,
        SYNTHETIC_VOLUME,
        quote(),
        timestamp=T,
        source_market_data_id="synthetic:entry",
    )


@pytest.mark.parametrize(
    "direction,entry,exit_price,entry_action,exit_action",
    [
        (Direction.LONG, "2000.50", "2000.00", "BUY", "SELL"),
        (Direction.SHORT, "2000.00", "2000.50", "SELL", "BUY"),
    ],
)
def test_sides_and_unchanged_spread(
    direction, entry, exit_price, entry_action, exit_action
):
    initial = flat()
    start = opened(direction)
    end = start.close(quote(), timestamp=T, source_market_data_id="synthetic:exit")
    assert (
        initial.status == "FLAT" and start.status == "OPEN" and end.status == "CLOSED"
    )
    assert start.position.entry_price == Decimal(entry)
    assert end.position.exit_price == Decimal(exit_price)
    assert [f.action.name for f in end.fills] == [entry_action, exit_action]
    assert end.price_movement == Decimal("-0.50") == -quote().spread
    assert end.fills[0].position_id == end.fills[1].position_id
    assert end.fills[0].execution_id != end.fills[1].execution_id
    assert end.fills[0].strategy_decision_id is None
    assert end == opened(direction).close(
        quote(), timestamp=T, source_market_data_id="synthetic:exit"
    )


@pytest.mark.parametrize(
    "direction,bid,ask,movement",
    [
        (Direction.LONG, "2002", "2002.5", "1.5"),
        (Direction.LONG, "1998", "1998.5", "-2.5"),
        (Direction.SHORT, "1998", "1998.5", "1.5"),
        (Direction.SHORT, "2002", "2002.5", "-2.5"),
    ],
)
def test_movement(direction, bid, ask, movement):
    t = T + timedelta(seconds=1)
    end = opened(direction).close(
        quote(bid, ask, t), timestamp=t, source_market_data_id="synthetic:later"
    )
    assert end.price_movement == Decimal(movement)


@pytest.mark.parametrize("direction", [Direction.LONG, Direction.SHORT])
def test_invalid_transitions_no_mutation(direction):
    initial = flat()
    before = initial.model_dump()
    with pytest.raises(ExecutionError):
        initial.close(quote(), timestamp=T, source_market_data_id="synthetic")
    assert initial.model_dump() == before
    state = opened(direction)
    before = state.model_dump()
    for candidate in Direction:
        with pytest.raises(ExecutionError):
            state.open(
                candidate,
                SYNTHETIC_VOLUME,
                quote(),
                timestamp=T,
                source_market_data_id="synthetic",
            )
    assert state.model_dump() == before
    closed = state.close(quote(), timestamp=T, source_market_data_id="synthetic")
    before = closed.model_dump()
    with pytest.raises(ExecutionError):
        closed.close(quote(), timestamp=T, source_market_data_id="synthetic")
    assert closed.model_dump() == before
    with pytest.raises(ValidationError):
        state.position = None


@pytest.mark.parametrize("volume", [0.37, Decimal("0"), Decimal("-1")])
def test_explicit_validated_volume(volume):
    state = flat()
    with pytest.raises(ValueError):
        state.open(
            Direction.LONG,
            volume,
            quote(),
            timestamp=T,
            source_market_data_id="synthetic",
        )
    assert state.status == "FLAT"


def test_no_midpoint_or_arbitrary_fill():
    state = opened()
    payload = state.fills[0].model_dump() | {"executed_price": quote().mid}
    with pytest.raises(ValidationError):
        ExecutionFill.model_validate(payload)
    payload = state.fills[0].model_dump() | {"executed_price": 2000.5}
    with pytest.raises(ValidationError):
        ExecutionFill.model_validate(payload)
    with pytest.raises(TypeError):
        flat().open(
            Direction.LONG,
            SYNTHETIC_VOLUME,
            quote(),
            timestamp=T,
            source_market_data_id="synthetic",
            executed_price=quote().mid,
        )


@pytest.mark.parametrize("bid,ask", [("0", "1"), ("-1", "1"), ("2", "1")])
def test_invalid_quotes(bid, ask):
    with pytest.raises(ValidationError):
        quote(bid, ask)


def test_utc_and_future_quotes():
    with pytest.raises(ValidationError):
        quote(timestamp=T.replace(tzinfo=None))
    with pytest.raises(ValueError):
        flat().open(
            Direction.LONG,
            SYNTHETIC_VOLUME,
            quote(),
            timestamp=T.replace(tzinfo=None),
            source_market_data_id="synthetic",
        )
    for offset in (-1, 1):
        with pytest.raises(ExecutionError):
            flat().open(
                Direction.LONG,
                SYNTHETIC_VOLUME,
                quote(timestamp=T + timedelta(seconds=offset)),
                timestamp=T,
                source_market_data_id="synthetic",
            )
    state = opened()
    with pytest.raises(ExecutionError):
        state.close(
            quote(timestamp=T - timedelta(seconds=1)),
            timestamp=T - timedelta(seconds=1),
            source_market_data_id="synthetic",
        )
    assert state.position.entry_price == Decimal("2000.50")
    # Future quotes do not participate in an earlier fill.
    quote("9999", "10000", T + timedelta(days=1))
    assert opened() == state
