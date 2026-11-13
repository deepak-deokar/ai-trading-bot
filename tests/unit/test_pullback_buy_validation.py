"""BUY-only projection and predeclared interpretation; synthetic inputs only."""

import ast
import runpy
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def api(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return runpy.run_path(str(ROOT / "scripts/validate_xauusd_pullback_buy.py"))


@pytest.fixture
def row():
    return runpy.run_path(str(ROOT / "tests/unit/test_xauusd_pullback.py"))["row"]


def test_predicate_is_exact_frozen_buy_expression(api):
    old = ast.parse(
        (ROOT / "src/trading_bot/strategies/xauusd_pullback.py").read_text()
    )
    original = next(
        n.test
        for n in ast.walk(old)
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.BoolOp)
        and ast.unparse(n.test).startswith("fast > slow")
    )
    new = ast.parse((ROOT / "scripts/validate_xauusd_pullback_buy.py").read_text())
    function = next(
        n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == "buy_only"
    )
    assert ast.dump(function.body[-1].value) == ast.dump(original)
    assert "evaluate_pullback" not in ast.unparse(new)
    assert "Side.SELL" not in ast.unparse(new)


@pytest.mark.parametrize(
    "change,expected",
    [
        ({}, True),
        ({"ema_12": "100"}, False),
        ({"momentum_12": "0"}, False),
        ({"momentum_3": "0"}, False),
        ({"spread_close": "0.750001"}, False),
        ({"relative_spread": "0.00030001"}, False),
        ({"rsi_14": "99", "ema_difference": "-999"}, True),
    ],
)
def test_buy_rules_only(api, row, change, expected):
    current = row(1, **change)
    assert (
        api["buy_only"](current, row(0, momentum_3="0"), as_of=current.available_at)
        is expected
    )


def test_continuity_completion_and_future_mutation(api, row):
    evaluate = api["buy_only"]
    current = row(1)
    previous = row(0, momentum_3="-1")
    assert evaluate(current, previous, as_of=current.available_at)
    assert not evaluate(current, None, as_of=current.available_at)
    assert not evaluate(current, row(0, momentum_3="1"), as_of=current.available_at)
    for p in (
        row(-1),
        row(2),
        previous.model_copy(update={"dataset_key": "other-day"}),
    ):
        assert not evaluate(current, p, as_of=current.available_at)
    for reason in ("DATASET_BOUNDARY", "DISCONTINUITY"):
        assert not evaluate(
            current.model_copy(update={"sequence_reset": reason}),
            previous,
            as_of=current.available_at,
        )
    with pytest.raises(ValueError):
        evaluate(
            current, previous, as_of=current.available_at - timedelta(microseconds=1)
        )
    with pytest.raises(ValueError):
        evaluate(current, previous, as_of=current.available_at.replace(tzinfo=None))
    sequence = [previous, current, row(2)]
    before = [
        evaluate(r, sequence[i - 1] if i else None, as_of=r.available_at)
        for i, r in enumerate(sequence)
    ]
    sequence[2] = row(2, momentum_3="-999", ema_12="1", momentum_12="-999")
    after = [
        evaluate(r, sequence[i - 1] if i else None, as_of=r.available_at)
        for i, r in enumerate(sequence)
    ]
    assert before[:2] == after[:2]


@pytest.mark.parametrize(
    "actual,random,percentile,label",
    [
        ("0.1", "0", "95", "STRONG VALIDATION SUPPORT"),
        ("0.1", "0", "94.9", "PARTIAL SUPPORT"),
        ("-0.1", "-0.2", "97", "PARTIAL SUPPORT"),
        ("-0.3", "-0.2", "20", "NO VALIDATION SUPPORT"),
    ],
)
def test_predeclared_primary_interpretation(api, actual, random, percentile, label):
    assert (
        api["classification"](
            Decimal(actual),
            {"random_mean": Decimal(random), "actual_percentile": Decimal(percentile)},
        )
        == label
    )
