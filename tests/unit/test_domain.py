from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trading_bot.domain.models import Bar, OrderRequest, Prediction

BAR = dict(
    symbol="SPY",
    timestamp="2026-01-02T10:05:00-05:00",
    open="100.10",
    high="101",
    low="99",
    close="100.20",
    volume=1000,
)


def test_normalizes_utc_and_preserves_decimal():
    bar = Bar(**BAR)
    assert bar.timestamp == datetime(2026, 1, 2, 15, 5, tzinfo=UTC)
    assert bar.close - bar.open == Decimal("0.10")
    with pytest.raises(ValidationError):
        bar.close = Decimal("101")


@pytest.mark.parametrize(
    "change",
    [
        {"timestamp": "2026-01-02T10:05:00"},
        {"high": "99"},
        {"low": "102"},
        {"close": "NaN"},
        {"open": "Infinity"},
        {"volume": -1},
        {"volume": 1.5},
        {"interval_seconds": 0},
        {"symbol": "spy"},
    ],
)
def test_rejects_invalid_bar(change):
    with pytest.raises(ValidationError):
        Bar(**(BAR | change))


def test_order_identity_and_whole_share_constraint():
    values = dict(
        symbol="SPY",
        timestamp=BAR["timestamp"],
        side="buy",
        quantity=1,
        strategy_id="baseline-v1",
        reason="test",
    )
    assert OrderRequest(**values).order_id != OrderRequest(**values).order_id
    with pytest.raises(ValidationError):
        OrderRequest(**(values | {"quantity": 0}))


def test_prediction_bounds():
    with pytest.raises(ValidationError):
        Prediction(
            symbol="SPY",
            timestamp=BAR["timestamp"],
            model_version="v1",
            probability_up=1.1,
            expected_return=0.01,
            confidence=0.8,
        )
