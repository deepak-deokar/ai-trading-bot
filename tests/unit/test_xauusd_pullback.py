from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from trading_bot.data.research_input import ResearchFeatureInput
from trading_bot.features.xauusd import FeatureValue, XAUUSDFeatureRow
from trading_bot.strategies.xauusd_pullback import evaluate_pullback

T = datetime(2024, 2, 1, 8, tzinfo=UTC)
STEP = timedelta(minutes=5)


def row(index, **changes):
    values = dict(
        ema_12="102",
        ema_26="100",
        momentum_3="1",
        momentum_12="2",
        spread_close="0.75",
        relative_spread="0.0003",
    )
    values.update(changes)
    return XAUUSDFeatureRow(
        dataset_key="synthetic-source-day",
        policy_key="synthetic",
        sequence_reset=None,
        input=ResearchFeatureInput(
            opening_timestamp=T + index * STEP,
            previous_observed_timestamp=T + (index - 1) * STEP,
            tick_count=1,
            **{
                f"{side}_{key}": D("100") if side == "bid" else D("100.5")
                for side in ("bid", "ask")
                for key in ("open", "close", "high", "low")
            },
        ),
        values=tuple(
            FeatureValue(
                name=k,
                value=D(v) if v is not None else None,
                unavailable="WARMUP" if v is None else None,
            )
            for k, v in values.items()
        ),
    )


def evaluate(previous=None, **changes):
    current = row(1, **changes)
    return evaluate_pullback(
        current,
        row(0, momentum_3="0") if previous is None else previous,
        as_of=current.available_at,
    )


@pytest.mark.parametrize(
    "changes,action",
    [
        ({}, "BUY"),
        ({"ema_12": "100"}, "NO_TRADE"),
        ({"ema_12": "99"}, "NO_TRADE"),
        ({"momentum_12": "0"}, "NO_TRADE"),
        ({"momentum_12": "-1"}, "NO_TRADE"),
        ({"momentum_3": "0"}, "NO_TRADE"),
        ({"momentum_3": "-1"}, "NO_TRADE"),
        ({"spread_close": "0.75001"}, "NO_TRADE"),
        ({"relative_spread": "0.00030001"}, "NO_TRADE"),
        ({"momentum_12": None}, "NO_TRADE"),
        ({"rsi_14": "99", "ema_difference": "-999"}, "BUY"),
    ],
)
def test_buy_conditions_and_no_rsi(changes, action):
    assert evaluate(**changes).action == action


@pytest.mark.parametrize(
    "previous,short,long,fast,action",
    [
        ("0", "-1", "-2", "98", "SELL"),
        ("1", "-1", "-2", "98", "SELL"),
        ("-1", "-2", "-2", "98", "NO_TRADE"),
        ("0", "0", "-2", "98", "NO_TRADE"),
        ("0", "-1", "0", "98", "NO_TRADE"),
        ("0", "-1", "-2", "102", "NO_TRADE"),
    ],
)
def test_sell_mirror(previous, short, long, fast, action):
    assert (
        evaluate(
            row(0, momentum_3=previous), momentum_3=short, momentum_12=long, ema_12=fast
        ).action
        == action
    )


def test_no_repeated_signal_in_either_direction():
    assert evaluate(row(0, momentum_3="1")).action == "NO_TRADE"
    assert (
        evaluate(
            row(0, momentum_3="-1"), ema_12="98", momentum_12="-2", momentum_3="-2"
        ).action
        == "NO_TRADE"
    )


def test_missing_previous_and_discontinuity():
    current = row(1)
    assert (
        evaluate_pullback(current, None, as_of=current.available_at).reason
        == "MISSING_PREVIOUS_ROW"
    )
    for prior in (
        row(-1),
        row(2),
        row(0).model_copy(update={"dataset_key": "other-day"}),
        row(0).model_copy(update={"policy_key": "other"}),
    ):
        assert (
            evaluate_pullback(current, prior, as_of=current.available_at).reason
            == "DISCONTINUITY"
        )
    for reset in ("DATASET_BOUNDARY", "DISCONTINUITY"):
        changed = current.model_copy(update={"sequence_reset": reset})
        assert (
            evaluate_pullback(changed, row(0), as_of=changed.available_at).reason
            == "DISCONTINUITY"
        )
    assert evaluate(row(0, momentum_3=None)).reason == "FEATURES_UNAVAILABLE"


def test_completed_rows_and_future_mutation():
    sequence = [row(0, momentum_3="-1"), row(1), row(2)]
    original = evaluate_pullback(
        sequence[1], sequence[0], as_of=sequence[1].available_at
    )
    sequence[2] = row(2, momentum_3="-999", momentum_12="-999")
    assert original == evaluate_pullback(
        sequence[1], sequence[0], as_of=sequence[1].available_at
    )
    with pytest.raises(ValueError):
        evaluate_pullback(
            sequence[1],
            sequence[0],
            as_of=sequence[1].available_at - timedelta(seconds=1),
        )
    with pytest.raises(ValueError):
        evaluate_pullback(sequence[1], sequence[0], as_of=T.replace(tzinfo=None))
    assert original.previous_row_hash and original.current_row_hash
