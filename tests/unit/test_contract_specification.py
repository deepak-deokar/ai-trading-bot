from datetime import UTC, datetime
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from trading_bot.domain.contracts import (
    ContractSpecification,
    ContractValidationCode,
    ContractValidationError,
    SpecificationSource,
)


def synthetic(**changes):
    # Deliberately nonstandard synthetic values, not a real broker specification.
    return ContractSpecification.model_validate(
        {
            "contract_size": Decimal("37"),
            "minimum_volume": Decimal("0.2"),
            "maximum_volume": Decimal("8"),
            "volume_step": Decimal("0.2"),
            "tick_size": Decimal("0.25"),
            "specification_source": SpecificationSource.TEST_FIXTURE,
        }
        | changes
    )


@pytest.mark.parametrize(
    "field",
    [
        "contract_size",
        "minimum_volume",
        "maximum_volume",
        "volume_step",
        "tick_size",
        "tick_value",
        "minimum_stop_distance",
    ],
)
@pytest.mark.parametrize(
    "value",
    [0.1, 1, "0.1", Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")],
)
def test_decimal_only_positive_fields(field, value):
    with pytest.raises(ValidationError):
        synthetic(**{field: value})


@pytest.mark.parametrize(
    "value,code",
    [("0.1", "BELOW_MINIMUM"), ("8.2", "ABOVE_MAXIMUM"), ("0.3", "VOLUME_STEP")],
)
def test_volume_errors(value, code):
    with pytest.raises(ContractValidationError) as error:
        synthetic().validate_volume(Decimal(value))
    assert error.value.code == code


@pytest.mark.parametrize("value", ["0.2", "0.4", "8"])
def test_valid_volume(value):
    assert synthetic().validate_volume(Decimal(value)) is None


def test_no_maximum_and_no_fixed_lot():
    assert synthetic(maximum_volume=None).validate_volume(Decimal("100")) is None
    spec = synthetic(minimum_volume=Decimal("3"), volume_step=Decimal("1.5"))
    spec.validate_volume(Decimal("4.5"))
    for name in ("contract_size", "minimum_volume", "volume_step", "tick_size"):
        assert ContractSpecification.model_fields[name].is_required()


@pytest.mark.parametrize("price,valid", [("4102.50", True), ("4102.51", False)])
def test_tick_validation(price, valid):
    if valid:
        synthetic().validate_price(Decimal(price))
    else:
        with pytest.raises(ContractValidationError) as error:
            synthetic().validate_price(Decimal(price))
        assert error.value.code == ContractValidationCode.PRICE_TICK


@pytest.mark.parametrize(
    "value", [1.5, "1.5", Decimal("0"), Decimal("-1"), Decimal("NaN")]
)
def test_helpers_reject_invalid_values(value):
    for method in (synthetic().validate_price, synthetic().validate_volume):
        with pytest.raises(ContractValidationError) as error:
            method(value)
        assert error.value.code == ContractValidationCode.INVALID_DECIMAL


@pytest.mark.parametrize("alias", [None, "XAUUSD", "XAUUSDm", "GOLD"])
def test_canonical_and_broker_symbols(alias):
    spec = synthetic(broker_symbol=alias)
    assert spec.canonical_symbol == "XAUUSD"
    assert spec.broker_symbol == alias
    assert spec.specification_source == SpecificationSource.TEST_FIXTURE
    with pytest.raises(ValidationError):
        synthetic(canonical_symbol="GOLD")
    with pytest.raises(ValidationError):
        spec.contract_size = Decimal("100")


@pytest.mark.parametrize(
    "changes",
    [
        {"contract_size": Decimal("38")},
        {"minimum_volume": Decimal("0.4")},
        {"maximum_volume": None},
        {"volume_step": Decimal("0.1")},
        {"tick_size": Decimal("0.5")},
        {"tick_value": Decimal("2")},
        {"price_digits": 3},
        {"minimum_stop_distance": Decimal("2")},
        {"broker_symbol": "GOLD"},
        {"specification_source": "MANUAL_RESEARCH"},
        {"observed_at": datetime(2026, 1, 1, tzinfo=UTC)},
    ],
)
def test_identity_changes(changes):
    assert synthetic(**changes).specification_id != synthetic().specification_id


def test_reproducible_identity_and_exact_arithmetic():
    original = synthetic()
    assert (
        original.specification_id
        == synthetic(contract_size=Decimal("37.000")).specification_id
    )
    assert len(original.specification_id) == 64
    with localcontext() as context:
        context.prec = 2
        assert original.specification_id == synthetic().specification_id
        original.validate_price(Decimal("123456789012345678901234567890.25"))
        with pytest.raises(ContractValidationError):
            original.validate_price(Decimal("123456789012345678901234567890.251"))
    assert original.model_dump(mode="json")["tick_size"] == "0.25"


@pytest.mark.parametrize(
    "changes",
    [
        {"maximum_volume": Decimal("0.1")},
        {"minimum_volume": Decimal("0.3")},
        {"price_digits": -1},
        {"price_digits": True},
        {"broker_symbol": " "},
        {"observed_at": datetime(2026, 1, 1)},
    ],
)
def test_invalid_metadata(changes):
    with pytest.raises(ValidationError):
        synthetic(**changes)


def test_observation_utc():
    spec = synthetic(observed_at=datetime.fromisoformat("2026-01-01T05:30:00+05:30"))
    assert spec.observed_at == datetime(2026, 1, 1, tzinfo=UTC)
