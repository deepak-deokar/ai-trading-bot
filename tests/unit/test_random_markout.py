from dataclasses import replace
from decimal import Decimal as D

import pytest

from trading_bot.data.random_markout import Observation, distribution, matched_trials


def pool():
    return tuple(
        Observation(f"{side}-{i}", ("2024-02", "ASIA", side), D(i) / 10, D(2), D(3))
        for side in ("BUY", "SELL")
        for i in range(5)
    )


def test_matching_determinism_and_price_blind_sampling():
    counts = {("2024-02", "ASIA", "BUY"): 3, ("2024-02", "ASIA", "SELL"): 2}
    first = matched_trials(pool(), counts, strategy="fixture", horizon=5)
    assert len(first) == 1000
    assert first == matched_trials(
        tuple(reversed(pool())), counts, strategy="fixture", horizon=5
    )
    changed = matched_trials(
        tuple(replace(p, markout=D(-999)) for p in pool()),
        counts,
        strategy="fixture",
        horizon=5,
    )
    assert [x["selection_hash"] for x in first] == [
        x["selection_hash"] for x in changed
    ]
    for trial in first:
        assert trial["BUY"]["count"] == 3 and trial["SELL"]["count"] == 2
        assert trial["ALL"]["count"] == 5
    assert first != matched_trials(pool(), counts, strategy="fixture", horizon=10)


def test_no_replacement_and_no_silent_fallback():
    counts = {("2024-02", "ASIA", "BUY"): 5}
    result = matched_trials(pool(), counts, strategy="fixture", horizon=5)
    assert all(t["ALL"]["mean_markout"] == D(".2") for t in result)
    with pytest.raises(ValueError):
        matched_trials(
            pool(), {("2024-02", "ASIA", "BUY"): 6}, strategy="fixture", horizon=5
        )
    with pytest.raises(ValueError):
        matched_trials(pool() + pool()[:1], counts, strategy="fixture", horizon=5)


def test_distribution_percentile_conventions():
    result = distribution([D(i) for i in range(1000)], D(499))
    assert result["p05"] == 49 and result["p95"] == 949
    assert result["random_mean"] == result["random_median"] == D("499.5")
    assert result["actual_percentile"] == D("49.95")
    assert distribution([D(0)] * 1000, D(0))["actual_percentile"] == 50


def test_month_and_session_matching_are_exact():
    observations = tuple(
        Observation(str(i), (month, session, "BUY"), D(i), D(2), D(3))
        for i, (month, session) in enumerate(
            [
                ("2024-02", "ASIA"),
                ("2024-02", "LONDON"),
                ("2024-03", "ASIA"),
                ("2024-03", "LONDON"),
            ]
        )
    )
    requested = {observations[0].stratum: 1, observations[3].stratum: 1}
    trials = matched_trials(observations, requested, strategy="fixture", horizon=20)
    assert all(t["ALL"]["mean_markout"] == D("1.5") for t in trials)
    assert all(t["ALL"]["count"] == 2 for t in trials)
