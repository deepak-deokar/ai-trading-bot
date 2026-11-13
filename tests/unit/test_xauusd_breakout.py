"""Synthetic causal breakout checks; no downloaded data."""

import runpy
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest

from trading_bot.data.research_input import ResearchFeatureInput
from trading_bot.strategies.xauusd_breakout import evaluate_breakout

ROOT = Path(__file__).resolve().parents[2]
BASE = runpy.run_path(str(ROOT / "tests/unit/test_xauusd_pullback.py"))["row"]


def row(i, close="100", high="101", low="99", **features):
    r = BASE(i, **features)
    prices = {"open": D(close), "close": D(close), "high": D(high), "low": D(low)}
    inp = ResearchFeatureInput.model_validate(
        r.input.model_dump()
        | {
            f"{side}_{k}": v + (D("0.2") if side == "ask" else 0)
            for side in ("bid", "ask")
            for k, v in prices.items()
        }
    )
    return r.model_copy(update={"input": inp})


def decide(current, prior=None):
    return evaluate_breakout(
        current,
        prior if prior is not None else [row(i) for i in range(13)],
        as_of=current.available_at,
    )


@pytest.mark.parametrize(
    "close,high,low,action",
    [
        ("102", "150", "99", "BUY"),  # signal high excluded from reference
        ("98", "101", "1", "SELL"),  # signal low excluded from reference
        ("101", "101", "99", "NO_TRADE"),
        ("99", "101", "99", "NO_TRADE"),
    ],
)
def test_strict_side_specific_structure(close, high, low, action):
    d = decide(row(13, close, high, low))
    assert d.action == action
    assert d.bid_reference == D("101") and d.ask_reference == D("99.2")


@pytest.mark.parametrize("direction", [1, -1])
def test_no_repeat_on_consecutive_breakouts(direction):
    prior = [row(i) for i in range(13)]
    first = (
        row(13, "102", "102", "99") if direction == 1 else row(13, "98", "101", "98")
    )
    second = (
        row(14, "103", "103", "99") if direction == 1 else row(14, "97", "101", "97")
    )
    assert decide(first, prior).action == ("BUY" if direction == 1 else "SELL")
    assert decide(second, prior + [first]).action == "NO_TRADE"


def test_no_trend_filters_and_spread_limits():
    assert (
        decide(
            row(
                13,
                "102",
                "102",
                "99",
                ema_12="1",
                ema_26="999",
                rsi_14="99",
                momentum_3="-99",
                momentum_12="-99",
            )
        ).action
        == "BUY"
    )
    for change in (
        {"spread_close": "0.75001"},
        {"relative_spread": "0.00030001"},
        {"spread_close": None},
    ):
        assert decide(row(13, "102", "102", "99", **change)).action == "NO_TRADE"


def test_continuity_history_and_completion():
    current = row(13, "102", "102", "99")
    prior = [row(i) for i in range(13)]
    assert decide(current, prior[:-1]).reason == "INSUFFICIENT_FRESHNESS_HISTORY"
    for field, value in [
        ("dataset_key", "other-day"),
        ("policy_key", "other-policy"),
        ("sequence_reset", "DISCONTINUITY"),
    ]:
        changed = list(prior)
        changed[4] = changed[4].model_copy(update={field: value})
        assert decide(current, changed).reason == "DISCONTINUITY"
    assert decide(current, prior[:4] + prior[5:] + [row(14)]).reason == "DISCONTINUITY"
    assert (
        decide(
            current.model_copy(update={"sequence_reset": "DATASET_BOUNDARY"}), prior
        ).reason
        == "DISCONTINUITY"
    )
    with pytest.raises(ValueError):
        evaluate_breakout(
            current, prior, as_of=current.available_at - timedelta(seconds=1)
        )
    with pytest.raises(ValueError):
        evaluate_breakout(
            current, prior, as_of=current.available_at.replace(tzinfo=None)
        )


def test_future_mutation_preserves_earlier_signal():
    sequence = [row(i) for i in range(13)] + [row(13, "102", "102", "99"), row(14)]
    before = decide(sequence[13], sequence[:13])
    sequence[14] = row(14, "500", "600", "1")
    assert before == decide(sequence[13], sequence[:13])
