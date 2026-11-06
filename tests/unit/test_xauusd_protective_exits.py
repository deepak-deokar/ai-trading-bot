"""Bounded offline synthetic exit mechanics; no strategy or broker assumptions."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from trading_bot.domain.contracts import ContractSpecification, SpecificationSource
from trading_bot.domain.positions import PositionDirection as Direction
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote, QuoteSource
from trading_bot.execution.accounting import Commission, LinearUSDContract, realize_usd
from trading_bot.execution.protection import (
    ProtectiveBarEvidence,
    ProtectiveInstruction,
)
from trading_bot.execution.protective_exits import evaluate_bar, evaluate_quote
from trading_bot.execution.xauusd import ExecutionError, ExecutionFill, XAUUSDExecution

D = Decimal
T = datetime(2024, 2, 20, 10, tzinfo=UTC)
END = T + timedelta(minutes=5)


def quote(bid="2000", ask="2001", timestamp=T):
    return MarketQuote(
        canonical_symbol="XAUUSD",
        timestamp=timestamp,
        bid=D(bid),
        ask=D(ask),
        source=QuoteSource.TEST_FIXTURE,
    )


def setup(direction=Direction.LONG, **changes):
    state = XAUUSDExecution(simulation_id=UUID(int=10)).open(
        direction,
        D("0.5"),
        quote(),
        timestamp=T,
        source_market_data_id="synthetic:entry",
    )
    values = dict(
        position_id=state.position.position_id,
        direction=direction,
        stop_price=D("1995" if direction == Direction.LONG else "2005"),
        target_price=D("2005" if direction == Direction.LONG else "1995"),
        created_at=T,
        creation_quote=quote(),
        source_identity="synthetic:protection",
    )
    values.update(changes)
    return state, ProtectiveInstruction(**values)


def bar(**changes):
    values = dict(
        opening_timestamp=T,
        bid_open=D("2000"),
        bid_high=D("2002"),
        bid_low=D("1998"),
        bid_close=D("2000"),
        ask_open=D("2001"),
        ask_high=D("2003"),
        ask_low=D("1999"),
        ask_close=D("2001"),
        tick_count=10,
    )
    values.update({k: D(v) if isinstance(v, str) else v for k, v in changes.items()})
    return QuoteBar(**values)


def run_bar(state, instruction, observation, timestamp=END):
    return evaluate_bar(
        state,
        instruction,
        observation,
        evaluated_at=timestamp,
        source_market_data_id="synthetic:bar",
    )


@pytest.mark.parametrize(
    "direction,bid,ask,trigger,price",
    [
        (Direction.LONG, "1995", "1996", "STOP_TRIGGERED", "1995"),
        (Direction.LONG, "2005", "2006", "TARGET_TRIGGERED", "2005"),
        (Direction.SHORT, "2004", "2005", "STOP_TRIGGERED", "2005"),
        (Direction.SHORT, "1994", "1995", "TARGET_TRIGGERED", "1995"),
        (Direction.LONG, "1993", "1994", "STOP_TRIGGERED", "1993"),
        (Direction.SHORT, "2006", "2007", "STOP_TRIGGERED", "2007"),
        (Direction.LONG, "2007", "2008", "TARGET_TRIGGERED", "2007"),
        (Direction.SHORT, "1992", "1993", "TARGET_TRIGGERED", "1993"),
    ],
)
def test_exact_quote_execution(direction, bid, ask, trigger, price):
    state, instruction = setup(direction)
    observation = quote(bid, ask, END)
    result = evaluate_quote(
        state,
        instruction,
        observation,
        evaluated_at=END,
        source_market_data_id="synthetic:quote",
    )
    assert result.trigger == trigger
    assert result.fill_price == D(price)
    assert result.lifecycle.position.volume == state.position.volume
    assert result.lifecycle.fills[-1].quote == observation
    assert result.lifecycle.fills[-1].protective_bar is None
    assert not result.intrabar_ambiguous
    assert result.trigger_market_side == (
        "BID" if direction == Direction.LONG else "ASK"
    )
    assert result.execution_side == direction.closing_side
    again = evaluate_quote(
        result.lifecycle,
        instruction,
        observation,
        evaluated_at=END,
        source_market_data_id="synthetic:later",
    )
    assert again.trigger == "ALREADY_CLOSED"
    assert again.fill_id is None
    assert len(again.lifecycle.fills) == 2


@pytest.mark.parametrize(
    "direction,values,trigger,price",
    [
        (
            Direction.LONG,
            {"bid_low": "1995", "ask_low": "1996"},
            "STOP_TRIGGERED",
            "1995",
        ),
        (
            Direction.LONG,
            {"bid_high": "2005", "ask_high": "2006"},
            "TARGET_TRIGGERED",
            "2005",
        ),
        (Direction.SHORT, {"ask_high": "2005"}, "STOP_TRIGGERED", "2005"),
        (
            Direction.SHORT,
            {"bid_low": "1994", "ask_low": "1995"},
            "TARGET_TRIGGERED",
            "1995",
        ),
        (
            Direction.LONG,
            {
                "bid_open": "1993",
                "bid_low": "1993",
                "ask_open": "1994",
                "ask_low": "1994",
            },
            "STOP_TRIGGERED",
            "1993",
        ),
        (
            Direction.SHORT,
            {
                "bid_open": "2006",
                "bid_high": "2006",
                "ask_open": "2007",
                "ask_high": "2007",
            },
            "STOP_TRIGGERED",
            "2007",
        ),
        (
            Direction.LONG,
            {
                "bid_open": "2007",
                "bid_high": "2008",
                "ask_open": "2008",
                "ask_high": "2009",
            },
            "TARGET_TRIGGERED",
            "2005",
        ),
        (
            Direction.SHORT,
            {
                "bid_open": "1992",
                "bid_low": "1991",
                "ask_open": "1993",
                "ask_low": "1992",
            },
            "TARGET_TRIGGERED",
            "1995",
        ),
        (
            Direction.LONG,
            {
                "bid_low": "1994",
                "ask_low": "1995",
                "bid_high": "2006",
                "ask_high": "2007",
            },
            "STOP_TRIGGERED_AMBIGUOUS",
            "1995",
        ),
        (
            Direction.SHORT,
            {
                "bid_low": "1994",
                "ask_low": "1995",
                "bid_high": "2006",
                "ask_high": "2007",
            },
            "STOP_TRIGGERED_AMBIGUOUS",
            "2005",
        ),
    ],
)
def test_separate_ohlc_sides_and_gap_conventions(direction, values, trigger, price):
    state, instruction = setup(direction)
    observation = bar(**values)
    result = run_bar(state, instruction, observation)
    assert result.trigger == trigger
    assert result.fill_price == D(price)
    assert result == run_bar(state, instruction, observation)
    assert result.intrabar_ambiguous == (trigger == "STOP_TRIGGERED_AMBIGUOUS")
    assert bool(result.ambiguity_reason) == result.intrabar_ambiguous
    fill = result.lifecycle.fills[-1]
    assert fill.timestamp == END
    assert fill.quote is None
    assert fill.bid is fill.ask is fill.spread is None
    assert fill.protective_bar.bar == observation
    assert result.lifecycle.position.volume == D("0.5")
    # Later observations cannot add another close.
    again = run_bar(result.lifecycle, instruction, observation)
    assert again.trigger == "ALREADY_CLOSED"
    assert again.lifecycle == result.lifecycle
    assert again.fill_price is None
    with pytest.raises(ExecutionError):
        result.lifecycle.close_protective_bar(fill.protective_bar)


@pytest.mark.parametrize(
    "direction,bid,ask,values",
    [
        # Midpoints/other side cross the target but executable side does not.
        (Direction.LONG, "2004", "2008", {"bid_high": "2004", "ask_high": "2008"}),
        (Direction.SHORT, "1992", "1996", {"bid_low": "1992", "ask_low": "1996"}),
    ],
)
def test_midpoint_and_wrong_side_cannot_trigger(direction, bid, ask, values):
    state, instruction = setup(direction)
    result = evaluate_quote(
        state,
        instruction,
        quote(bid, ask, END),
        evaluated_at=END,
        source_market_data_id="synthetic:wide-spread",
    )
    assert result.trigger == "NO_EXIT"
    assert result.lifecycle == state
    assert run_bar(state, instruction, bar(**values)).trigger == "NO_EXIT"


@pytest.mark.parametrize(
    "direction,field,value",
    [
        (Direction.LONG, "stop_price", D("2000")),
        (Direction.LONG, "target_price", D("2000")),
        (Direction.SHORT, "stop_price", D("2001")),
        (Direction.SHORT, "target_price", D("2001")),
        (Direction.LONG, "stop_price", 1995.0),
        (Direction.LONG, "target_price", 2005.0),
        (Direction.LONG, "stop_price", D("0")),
        (Direction.LONG, "created_at", T.replace(tzinfo=None)),
    ],
)
def test_invalid_instructions(direction, field, value):
    with pytest.raises(ValidationError):
        setup(direction, **{field: value})


def test_causality_identity_and_freezing():
    state, instruction = setup()
    observation = bar(bid_low="1995")
    for invalid_time in (END - timedelta(microseconds=1), END.replace(tzinfo=None)):
        with pytest.raises(ValueError):
            run_bar(state, instruction, observation, invalid_time)
    with pytest.raises(ValueError):
        run_bar(state, instruction, bar(opening_timestamp=T - timedelta(minutes=5)))
    with pytest.raises(ValueError):
        evaluate_quote(
            state,
            instruction,
            quote(timestamp=END),
            evaluated_at=T,
            source_market_data_id="synthetic:future",
        )
    wrong_id = instruction.model_copy(update={"position_id": UUID(int=999)})
    with pytest.raises(ExecutionError):
        run_bar(state, wrong_id, observation)
    with pytest.raises(ExecutionError):
        run_bar(XAUUSDExecution(simulation_id=UUID(int=1)), instruction, observation)
    result = run_bar(state, instruction, observation)
    # A radically different future bar is never an input to the earlier evaluation.
    bar(opening_timestamp=END, bid_high="9999", ask_high="10000")
    assert result == run_bar(state, instruction, observation)
    assert (
        run_bar(state, instruction, observation, END + timedelta(hours=2)).fill_price
        == result.fill_price
    )
    assert result.lifecycle.fills[-1].timestamp == END
    assert instruction.created_at.tzinfo == UTC
    with pytest.raises(ValidationError):
        instruction.stop_price = D("1990")
    offset = T.astimezone(timezone(timedelta(hours=5)))
    assert setup(created_at=offset)[1].created_at == T


def test_no_target_and_bar_evidence_cannot_forge_quote_or_fill():
    state, instruction = setup(target_price=None)
    assert (
        run_bar(state, instruction, bar(bid_high="2010", ask_high="2011")).trigger
        == "NO_EXIT"
    )
    result = run_bar(state, instruction, bar(bid_low="1994"))
    fill = result.lifecycle.fills[-1]
    for changes in (
        {"executed_price": D("1996")},
        {"quote": quote(timestamp=END)},
        {"intent": "OPEN"},
    ):
        with pytest.raises(ValidationError):
            ExecutionFill.model_validate(fill.model_dump() | changes)
    evidence = ProtectiveBarEvidence(
        instruction=instruction,
        bar=bar(),
        evaluated_at=END,
        source_market_data_id="synthetic",
    )
    with pytest.raises(ExecutionError):
        state.close_protective_bar(evidence)


def test_protective_fill_accounting():
    state, instruction = setup()
    result = run_bar(
        state,
        instruction,
        bar(bid_low="1993", bid_open="1993", ask_low="1994", ask_open="1994"),
    )
    contract = LinearUSDContract(
        specification=ContractSpecification(
            contract_size=D("10"),
            minimum_volume=D("0.25"),
            maximum_volume=D("2"),
            volume_step=D("0.25"),
            tick_size=D("0.01"),
            specification_source=SpecificationSource.TEST_FIXTURE,
        ),
        price_unit="USD_PER_TROY_OUNCE",
        contract_size_unit="TROY_OUNCES_PER_VOLUME_UNIT",
        quote_currency="USD",
        account_currency="USD",
    )
    accounted = realize_usd(
        result.lifecycle,
        contract,
        Commission(currency="USD", fixed_round_trip_usd=D("1.25")),
    )
    assert accounted.raw_price_movement == D("-8")
    assert accounted.gross_usd == D("-40")
    assert accounted.net_usd == D("-41.25")


def test_creation_after_bar_open_and_before_entry_are_rejected():
    state, instruction = setup()
    later = T + timedelta(seconds=1)
    late_instruction = ProtectiveInstruction.model_validate(
        instruction.model_dump()
        | {"created_at": later, "creation_quote": quote(timestamp=later).model_dump()}
    )
    with pytest.raises(ValidationError):
        run_bar(state, late_instruction, bar(bid_low="1994"))
    earlier = T - timedelta(seconds=1)
    early_instruction = ProtectiveInstruction.model_validate(
        instruction.model_dump()
        | {
            "created_at": earlier,
            "creation_quote": quote(timestamp=earlier).model_dump(),
        }
    )
    with pytest.raises(ExecutionError):
        run_bar(state, early_instruction, bar(bid_low="1994"))
    # Direct evidence-to-lifecycle path also enforces entry chronology.
    evidence = ProtectiveBarEvidence(
        instruction=early_instruction,
        bar=bar(bid_low="1994"),
        evaluated_at=END,
        source_market_data_id="synthetic:early",
    )
    with pytest.raises(ValidationError):
        state.close_protective_bar(evidence)


def test_unchecked_invalid_observations_and_wrong_direction_rejected():
    state, instruction = setup()
    with pytest.raises(ValidationError):
        run_bar(state, instruction, bar().model_copy(update={"bid_low": D("-1")}))
    with pytest.raises(ValidationError):
        run_bar(state, instruction, bar(), END.replace(tzinfo=None))
    _, short_instruction = setup(Direction.SHORT)
    with pytest.raises(ExecutionError):
        run_bar(state, short_instruction, bar())
    invalid = instruction.model_copy(update={"stop_price": D("9999")})
    with pytest.raises(ValidationError):
        run_bar(state, invalid, bar())
