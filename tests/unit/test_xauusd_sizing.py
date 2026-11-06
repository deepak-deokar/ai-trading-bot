"""Offline synthetic contracts only; no broker specification claims."""

from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product

import pytest
from pydantic import ValidationError

from trading_bot.domain.contracts import ContractSpecification, SpecificationSource
from trading_bot.execution.accounting import Commission, LinearUSDContract
from trading_bot.execution.sizing import SizingRequest, SizingStatus, size_position

D = Decimal


def request(**changes: object) -> SizingRequest:
    values: dict[str, object] = dict(
        account_equity=D("500"),
        account_currency="USD",
        risk_fraction=D("0.01"),
        stop_distance=D("1"),
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
    )
    values.update(changes)
    return SizingRequest.model_validate(values)


@pytest.mark.parametrize(
    "stop,volume,gross,total,next_risk",
    [
        ("0.1", "2", "2", "3.25", None),
        ("0.5", "0.75", "3.75", "5", "6.25"),
        ("1", "0.25", "2.5", "3.75", "6.25"),
        ("2", None, None, None, None),
    ],
)
def test_reference_account(stop, volume, gross, total, next_risk):
    result = size_position(request(stop_distance=D(stop)))
    assert result.risk_budget_usd == D("5")
    for actual, expected in [
        (result.selected_volume, volume),
        (result.projected_gross_stop_loss, gross),
        (result.projected_net_stop_loss, total),
        (result.next_step_projected_loss, next_risk),
    ]:
        assert actual == (D(expected) if expected is not None else None)
    assert result.projected_explicit_costs == D("1.25")
    assert result.status == (
        SizingStatus.SIZED if volume else SizingStatus.NO_VALID_VOLUME
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"account_equity": D("0")},
        {"account_equity": D("-1")},
        {"stop_distance": D("0")},
        {"stop_distance": D("-1")},
        {"risk_fraction": D("0")},
        {"risk_fraction": D("-0.1")},
        {"risk_fraction": D("1.1")},
        {"risk_fraction": 0.01},
        {"stop_distance": 1.0},
        {"account_equity": 500.0},
        {"account_currency": "EUR"},
        {"risk_fraction": None},
        {"risk_amount": D("5")},
        {"risk_fraction": None, "risk_amount": D("501")},
        {"risk_fraction": None, "risk_amount": D("NaN")},
    ],
)
def test_invalid_inputs(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_unsupported_contract_and_unchecked_copy():
    original = request()
    data = original.model_dump()
    data["contract"]["specification"]["tick_value"] = D("1")
    with pytest.raises(ValidationError):
        SizingRequest.model_validate(data)
    with pytest.raises(ValidationError):
        size_position(original.model_copy(update={"stop_distance": D("-1")}))


def test_costs_exhaust_budget_and_explicit_amount():
    for fee in ("5", "6"):
        result = size_position(
            request(commission=Commission(currency="USD", fixed_round_trip_usd=D(fee)))
        )
        assert result.status == SizingStatus.NO_VALID_VOLUME
        assert result.reason == "COSTS_CONSUME_BUDGET"
    assert size_position(
        request(risk_fraction=None, risk_amount=D("5"))
    ).selected_volume == D("0.25")


def test_exact_arithmetic_invariants_and_monotonicity():
    # 324 combinations; exact independent Fraction oracle, no network/dependency.
    for equity, fraction, size, step in product(
        ("50", "500", "10000"),
        ("0.01", "0.03"),
        ("1", "10", "33"),
        ("0.25", "0.3", "2"),
    ):
        previous = None
        for stop in ("0.1", "0.7", "1", "3", "10", "100"):
            data = request().model_dump()
            data.update(
                account_equity=D(equity),
                risk_fraction=D(fraction),
                stop_distance=D(stop),
            )
            data["contract"]["specification"].update(
                contract_size=D(size),
                minimum_volume=D(step),
                volume_step=D(step),
                maximum_volume=None,
            )
            req = SizingRequest.model_validate(data)
            expected_budget = Fraction(D(equity)) * Fraction(D(fraction))
            with localcontext() as context:
                context.prec = 2
                result = size_position(req)
            assert result == size_position(req)
            assert Fraction(result.risk_budget_usd) == expected_budget
            volume = result.selected_volume or D("0")
            if previous is not None:
                assert volume <= previous
            previous = volume
            if result.status == SizingStatus.SIZED:
                req.contract.specification.validate_volume(volume)
                loss = Fraction(D(stop)) * Fraction(D(size)) * Fraction(
                    volume
                ) + Fraction(D("1.25"))
                assert Fraction(result.projected_net_stop_loss) == loss
                assert loss <= expected_budget
                assert Fraction(result.next_step_projected_loss) > expected_budget
            else:
                assert (
                    Fraction(D(stop)) * Fraction(D(size)) * Fraction(D(step))
                    + Fraction(D("1.25"))
                    > expected_budget
                )


def test_non_grid_maximum_and_frozen_models():
    data = request(stop_distance=D("0.01")).model_dump()
    data["contract"]["specification"]["maximum_volume"] = D("1.9")
    req = SizingRequest.model_validate(data)
    result = size_position(req)
    assert result.selected_volume == D("1.75")
    assert result.next_valid_volume is None
    assert result.reason == "CONTRACT_MAXIMUM"
    with pytest.raises(ValidationError):
        result.selected_volume = D("2")
