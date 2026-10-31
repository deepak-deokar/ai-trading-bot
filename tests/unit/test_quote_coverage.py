from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.data.quote_coverage import (
    AcceptedGapPattern,
    Completeness,
    daily_coverage,
    recurring_pattern,
)
from trading_bot.domain.quote_bars import QuoteBar

PATTERN_BINS = tuple(range(204, 216))


def fixture(day=16, missing=PATTERN_BINS, provider="TEST_FIXTURE"):
    start = datetime(2024, 1, day, 5, tzinfo=UTC)
    ds = QuoteDataset(
        provider=provider,
        provider_symbol="XAU/USD",
        source_archive="synthetic.zip",
        source_sha256="a" * 64,
        source_month="2024-01",
        selected_source_date=f"2024-01-{day}",
        start=start,
        end=start + timedelta(days=1),
        source_timezone="UTC-05:00",
        normalization_version="fixture-v1",
        aggregation_version="fixture-v1",
    )
    bars = tuple(
        QuoteBar(
            opening_timestamp=start + timedelta(minutes=i * 5),
            tick_count=1,
            **{
                f"{side}_{k}": Decimal("2000")
                for side in ("bid", "ask")
                for k in ("open", "high", "low", "close")
            },
        )
        for i in range(288)
        if i not in missing
    )
    return ds, bars


def policy(ds):
    return AcceptedGapPattern(
        pattern_id="synthetic",
        reference=ds,
        accepted_dates=("2024-01-16", "2024-01-17"),
        missing_bin_indices=tuple(range(204, 216)),
    )


def test_pilot_and_explicit_acceptance_no_fill():
    ds, bars = fixture()
    before = tuple(bars)
    s = daily_coverage(ds, bars)
    assert (s.expected_bins, s.observed_bars, len(s.missing_openings)) == (288, 276, 12)
    assert not s.research_usable
    accepted = daily_coverage(ds, bars, policy(ds))
    assert accepted.research_usable and accepted.classification == Completeness.COMPLETE
    assert accepted.longest_missing_run_bins == 12 and accepted.unexpected_gaps == ()
    assert accepted.missing_openings[0] == datetime(2024, 1, 16, 22, tzinfo=UTC)
    assert accepted.missing_openings[-1] == datetime(2024, 1, 16, 22, 55, tzinfo=UTC)
    assert bars == before and len(bars) == 276


def test_unexpected_and_consecutive_gaps():
    ds, bars = fixture(missing=tuple(range(204, 216)) + (1, 2, 50))
    s = daily_coverage(ds, bars, policy(ds))
    assert len(s.unexpected_gaps) == 3 and s.longest_missing_run_bins == 12
    assert s.classification == Completeness.INCOMPLETE and not s.research_usable


def test_no_data_and_complete_and_pattern_mismatch():
    ds, bars = fixture(missing=())
    assert daily_coverage(ds, bars).research_usable
    assert daily_coverage(ds, ()).classification == Completeness.NO_DATA
    assert not daily_coverage(ds, (), policy(ds)).research_usable
    assert (
        daily_coverage(ds, bars, policy(ds)).classification
        == Completeness.PATTERN_MISMATCH
    )


def test_recurring_requires_distinct_dates_same_family():
    a = daily_coverage(*fixture())
    b = daily_coverage(*fixture(17))
    r = recurring_pattern((a, b), tuple(range(204, 216)))
    assert r["classification"] == "RECURRING_PROVIDER_GAP_PATTERN"
    assert r["exact_days"] == ["2024-01-16", "2024-01-17"]
    assert (
        recurring_pattern((a,), tuple(range(204, 216)))["classification"]
        == "INSUFFICIENT_RECURRING_EVIDENCE"
    )
    with pytest.raises(ValueError):
        recurring_pattern((a, a), tuple(range(204, 216)))
    with pytest.raises(ValueError):
        recurring_pattern(
            (a, daily_coverage(*fixture(17, provider="OTHER"))), tuple(range(204, 216))
        )


def test_isolation_and_boundaries():
    ds, bars = fixture()
    assert daily_coverage(ds, bars).last_observed_bar == datetime(
        2024, 1, 17, 4, 55, tzinfo=UTC
    )
    for update in [
        {"provider": "OTHER"},
        {"source_sha256": "b" * 64},
        {"normalization_version": "other"},
    ]:
        with pytest.raises(ValueError):
            daily_coverage(ds.model_copy(update=update), bars, policy(ds))
    with pytest.raises(ValueError):
        daily_coverage(ds, bars + (bars[0],))
    with pytest.raises(ValueError):
        daily_coverage(ds.model_copy(update={"end": ds.end - timedelta(hours=1)}), bars)
