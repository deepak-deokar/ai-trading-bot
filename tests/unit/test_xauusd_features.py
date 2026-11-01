from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from trading_bot.data.research_input import ApprovedResearchInputs, ResearchFeatureInput
from trading_bot.features.definitions import FeatureError
from trading_bot.features.xauusd import VERSION, calculate_xauusd

START = datetime(2024, 2, 20, 5, tzinfo=UTC)


def batch(count=40, gap_at=None):
    inputs = []
    previous = None
    for i in range(count):
        opening = START + timedelta(
            minutes=5 * i + (60 if gap_at is not None and i >= gap_at else 0)
        )
        bid = Decimal(100 + i)
        inputs.append(
            ResearchFeatureInput(
                opening_timestamp=opening,
                previous_observed_timestamp=previous,
                tick_count=i + 1,
                bid_open=bid - 1,
                bid_high=bid + 3,
                bid_low=bid - 2,
                bid_close=bid,
                ask_open=bid,
                ask_high=bid + 5,
                ask_low=bid - 1,
                ask_close=bid + 1,
            )
        )
        previous = opening
    return ApprovedResearchInputs(
        dataset_key="synthetic",
        policy_version="synthetic",
        policy_key="synthetic",
        as_of=inputs[-1].available_at,
        inputs=tuple(inputs),
    )


def test_exact_side_spread_activity_and_warmups():
    rows = calculate_xauusd(batch())
    r = rows[0]
    assert r.feature_set_version == VERSION
    for name, value in {
        "mid_close": "100.5",
        "bid_range": "5",
        "ask_range": "6",
        "bid_body": "1",
        "ask_body": "1",
        "spread_open": "1",
        "spread_close": "1",
        "spread_change": "0",
        "tick_count": "1",
    }.items():
        assert r.value(name) == Decimal(value)
    assert not any(
        "volume" in v.name or "mid_high" in v.name or "atr" in v.name for v in r.values
    )
    for period in (1, 3, 12):
        assert rows[period - 1].value(f"return_{period}") is None
        with localcontext() as c:
            c.prec = 50
            assert (
                rows[period].value(f"return_{period}")
                == (Decimal("100.5") + period) / Decimal("100.5") - 1
            )
    assert rows[3].value("momentum_3") == 3
    assert rows[12].value("momentum_12") == 12
    assert rows[10].value("ema_12") is None
    assert rows[11].value("ema_12") == 106
    assert rows[24].value("ema_26") is None
    assert rows[25].value("ema_26") == 113
    assert rows[13].value("rsi_14") is None
    assert rows[14].value("rsi_14") == 100
    assert all(v.unavailable == "WARMUP" for v in r.values if v.value is None)


def test_strong_future_mutation_and_prefix_causality():
    original = batch(60)
    k = 30
    changed = []
    for i, item in enumerate(original.inputs):
        if i > k:
            values = item.model_dump()
            for side in ("bid", "ask"):
                for field in ("open", "high", "low", "close"):
                    values[f"{side}_{field}"] += Decimal(10000 * (i + 1))
            item = ResearchFeatureInput(**values)
        changed.append(item)
    first = calculate_xauusd(original)
    second = calculate_xauusd(original.model_copy(update={"inputs": tuple(changed)}))
    assert first[: k + 1] == second[: k + 1]
    prefix = original.model_copy(
        update={
            "inputs": original.inputs[: k + 1],
            "as_of": original.inputs[k].available_at,
        }
    )
    assert calculate_xauusd(prefix) == first[: k + 1]
    assert first[k + 1 :] != second[k + 1 :]


def test_gap_and_dataset_reset_determinism():
    data = batch(60, gap_at=30)
    rows = calculate_xauusd(data)
    assert len(rows) == 60
    assert rows[30].sequence_reset == "DISCONTINUITY"
    assert rows[30].input.elapsed_since_previous == timedelta(minutes=65)
    assert rows[30].value("return_1") is None
    assert rows[40].value("ema_12") is None
    assert rows[41].value("ema_12") is not None
    assert rows[43].value("rsi_14") is None
    assert rows[44].value("rsi_14") is not None
    assert all(
        v.unavailable == "GAP_WARMUP" for v in rows[30].values if v.value is None
    )
    other = data.model_copy(
        update={"dataset_key": "another", "inputs": data.inputs[20:]}
    )
    assert calculate_xauusd(other)[0].value("ema_12") is None
    with localcontext() as context:
        context.prec = 6
        assert calculate_xauusd(data) == rows
    assert calculate_xauusd(data) == rows


def test_flat_and_falling_rsi():
    data = batch()
    for descending, expected in [(False, 50), (True, 0)]:
        items = []
        for i, item in enumerate(data.inputs):
            delta = Decimal(-2 * i if descending else -i)
            values = item.model_dump()
            for side in ("bid", "ask"):
                for key in ("open", "high", "low", "close"):
                    values[f"{side}_{key}"] += delta
            items.append(ResearchFeatureInput(**values))
        assert (
            calculate_xauusd(data.model_copy(update={"inputs": tuple(items)}))[
                14
            ].value("rsi_14")
            == expected
        )


def test_cutoff_and_order_rejection():
    data = batch()
    with pytest.raises(FeatureError):
        calculate_xauusd(data.model_copy(update={"as_of": START}))
    with pytest.raises(FeatureError):
        calculate_xauusd(
            data.model_copy(update={"inputs": tuple(reversed(data.inputs))})
        )
