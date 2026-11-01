from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trading_bot.data.research_input import ResearchFeatureInput
from trading_bot.features.xauusd import FeatureValue, XAUUSDFeatureRow
from trading_bot.strategies.xauusd import evaluate_xauusd


def feature_row(index=0, **changes):
    opening = datetime(2024, 2, 20, 8, tzinfo=UTC) + timedelta(minutes=index * 5)
    item = ResearchFeatureInput(
        opening_timestamp=opening,
        tick_count=10,
        **{
            f"{s}_{k}": Decimal("2000") + (Decimal("0.3") if s == "ask" else 0)
            for s in ("bid", "ask")
            for k in ("open", "high", "low", "close")
        },
    )
    values = {
        "ema_12": "2002",
        "ema_26": "2000",
        "ema_difference": "2",
        "momentum_3": "1",
        "rsi_14": "60",
        "spread_close": "0.3",
        "relative_spread": "0.00015",
    }
    values.update(changes)
    return XAUUSDFeatureRow(
        dataset_key="synthetic",
        policy_key="synthetic",
        input=item,
        sequence_reset=None,
        values=tuple(
            FeatureValue(
                name=k,
                value=Decimal(v) if v is not None else None,
                unavailable="GAP_WARMUP" if v is None else None,
            )
            for k, v in values.items()
        ),
    )


def evaluate(row):
    return evaluate_xauusd(row, as_of=row.available_at)


@pytest.mark.parametrize(
    "changes,action,reason",
    [
        ({}, "BUY", "BUY_SETUP"),
        (
            {
                "ema_12": "1998",
                "ema_difference": "-2",
                "momentum_3": "-1",
                "rsi_14": "40",
            },
            "SELL",
            "SELL_SETUP",
        ),
        ({"momentum_3": "-1"}, "NO_TRADE", "SIGNALS_CONFLICT"),
        ({"ema_26": None}, "NO_TRADE", "WARMUP_INCOMPLETE"),
        ({"spread_close": "0.75001"}, "NO_TRADE", "SPREAD_TOO_WIDE"),
        ({"relative_spread": "0.00030001"}, "NO_TRADE", "SPREAD_TOO_WIDE"),
        ({"rsi_14": "70.01"}, "NO_TRADE", "RSI_TOO_EXTENDED"),
        (
            {
                "ema_12": "1998",
                "ema_difference": "-2",
                "momentum_3": "-1",
                "rsi_14": "29.99",
            },
            "NO_TRADE",
            "RSI_TOO_EXTENDED",
        ),
        ({"rsi_14": "54.99"}, "NO_TRADE", "RSI_NO_CONFIRMATION"),
        ({"ema_12": "2000", "ema_difference": "0"}, "NO_TRADE", "NO_SETUP"),
        (
            {"rsi_14": "55", "spread_close": "0.75", "relative_spread": "0.0003"},
            "BUY",
            "BUY_SETUP",
        ),
        ({"rsi_14": "70"}, "BUY", "BUY_SETUP"),
        (
            {
                "ema_12": "1998",
                "ema_difference": "-2",
                "momentum_3": "-1",
                "rsi_14": "30",
            },
            "SELL",
            "SELL_SETUP",
        ),
        (
            {
                "ema_12": "1998",
                "ema_difference": "-2",
                "momentum_3": "-1",
                "rsi_14": "45",
            },
            "SELL",
            "SELL_SETUP",
        ),
    ],
)
def test_fixed_rules(changes, action, reason):
    result = evaluate(feature_row(**changes))
    assert result.action == action
    assert reason in result.reasons
    assert not hasattr(result, "quantity") and not hasattr(result, "order_id")


def test_completion_identity_immutability():
    row = feature_row()
    result = evaluate(row)
    assert result.available_at == row.opening_timestamp + timedelta(minutes=5)
    assert result.source_dataset_key == row.dataset_key
    assert result.source_feature_version == row.feature_set_version
    assert len(result.source_feature_row_hash) == 64
    assert result.feature_snapshot == row.values
    with pytest.raises(ValueError):
        evaluate_xauusd(row, as_of=row.available_at - timedelta(microseconds=1))
    with pytest.raises(ValueError):
        evaluate_xauusd(row, as_of=row.available_at.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        result.side = None


def test_future_mutation_and_repeat():
    original = [feature_row(i) for i in range(60)]
    before = tuple(map(evaluate, original))
    changed = original[:31] + [
        feature_row(
            i,
            ema_12="9000",
            ema_difference="7000",
            momentum_3="5000",
            rsi_14="99",
            spread_close="50",
        )
        for i in range(31, 60)
    ]
    after = tuple(map(evaluate, changed))
    assert before[:31] == after[:31]
    assert before[31:] != after[31:]
    assert before == tuple(map(evaluate, original))
