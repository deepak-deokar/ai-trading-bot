from decimal import Decimal, localcontext

import pytest
from test_xauusd_features import batch

from trading_bot.features.market_state import calculate_market_state
from trading_bot.features.market_state_v2 import (
    MarketTaxonomyV2,
    calculate_market_state_v2,
)
from trading_bot.features.market_taxonomy import MarketTaxonomy
from trading_bot.features.research_repository import content_hash


def oscillating(short=1, long=1, count=37, gap_at=None):
    source = batch(count, gap_at=gap_at)
    price = Decimal(100)
    items = []
    for i, item in enumerate(source.inputs):
        if i:
            price += Decimal(short if i > 24 else long) * (1 if i % 2 else -1)
        items.append(
            item.model_copy(
                update={
                    f"{side}_{field}": price + offset
                    for side, offset in (("bid", Decimal(0)), ("ask", Decimal(1)))
                    for field in ("open", "high", "low", "close")
                }
            )
        )
    return source.model_copy(update={"inputs": tuple(items)})


@pytest.mark.parametrize(
    "short,long,label", [(4, 1, "EXPANDED"), (1, 4, "COMPRESSED"), (1, 1, "NEUTRAL")]
)
def test_synthetic_states(short, long, label):
    source = oscillating(short, long)
    rows = calculate_market_state_v2(source)
    ratio = rows[-1].volatility_ratio_12_36
    assert ratio is not None
    assert (
        ratio > 1
        if label == "EXPANDED"
        else ratio < 1 if label == "COMPRESSED" else ratio == 1
    )
    assert all(r.volatility_ratio_12_36 is None for r in rows[:36])
    assert rows[35].ratio_unavailable == "WARMUP"
    assert rows[-1].baseline.value("bid_range_ratio_12_36") <= 1
    v1 = calculate_market_state(source)
    assert content_hash(
        [r.baseline.model_dump(mode="json") for r in rows]
    ) == content_hash([r.model_dump(mode="json") for r in v1])
    p = MarketTaxonomyV2(
        volatility_low=Decimal(1),
        volatility_high=Decimal(2),
        efficiency_low=Decimal("0.2"),
        efficiency_high=Decimal("0.7"),
        development_hash="synthetic",
    )
    assert p.classify(rows[-1])[1] == label


def test_zero_denominator_not_fallback_or_warmup():
    rows = calculate_market_state_v2(batch(40))
    assert rows[35].ratio_unavailable == "WARMUP"
    assert rows[36].ratio_unavailable == "ZERO_DENOMINATOR"
    assert rows[36].volatility_ratio_12_36 is None
    p = MarketTaxonomyV2(
        volatility_low=Decimal(1),
        volatility_high=Decimal(2),
        efficiency_low=Decimal("0.2"),
        efficiency_high=Decimal("0.7"),
        development_hash="synthetic",
    )
    assert p.classify(rows[36]) == ("LOW_VOL_DIRECTIONAL", None)


def test_future_mutation_prefix_and_context():
    source = oscillating(count=90)
    first = calculate_market_state_v2(source)
    prefix = source.model_copy(
        update={"inputs": source.inputs[:45], "as_of": source.inputs[44].available_at}
    )
    assert calculate_market_state_v2(prefix) == first[:45]
    changed = list(source.inputs)
    changed[60] = changed[60].model_copy(
        update={
            "bid_high": Decimal(9999),
            "ask_high": Decimal(10000),
            "bid_close": Decimal(9999),
            "ask_close": Decimal(10000),
        }
    )
    assert (
        calculate_market_state_v2(source.model_copy(update={"inputs": tuple(changed)}))[
            :60
        ]
        == first[:60]
    )
    with localcontext() as c:
        c.prec = 6
        assert calculate_market_state_v2(source) == first


def test_gap_day_and_dataset_resets():
    rows = calculate_market_state_v2(oscillating(count=90, gap_at=45))
    assert rows[44].volatility_ratio_12_36 is not None
    assert rows[45].baseline.sequence_reset == "DISCONTINUITY"
    assert rows[80].ratio_unavailable == "GAP_WARMUP"
    assert rows[81].volatility_ratio_12_36 is not None
    rows = calculate_market_state_v2(oscillating(count=330))
    assert rows[288].baseline.sequence_reset == "SOURCE_DAY"
    assert rows[323].volatility_ratio_12_36 is None
    assert rows[324].volatility_ratio_12_36 is not None
    source = oscillating(count=90)
    new = source.model_copy(update={"dataset_key": "new", "inputs": source.inputs[45:]})
    assert (
        calculate_market_state_v2(new)[0].baseline.sequence_reset == "DATASET_BOUNDARY"
    )
    assert calculate_market_state_v2(new)[35].volatility_ratio_12_36 is None


def test_core_thresholds_equal_and_immutable():
    args = dict(
        volatility_low=Decimal(1),
        volatility_high=Decimal(2),
        efficiency_low=Decimal("0.2"),
        efficiency_high=Decimal("0.7"),
        development_hash="synthetic",
    )
    old, new = MarketTaxonomy(**args), MarketTaxonomyV2(**args)
    rows = calculate_market_state_v2(oscillating(count=90))
    assert [old.classify(r.baseline)[0] for r in rows] == [
        new.classify(r)[0] for r in rows
    ]
    with pytest.raises(ValueError):
        rows[0].volatility_ratio_12_36 = Decimal(1)
    with pytest.raises(ValueError):
        new.volatility_low = Decimal(0)


def test_frozen_v1_artifacts_unchanged():
    import hashlib
    from pathlib import Path

    frozen = {
        "src/trading_bot/features/market_state.py": (
            "36cdab649c6a88315551149a9142899f" "1884f1e18f33367672a0a2a8a069a4eb"
        ),
        "src/trading_bot/features/market_taxonomy.py": (
            "c184bb0e98b14f1cbf2589fc8daeba0b" "11e350a806ec93d1dfe8b6fc4440c922"
        ),
        "config/xauusd_market_state_taxonomy_v1.yaml": (
            "104a598e11cdd2ac59b397b959d105fa" "e6dd2e2acf485b4eed90a7c3a4ca5349"
        ),
        "docs/xauusd-market-state-features.json": (
            "2f388d203670608c8a1337bb9566b43e" "27158e5461c50a0107f0eb3c7ae5cf4d"
        ),
        "docs/xauusd-market-state-characterization.json": (
            "96c395cdfa7bd811c036f900dc30b183" "e46768610cf98eaa32cf82ec18cf46b4"
        ),
    }
    for path, expected in frozen.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
