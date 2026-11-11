from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from uuid import UUID

import pytest
from pydantic import ValidationError

from trading_bot.domain.contracts import ContractSpecification, SpecificationSource
from trading_bot.domain.positions import PositionDirection
from trading_bot.domain.quotes import MarketQuote, QuoteSource
from trading_bot.execution.accounting import Commission, LinearUSDContract, realize_usd
from trading_bot.execution.xauusd import XAUUSDExecution

T = datetime(2024, 2, 20, 10, tzinfo=UTC)


def contract(**changes):
    values = dict(
        contract_size=Decimal("10"),
        minimum_volume=Decimal("0.25"),
        maximum_volume=Decimal("2"),
        volume_step=Decimal("0.25"),
        tick_size=Decimal("0.01"),
        specification_source=SpecificationSource.TEST_FIXTURE,
    )
    values.update(changes)
    return LinearUSDContract(
        specification=ContractSpecification(**values),
        price_unit="USD_PER_TROY_OUNCE",
        contract_size_unit="TROY_OUNCES_PER_VOLUME_UNIT",
        quote_currency="USD",
        account_currency="USD",
    )


def lifecycle(direction="LONG", bid="2002", ask="2002.50", volume=Decimal("0.5")):
    def quote(b, a, t):
        return MarketQuote(
            canonical_symbol="XAUUSD",
            bid=Decimal(b),
            ask=Decimal(a),
            timestamp=t,
            source=QuoteSource.TEST_FIXTURE,
        )

    start = XAUUSDExecution(simulation_id=UUID(int=10)).open(
        PositionDirection(direction),
        volume,
        quote("2000", "2000.50", T),
        timestamp=T,
        source_market_data_id="synthetic-entry",
    )
    return start.close(
        quote(bid, ask, T + timedelta(seconds=1)),
        timestamp=T + timedelta(seconds=1),
        source_market_data_id="synthetic-exit",
    )


def zero():
    return Commission(currency="USD", fixed_round_trip_usd=Decimal("0"))


@pytest.mark.parametrize(
    "direction,bid,ask,gross",
    [
        ("LONG", "2002", "2002.50", "7.5"),
        ("LONG", "1998", "1998.50", "-12.5"),
        ("SHORT", "1998", "1998.50", "7.5"),
        ("SHORT", "2002", "2002.50", "-12.5"),
        ("LONG", "2000", "2000.50", "-2.5"),
        ("SHORT", "2000", "2000.50", "-2.5"),
    ],
)
def test_hand_calculated_fills_no_double_spread(direction, bid, ask, gross):
    state = lifecycle(direction, bid, ask)
    result = realize_usd(state, contract(), zero())
    assert result.gross_usd == Decimal(gross) == result.net_usd
    assert result.raw_price_movement == state.price_movement
    assert result.lifecycle.fills == state.fills
    assert result.contract_specification_id == contract().specification.specification_id
    assert result == realize_usd(state, contract(), zero())


def test_volume_scaling_and_commission_once():
    base = realize_usd(lifecycle(), contract(), zero())
    doubled = realize_usd(lifecycle(volume=Decimal("1")), contract(), zero())
    assert doubled.gross_usd == 2 * base.gross_usd
    fee = Commission(currency="USD", fixed_round_trip_usd=Decimal("1.25"))
    with localcontext() as c:
        c.prec = 2
        result = realize_usd(lifecycle(), contract(), fee)
    assert result.gross_usd == Decimal("7.50")
    assert result.commission_usd == Decimal("1.25")
    assert result.net_usd == Decimal("6.25")
    assert result.slippage_usd == Decimal("0")


@pytest.mark.parametrize("volume", ["0.1", "0.3", "2.25"])
def test_volume_rejected_without_rounding(volume):
    with pytest.raises(ValueError):
        realize_usd(lifecycle(volume=Decimal(volume)), contract(), zero())


@pytest.mark.parametrize("field", ["quote_currency", "account_currency"])
def test_currency_rejected(field):
    values = contract().model_dump() | {field: "EUR"}
    with pytest.raises(ValidationError):
        LinearUSDContract.model_validate(values)


def test_decimal_and_closed_requirement():
    with pytest.raises(ValidationError):
        contract(contract_size=10.0)
    with pytest.raises(ValidationError):
        Commission(currency="USD", fixed_round_trip_usd=1.0)
    with pytest.raises(ValidationError):
        Commission(currency="USD", fixed_round_trip_usd=Decimal("-1"))
    with pytest.raises(ValueError):
        realize_usd(XAUUSDExecution(simulation_id=UUID(int=1)), contract(), zero())
    closed = lifecycle()
    open_state = XAUUSDExecution(
        simulation_id=closed.simulation_id,
        position=closed.position.model_copy(
            update={"closed_at": None, "exit_price": None}
        ),
        fills=closed.fills[:1],
    )
    with pytest.raises(ValueError):
        realize_usd(open_state, contract(), zero())
    with pytest.raises(ValueError):
        contract(tick_value=Decimal("1"))
    result = realize_usd(lifecycle(bid="2002.001", ask="2002.501"), contract(), zero())
    assert result.gross_usd == Decimal("7.505")


@pytest.mark.parametrize(
    "direction,bid,ask,gross",
    [
        ("LONG", "2035.956", "2036.156", "177.280"),
        ("SHORT", "2035.756", "2035.956", "-179.780"),
    ],
)
def test_off_grid_market_exit_exact_accounting(direction, bid, ask, gross):
    state = lifecycle(direction, bid, ask)
    fee = Commission(currency="USD", fixed_round_trip_usd=Decimal("1.25"))
    result = realize_usd(state, contract(), fee)
    assert state.position.exit_price == Decimal("2035.956")
    assert result.gross_usd == Decimal(gross)
    assert result.net_usd == Decimal(gross) - Decimal("1.25")
    assert result.commission_usd == Decimal("1.25")


@pytest.mark.parametrize(
    "price",
    [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), 2035.956],
)
def test_invalid_observed_prices_remain_rejected(price):
    with pytest.raises((ValueError, TypeError)):
        MarketQuote(
            canonical_symbol="XAUUSD", timestamp=T, bid=price, ask=Decimal("3000")
        )
