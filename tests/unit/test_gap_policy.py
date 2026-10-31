"""Synthetic quotes only; real evidence hashes bind the configured selection."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from trading_bot.data.gap_policy import (
    DayType,
    MissingOpeningRange,
    ProviderGapPolicy,
    evaluate_gap_policy,
    load_gap_policy,
)
from trading_bot.data.gap_policy import (
    EligibilityStatus as Status,
)
from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.data.quote_coverage import daily_coverage
from trading_bot.domain.quote_bars import QuoteBar

POLICY = load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml"))


def sample(day, missing=None, **overrides):
    day = date.fromisoformat(day)
    start = datetime(day.year, day.month, day.day, 5, tzinfo=UTC)
    segment = next(
        (
            s
            for s in POLICY.segments
            if s.effective_start_date <= day <= s.effective_end_date
        ),
        POLICY.segments[0],
    )
    if missing is None:
        missing = {i for r in segment.allowed_missing_ranges for i in r.indices}
    values = dict(
        provider="HISTDATA",
        provider_symbol="XAU/USD",
        source_archive="synthetic-quotes.zip",
        source_sha256=segment.evidence.archive_sha256,
        source_month=day.strftime("%Y-%m"),
        selected_source_date=day.isoformat(),
        start=start,
        end=start + timedelta(days=1),
        source_timezone=POLICY.source_timezone,
        normalization_version="histdata-ticks-v1",
        aggregation_version="bid-ask-utc-5minute-v1",
    )
    values.update(overrides)
    ds = QuoteDataset(**values)
    bars = tuple(
        QuoteBar(
            opening_timestamp=start + timedelta(minutes=5 * i),
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
    return day, daily_coverage(ds, bars)


@pytest.mark.parametrize(
    "day",
    [
        "2024-01-16",
        "2024-02-20",
        "2024-03-04",
        "2024-03-07",
        "2024-03-11",
        "2024-03-27",
        "2024-04-01",
        "2024-04-30",
    ],
)
def test_normal_dates(day):
    day, coverage = sample(day)
    before = coverage.model_dump()
    result = evaluate_gap_policy(day, coverage, POLICY)
    assert result.eligible and result.status == Status.ELIGIBLE
    assert coverage.model_dump() == before
    assert not coverage.research_usable  # G2B2 default acceptance is unchanged.


@pytest.mark.parametrize(
    "day",
    [
        "2024-01-15",
        "2024-02-19",
        "2024-03-28",
        "2024-03-29",
        "2024-01-19",
        "2024-04-06",
    ],
)
def test_exclusions_even_with_exact_missing_set(day):
    day, c = sample(day)
    assert evaluate_gap_policy(day, c, POLICY).status == Status.EXCLUDED


@pytest.mark.parametrize(
    "missing,status",
    [
        (set(range(204, 216)) | {0}, Status.UNEXPECTED),
        (set(range(204, 215)), Status.MISMATCH),
        (set(), Status.MISMATCH),
        (set(range(288)), Status.NO_DATA),
    ],
)
def test_exact_missing_set(missing, status):
    day, c = sample("2024-01-16", missing)
    assert evaluate_gap_policy(day, c, POLICY).status == status


@pytest.mark.parametrize(
    "changes",
    [
        {"source_sha256": "a" * 64},
        {"provider": "OTHER"},
        {"provider_symbol": "GOLD"},
        {"normalization_version": "wrong"},
        {"aggregation_version": "wrong"},
        {"source_timezone": "America/New_York"},
        {"source_month": "2024-02"},
    ],
)
def test_provenance(changes):
    day, c = sample("2024-01-16", **changes)
    assert evaluate_gap_policy(day, c, POLICY).status == Status.PROVENANCE


@pytest.mark.parametrize("day", ["2023-12-28", "2024-03-01", "2024-05-01"])
def test_outside_policy(day):
    day, c = sample(day)
    expected = Status.EXCLUDED if day.weekday() >= 4 else Status.NO_SEGMENT
    assert evaluate_gap_policy(day, c, POLICY).status == expected


def test_external_classification_and_inconsistent_coverage():
    day, c = sample("2024-01-16")
    assert (
        evaluate_gap_policy(day, c, POLICY, day_type=DayType.UNEXPLAINED).status
        == Status.EXCLUDED
    )
    assert (
        evaluate_gap_policy(
            day, c.model_copy(update={"observed_bars": 0}), POLICY
        ).status
        == Status.INVALID
    )
    assert (
        evaluate_gap_policy(
            day, c.model_copy(update={"dataset_key": "wrong"}), POLICY
        ).status
        == Status.PROVENANCE
    )
    assert evaluate_gap_policy(date(2024, 1, 17), c, POLICY).status == Status.PROVENANCE


def test_policy_validation_and_identity():
    data = POLICY.model_dump()
    data["segments"] = (*POLICY.segments, POLICY.segments[0])
    with pytest.raises(ValidationError):
        ProviderGapPolicy.model_validate(data)
    with pytest.raises(ValidationError):
        POLICY.policy_version = "changed"
    assert (
        load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml")).policy_key
        == POLICY.policy_key
    )
    changed = POLICY.model_copy(update={"policy_version": "v2"})
    assert changed.policy_key != POLICY.policy_key
    with pytest.raises(ValidationError):
        MissingOpeningRange(start="22:01", end="22:55")
    with pytest.raises(ValidationError):
        MissingOpeningRange(start="04:55", end="05:00")


def test_evidence_hashes():
    import hashlib

    for segment in POLICY.segments:
        evidence = segment.evidence
        assert (
            hashlib.sha256(Path(evidence.report_reference).read_bytes()).hexdigest()
            == evidence.report_sha256
        )


def test_distinct_segments_cannot_overlap():
    data = POLICY.model_dump()
    overlapping = POLICY.segments[0].model_copy(update={"segment_id": "different"})
    data["segments"] = (*POLICY.segments, overlapping)
    with pytest.raises(ValidationError, match="segments overlap"):
        ProviderGapPolicy.model_validate(data)


def test_clock_regimes_are_not_interchangeable():
    day, c = sample("2024-03-11", set(range(204, 216)))
    assert evaluate_gap_policy(day, c, POLICY).status == Status.UNEXPECTED
    day, c = sample("2024-04-01", set(range(192, 204)))
    assert evaluate_gap_policy(day, c, POLICY).status == Status.UNEXPECTED


def test_partial_and_no_data_holiday():
    day, c = sample("2024-01-19", set(range(204, 288)))
    assert evaluate_gap_policy(day, c, POLICY).status == Status.EXCLUDED
    day, c = sample("2024-03-29", set(range(288)))
    assert evaluate_gap_policy(day, c, POLICY).status == Status.NO_DATA


def test_naive_duplicate_missing_and_overnight_range():
    day, c = sample("2024-01-16")
    naive = tuple(t.replace(tzinfo=None) for t in c.missing_openings)
    assert (
        evaluate_gap_policy(
            day, c.model_copy(update={"missing_openings": naive}), POLICY
        ).status
        == Status.INVALID
    )
    duplicate = (*c.missing_openings, c.missing_openings[0])
    assert (
        evaluate_gap_policy(
            day, c.model_copy(update={"missing_openings": duplicate}), POLICY
        ).status
        == Status.INVALID
    )
    assert MissingOpeningRange(start="23:55", end="00:05").indices == (227, 228, 229)
