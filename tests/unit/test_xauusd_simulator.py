"""Offline synthetic orchestration; independent checks of reused mechanics."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from uuid import UUID

import pytest
from pydantic import ValidationError

from trading_bot.domain.contracts import ContractSpecification, SpecificationSource
from trading_bot.domain.positions import PositionDirection as Direction
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.execution.accounting import Commission, LinearUSDContract, realize_usd
from trading_bot.execution.simulator import (
    SimulationBar,
    SimulationDataError,
    TradePlan,
    simulate_trade,
)
from trading_bot.execution.sizing import size_position

D = Decimal
T = datetime(2024, 2, 20, 10, tzinfo=UTC)
STEP = timedelta(minutes=5)


def plan(direction=Direction.LONG, **changes):
    values = dict(
        plan_id=UUID(int=10),
        direction=direction,
        created_at=T,
        entry_timestamp=T,
        stop_price=D("1995" if direction == Direction.LONG else "2005"),
        target_price=D("2005" if direction == Direction.LONG else "1995"),
        account_equity=D("500"),
        account_currency="USD",
        risk_fraction=D("0.05"),
        contract=LinearUSDContract(
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
        ),
        commission=Commission(currency="USD", fixed_round_trip_usd=D("1.25")),
        source_identity="synthetic:explicit-plan",
    )
    values.update(changes)
    return TradePlan(**values)


def observation(index=0, **changes):
    values = dict(
        opening_timestamp=T + index * STEP,
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
    return SimulationBar(
        bar=QuoteBar(**values), source_market_data_id=f"synthetic:bar:{index}"
    )


def run(p, bars, as_of=T + 10 * STEP):
    return simulate_trade(p, bars, as_of=as_of)


@pytest.mark.parametrize(
    "direction,changes,status,entry,exit_price,net",
    [
        (
            Direction.LONG,
            {"bid_high": "2005", "ask_high": "2006"},
            "CLOSED_TARGET",
            "2001",
            "2005",
            "8.75",
        ),
        (
            Direction.LONG,
            {"bid_low": "1995", "ask_low": "1996"},
            "CLOSED_STOP",
            "2001",
            "1995",
            "-16.25",
        ),
        (
            Direction.SHORT,
            {"bid_low": "1994", "ask_low": "1995"},
            "CLOSED_TARGET",
            "2000",
            "1995",
            "11.25",
        ),
        (
            Direction.SHORT,
            {"ask_high": "2005"},
            "CLOSED_STOP",
            "2000",
            "2005",
            "-13.75",
        ),
        (
            Direction.LONG,
            {
                "bid_low": "1994",
                "ask_low": "1995",
                "bid_high": "2006",
                "ask_high": "2007",
            },
            "CLOSED_STOP_AMBIGUOUS",
            "2001",
            "1995",
            "-16.25",
        ),
    ],
)
def test_closed_lifecycle_and_exact_component_reuse(
    direction, changes, status, entry, exit_price, net
):
    p = plan(direction)
    bars = [observation(), observation(1, **changes)]
    result = run(p, bars)
    assert result.status == status
    assert result.entry_fill.executed_price == D(entry)
    assert result.exit_fill.executed_price == D(exit_price)
    assert result.volume == D("0.25")
    assert result.net_pnl == D(net)
    assert result.costs == D("1.25")
    assert result.accounting == realize_usd(result.lifecycle, p.contract, p.commission)
    assert result.sizing == size_position(result.sizing.request)
    assert len(result.lifecycle.fills) == 2
    assert result.protection.position_id == result.position_id
    assert result.bars_processed == 2
    assert not result.risk_budget_breached
    assert result == run(p, bars)
    kinds = [event.kind for event in result.events]
    assert kinds[:5] == [
        "PLAN_ACCEPTED",
        "VOLUME_SIZED",
        "ENTRY_FILLED",
        "PROTECTION_ATTACHED",
        "NO_EXIT",
    ]
    assert kinds[-2:] == ["POSITION_CLOSED", "ACCOUNTING_COMPLETED"]
    assert [e.sequence for e in result.events] == list(range(len(result.events)))
    assert len({e.event_id for e in result.events}) == len(result.events)
    assert [e.timestamp for e in result.events] == sorted(
        e.timestamp for e in result.events
    )


@pytest.mark.parametrize(
    "direction,changes,exit_price,net",
    [
        (
            Direction.LONG,
            {
                "bid_open": "1990",
                "bid_low": "1990",
                "ask_open": "1991",
                "ask_low": "1991",
            },
            "1990",
            "-28.75",
        ),
        (
            Direction.SHORT,
            {
                "bid_open": "2010",
                "bid_high": "2010",
                "ask_open": "2011",
                "ask_high": "2011",
            },
            "2011",
            "-28.75",
        ),
    ],
)
def test_gap_breach_is_reported_not_repaired(direction, changes, exit_price, net):
    p = plan(direction)
    with localcontext() as context:
        context.prec = 2
        result = run(p, [observation(), observation(1, **changes)])
    assert result.exit_fill.executed_price == D(exit_price)
    assert result.net_pnl == D(net)
    assert result.projected_stop_risk <= result.risk_budget == D("25")
    assert result.risk_budget_breached
    assert "RISK_BUDGET_EXCEEDED_BY_GAP" in result.audit_reasons
    assert result.events[-1].kind == "RISK_BUDGET_BREACH"


def test_no_valid_volume_prevents_entry_and_cost_charge():
    result = run(plan(risk_fraction=D("0.01")), [observation()])
    assert result.status == "NO_TRADE_RISK"
    assert result.risk_budget == D("5")
    assert result.lifecycle.fills == ()
    assert result.volume is result.protection is result.accounting is None
    assert result.costs is None
    assert [e.kind for e in result.events] == ["PLAN_ACCEPTED", "PLAN_REJECTED"]


def test_open_and_pending_at_end_do_not_force_exit():
    opened = run(plan(), [observation()])
    assert opened.status == "OPEN_AT_END"
    assert len(opened.lifecycle.fills) == 1
    assert opened.exit_fill is opened.accounting is opened.net_pnl is None
    for bars in ([], [observation(-1)]):
        pending = run(plan(), bars)
        assert pending.status == "PENDING_AT_END"
        assert pending.lifecycle.status == "FLAT"
        assert pending.sizing is None
    incomplete = run(plan(), [observation()], as_of=T + timedelta(minutes=4))
    assert incomplete.status == "PENDING_AT_END"
    assert incomplete.bars_processed == 0


def test_next_opening_no_retroactive_entry_and_actual_price_sizing():
    p = plan(
        created_at=T + timedelta(minutes=2), entry_timestamp=T + timedelta(minutes=2)
    )
    # An extreme pre-entry bar cannot trigger an exit or supply an entry price.
    before = observation(
        bid_low="1000", bid_high="3000", ask_low="1001", ask_high="3001"
    )
    next_bar = observation(
        1, bid_open="2002", bid_high="2003", ask_open="2003", ask_high="2004"
    )
    result = run(p, [before, next_bar])
    assert result.entry_fill.timestamp == T + STEP
    assert result.entry_fill.executed_price == D("2003")
    assert result.sizing.request.stop_distance == D("8")
    assert result.status == "OPEN_AT_END"
    changed_before = run(p, [observation(), next_bar])
    assert changed_before == result
    changed_open = run(p, [before, observation(1)])
    assert changed_open.entry_fill.executed_price == D("2001")
    assert changed_open.sizing.request.stop_distance == D("6")
    # A plan created exactly at prior bar completion can use the next opening.
    at_boundary = run(
        plan(created_at=T + STEP, entry_timestamp=T + STEP), [before, next_bar]
    )
    assert at_boundary.entry_fill.timestamp == T + STEP


def test_future_suffix_never_consumed_and_entry_uses_no_extrema():
    p = plan()
    close_bar = observation(1, bid_high="2006", ask_high="2007")
    baseline = run(p, [observation(), close_bar])
    future = observation(2, bid_high="9999", ask_high="10000")
    assert run(p, [observation(), close_bar, future]) == baseline

    def guarded():
        yield observation()
        yield close_bar
        raise AssertionError("must not request observations after closure")

    assert run(p, guarded()) == baseline
    same_bar_exit = run(p, [observation(bid_high="2006", ask_high="2007")])
    assert same_bar_exit.entry_fill == baseline.entry_fill
    assert same_bar_exit.sizing == baseline.sizing
    assert same_bar_exit.entry_fill.timestamp < same_bar_exit.exit_fill.timestamp


@pytest.mark.parametrize(
    "changes",
    [
        {"stop_price": D("2001")},
        {"target_price": D("1999")},
        {"stop_price": D("1995.001")},
    ],
)
def test_market_invalid_plan_rejected_before_open(changes):
    result = run(plan(**changes), [observation()])
    assert result.status == "REJECTED_INVALID_PLAN"
    assert result.lifecycle.fills == ()
    assert result.events[-1].kind == "PLAN_REJECTED"


@pytest.mark.parametrize(
    "changes",
    [
        {"stop_price": 1995.0},
        {"account_equity": 500.0},
        {"risk_fraction": 0.05},
        {"created_at": T.replace(tzinfo=None)},
        {"entry_timestamp": T.replace(tzinfo=None)},
        {"entry_timestamp": T - STEP},
        {"risk_fraction": D("0")},
        {"risk_fraction": D("1.1")},
        {"risk_amount": D("5")},
        {"risk_fraction": None},
        {"account_currency": "EUR"},
        {"canonical_symbol": "RELIANCE"},
        {"source_identity": " "},
    ],
)
def test_plan_validation(changes):
    with pytest.raises(ValidationError):
        plan(**changes)


def test_utc_freezing_and_invalid_observation_order():
    offset = T.astimezone(timezone(timedelta(hours=5)))
    p = plan(
        created_at=offset,
        entry_timestamp=offset,
        risk_fraction=None,
        risk_amount=D("25"),
    )
    assert p.created_at.tzinfo == UTC
    with pytest.raises(ValidationError):
        p.stop_price = D("1990")
    for bars in ([observation(), observation()], [observation(1), observation()]):
        with pytest.raises(SimulationDataError):
            run(p, bars)
    duplicate_id = observation(1).model_copy(
        update={"source_market_data_id": observation().source_market_data_id}
    )
    with pytest.raises(SimulationDataError):
        run(p, [observation(), duplicate_id])
    with pytest.raises(ValueError):
        run(p, [], as_of=T.replace(tzinfo=None))
    with pytest.raises(ValueError):
        run(p, [], as_of=T - STEP)
    with pytest.raises(ValidationError):
        run(p.model_copy(update={"stop_price": D("-1")}), [])


def test_missing_intervals_are_not_filled_and_stop_only_plan():
    p = plan(target_price=None, risk_fraction=None, risk_amount=D("25"))
    result = run(p, [observation(), observation(4, bid_low="1995")])
    assert result.status == "CLOSED_STOP"
    assert result.bars_processed == len(result.evaluations) == 2
    assert result.exit_fill.timestamp == T + 5 * STEP
    assert result.protection.target_price is None
    assert result.risk_budget == D("25")


def test_risk_rejection_is_terminal_without_consuming_future():
    def guarded():
        yield observation()
        raise AssertionError("risk-rejected plan must not consume another bar")

    result = run(plan(risk_fraction=D("0.01")), guarded())
    assert result.status == "NO_TRADE_RISK"
    assert result.position_id is result.entry_observation is None
