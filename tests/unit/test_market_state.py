from datetime import timedelta
from decimal import Decimal, localcontext

import pytest
from test_xauusd_features import batch

from trading_bot.features.definitions import FeatureError
from trading_bot.features.market_state import calculate_market_state
from trading_bot.features.xauusd import calculate_xauusd


def test_arithmetic_and_warmups():
    rows = calculate_market_state(batch(50))
    assert rows[0].value("bid_true_range") is None
    assert rows[1].value("bid_true_range") == 5
    assert rows[1].value("ask_true_range") == 6
    assert rows[13].value("bid_atr_14") is None
    assert rows[14].value("bid_atr_14") == 5
    assert rows[14].value("ask_atr_14") == 6
    for n in (12, 36):
        assert rows[n - 2].value(f"bid_range_{n}") is None
        assert rows[n - 1].value(f"bid_range_{n}") == n + 4
        assert rows[n - 1].value(f"mid_change_std_{n}") is None
        assert rows[n].value(f"mid_change_std_{n}") == 0
    assert rows[11].value("mid_efficiency_12") is None
    assert rows[12].value("mid_efficiency_12") == 1
    assert rows[36].value("bid_range_ratio_12_36") == Decimal("0.4")


def test_future_prefix_determinism_and_baseline():
    source = batch(60)
    baseline = calculate_xauusd(source)
    full = calculate_market_state(source)
    prefix = source.model_copy(
        update={"inputs": source.inputs[:30], "as_of": source.inputs[29].available_at}
    )
    assert calculate_market_state(prefix) == full[:30]
    changed = list(source.inputs)
    changed[40] = changed[40].model_copy(
        update={"bid_high": Decimal(99999), "ask_high": Decimal(100000)}
    )
    assert (
        calculate_market_state(source.model_copy(update={"inputs": tuple(changed)}))[
            :40
        ]
        == full[:40]
    )
    with localcontext() as ctx:
        ctx.prec = 8
        assert calculate_market_state(source) == full
    assert calculate_xauusd(source) == baseline


def test_gap_and_day_reset():
    rows = calculate_market_state(batch(70, gap_at=40))
    assert rows[40].sequence_reset == "DISCONTINUITY"
    assert rows[40].value("bid_true_range") is None
    assert rows[54].value("bid_atr_14") == 5
    source = batch(300)
    rows = calculate_market_state(source)
    assert rows[288].sequence_reset == "SOURCE_DAY"
    assert rows[288].value("bid_true_range") is None
    assert rows[288].value("mid_efficiency_12") is None
    assert calculate_market_state(batch(1))[0].sequence_reset == "DATASET_BOUNDARY"


def test_flat_and_choppy():
    source = batch(50)
    for flat in (True, False):
        inputs = []
        for i, item in enumerate(source.inputs):
            price = Decimal(100 if flat else 100 + i % 2)
            inputs.append(
                item.model_copy(
                    update={
                        f"{side}_{field}": price
                        for side in ("bid", "ask")
                        for field in ("open", "high", "low", "close")
                    }
                )
            )
        rows = calculate_market_state(
            source.model_copy(update={"inputs": tuple(inputs)})
        )
        assert rows[-1].value("mid_efficiency_12") == 0
        assert rows[-1].value("mid_change_std_12") == (0 if flat else 1)
        assert rows[-1].value("bid_range_ratio_12_36") == (0 if flat else 1)


def test_invalid_order_and_incomplete():
    source = batch(20)
    for changes in (
        {"inputs": tuple(reversed(source.inputs))},
        {"as_of": source.as_of - timedelta(seconds=1)},
    ):
        with pytest.raises(FeatureError):
            calculate_market_state(source.model_copy(update=changes))


def test_true_range_previous_close_and_side_independence():
    source = batch(20)
    items = list(source.inputs)
    old = items[1]
    items[1] = old.model_copy(
        update={
            "bid_open": Decimal(110),
            "bid_high": Decimal(112),
            "bid_low": Decimal(109),
            "bid_close": Decimal(111),
            "ask_open": Decimal(120),
            "ask_high": Decimal(125),
            "ask_low": Decimal(118),
            "ask_close": Decimal(122),
        }
    )
    rows = calculate_market_state(source.model_copy(update={"inputs": tuple(items)}))
    assert rows[1].value("bid_true_range") == 12
    assert rows[1].value("ask_true_range") == 24
    assert all(
        Decimal(0) <= r.value("mid_efficiency_12") <= Decimal(1) for r in rows[12:]
    )
    with pytest.raises(ValueError):
        rows[0].dataset_key = "changed"
