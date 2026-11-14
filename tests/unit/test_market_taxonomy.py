from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import pytest
from test_xauusd_features import batch

from trading_bot.features.market_state import calculate_market_state
from trading_bot.features.market_taxonomy import (
    STATES,
    WARMUP,
    MarketTaxonomy,
    StateObservation,
    quantile,
    range_state,
    temporal_summary,
)
from trading_bot.features.research_repository import content_hash
from trading_bot.features.xauusd import FeatureValue


def policy():
    return MarketTaxonomy(
        volatility_low=Decimal(1),
        volatility_high=Decimal(2),
        efficiency_low=Decimal("0.25"),
        efficiency_high=Decimal("0.75"),
        development_hash="synthetic",
    )


def row(v, e, r=Decimal("0.5")):
    base = calculate_market_state(batch(1))[0]
    return base.model_copy(
        update={
            "values": tuple(
                FeatureValue(name=k, value=n)
                for k, n in zip(
                    ("mid_change_std_36", "mid_efficiency_12", "bid_range_ratio_12_36"),
                    (v, e, r),
                    strict=True,
                )
            )
        }
    )


def test_quantiles_exact_deterministic():
    values = tuple(Decimal(n) for n in range(1, 10))
    assert quantile(values, Decimal("0.333333")) == 3
    assert quantile(values, Decimal("0.666667")) == 7
    with localcontext() as c:
        c.prec = 2
        assert quantile(tuple(reversed(values)), Decimal("0.666667")) == 7


@pytest.mark.parametrize(
    "v,e,expected",
    [
        ("1", "0.25", STATES[0]),
        ("2", "0.75", STATES[4]),
        ("2.0001", "0.7501", STATES[8]),
        ("1.0001", "0.2501", STATES[4]),
    ],
)
def test_exact_boundaries(v, e, expected):
    assert policy().classify(row(Decimal(v), Decimal(e)))[0] == expected


def test_range_and_warmup():
    assert [range_state(Decimal(s)) for s in ("0.99", "1", "1.01")] == [
        "COMPRESSED",
        "NEUTRAL",
        "EXPANDED",
    ]
    for args in (
        (None, Decimal(1), Decimal(1)),
        (Decimal(1), None, Decimal(1)),
        (Decimal(1), Decimal(1), None),
    ):
        assert policy().classify(row(*args)) == (WARMUP, None)


def test_temporal_segments_counts():
    start = datetime(2024, 2, 1, 5, tzinfo=UTC)
    data = tuple(
        StateObservation(ds, start + timedelta(minutes=i * 5), state, reset)
        for i, ds, state, reset in (
            (0, "a", STATES[0], True),
            (1, "a", STATES[0], False),
            (2, "a", STATES[1], False),
            (3, "a", WARMUP, False),
            (4, "a", STATES[1], False),
            (8, "a", STATES[1], False),
            (9, "a", STATES[1], True),
            (10, "b", STATES[1], False),
        )
    )
    runs, matrix = temporal_summary(data)
    assert runs[STATES[0]] == [2]
    assert runs[STATES[1]] == [1, 1, 1, 1, 1]
    assert sum(sum(row.values()) for row in matrix.values()) == 2
    assert matrix[STATES[0]][STATES[0]] == 1
    assert matrix[STATES[0]][STATES[1]] == 1
    assert sum(sum(v) for v in runs.values()) == 7
    assert temporal_summary(data) == (runs, matrix)


def test_source_day_boundary_and_utc_midnight():
    for hour, expected in ((5, 0), (0, 1)):
        end = datetime(2024, 2, 2, hour, tzinfo=UTC)
        _, matrix = temporal_summary(
            (
                StateObservation("a", end - timedelta(minutes=5), STATES[0]),
                StateObservation("a", end, STATES[0]),
            )
        )
        assert matrix[STATES[0]][STATES[0]] == expected


def test_identity_immutable_and_features_unchanged():
    original = calculate_market_state(batch(60))
    before = content_hash([r.model_dump(mode="json") for r in original])
    p = policy()
    a = [p.classify(r) for r in original]
    assert content_hash(a) == content_hash([p.classify(r) for r in original])
    assert content_hash([r.model_dump(mode="json") for r in original]) == before
    with pytest.raises(ValueError):
        p.volatility_low = Decimal(0)
    assert content_hash(p.model_dump(mode="json")) != content_hash(
        p.model_copy(update={"volatility_low": Decimal("0.1")}).model_dump(mode="json")
    )


def test_offline_report_reconciliation_and_identity():
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "taxonomy_report", Path("scripts/characterize_xauusd_market_state.py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    features = calculate_market_state(batch(90, gap_at=45))
    ds = SimpleNamespace(
        source_month="2024-02",
        selected_source_date="2024-02-20",
        dataset_key="synthetic",
    )
    data = [(ds, r) for r in features]
    first = module.analyze({"datasets": ["synthetic"]}, data)
    second = module.analyze({"datasets": ["synthetic"]}, data)
    assert content_hash(first) == content_hash(second)
    assert first["overall"]["classified"] == 18
    assert first["overall"]["unclassified"] == 72
    assert sum(s["classified"] for s in first["sessions"].values()) == 18
    assert sum(s["count"] for s in first["overall"]["states"].values()) == 18
    assert sum(sum(row.values()) for row in first["transition_counts"].values()) == 16
