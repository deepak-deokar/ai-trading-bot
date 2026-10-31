"""Derived research coverage, never broker schedules or execution permission."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.domain.models import DomainModel
from trading_bot.domain.quote_bars import QuoteBar


class Completeness(StrEnum):
    COMPLETE = "COMPLETE_UNDER_OBSERVED_PROVIDER_PATTERN"
    INCOMPLETE = "INCOMPLETE_UNEXPECTED_GAPS"
    PATTERN_MISMATCH = "INCOMPLETE_PATTERN_MISMATCH"
    NO_DATA = "NO_DATA"


def family(dataset: QuoteDataset) -> tuple[str, ...]:
    return (
        dataset.provider,
        dataset.provider_symbol,
        dataset.canonical_symbol,
        dataset.source_sha256,
        dataset.source_timezone,
        dataset.normalization_version,
        dataset.aggregation_version,
        dataset.interval,
        dataset.start.timetz().isoformat(),
    )


class AcceptedGapPattern(DomainModel):
    """Explicit caller acceptance, scoped to source and specific research days."""

    pattern_id: str = Field(min_length=1)
    reference: QuoteDataset
    accepted_dates: tuple[str, ...]
    missing_bin_indices: tuple[int, ...]

    @model_validator(mode="after")
    def valid_indices(self) -> Self:
        if not self.accepted_dates or not self.missing_bin_indices:
            raise ValueError("explicit dates and missing bins required")
        if len(set(self.missing_bin_indices)) != len(self.missing_bin_indices):
            raise ValueError("duplicate pattern bins")
        if any(i < 0 or i >= 288 for i in self.missing_bin_indices):
            raise ValueError("pattern bin outside daily range")
        return self

    def openings(self, dataset: QuoteDataset) -> set[datetime]:
        if (
            family(dataset) != family(self.reference)
            or dataset.selected_source_date not in self.accepted_dates
            or dataset.start.timetz() != self.reference.start.timetz()
        ):
            raise ValueError("accepted pattern is not applicable to this dataset")
        return {
            dataset.start + timedelta(minutes=5 * i) for i in self.missing_bin_indices
        }


class DailyCoverage(DomainModel):
    dataset_key: str
    provenance: QuoteDataset
    expected_bins: int
    observed_bars: int
    missing_openings: tuple[datetime, ...]
    unexpected_gaps: tuple[datetime, ...]
    longest_missing_run_bins: int
    first_observed_bar: datetime | None
    last_observed_bar: datetime | None
    tick_count: int
    accepted_pattern_id: str | None
    pattern_matches: bool
    classification: Completeness
    research_usable: bool


def daily_coverage(
    dataset: QuoteDataset,
    bars: tuple[QuoteBar, ...],
    accepted_pattern: AcceptedGapPattern | None = None,
) -> DailyCoverage:
    if dataset.end - dataset.start != timedelta(days=1):
        raise ValueError("coverage requires a complete 24-hour research-day range")
    expected = {dataset.start + timedelta(minutes=5 * i) for i in range(288)}
    observed = {bar.opening_timestamp for bar in bars}
    if len(observed) != len(bars) or not observed <= expected:
        raise ValueError("duplicate or out-of-range bars")
    if any(
        b.canonical_symbol != dataset.canonical_symbol or b.interval != dataset.interval
        for b in bars
    ):
        raise ValueError("bar identity mismatch")
    missing = expected - observed
    accepted = accepted_pattern.openings(dataset) if accepted_pattern else set()
    unexpected = missing - accepted
    matches = missing == accepted
    classification = (
        Completeness.NO_DATA
        if not bars
        else (
            Completeness.INCOMPLETE
            if unexpected
            else Completeness.PATTERN_MISMATCH if not matches else Completeness.COMPLETE
        )
    )
    longest = streak = 0
    for opening in sorted(expected):
        streak = streak + 1 if opening in missing else 0
        longest = max(longest, streak)
    return DailyCoverage(
        dataset_key=dataset.dataset_key,
        provenance=dataset,
        expected_bins=288,
        observed_bars=len(bars),
        missing_openings=tuple(sorted(missing)),
        unexpected_gaps=tuple(sorted(unexpected)),
        longest_missing_run_bins=longest,
        first_observed_bar=min(observed) if observed else None,
        last_observed_bar=max(observed) if observed else None,
        tick_count=sum(b.tick_count for b in bars),
        accepted_pattern_id=accepted_pattern.pattern_id if accepted_pattern else None,
        pattern_matches=matches,
        classification=classification,
        research_usable=classification == Completeness.COMPLETE,
    )


def coverage_for_run(
    repo: QuoteBarRepository,
    run_id: UUID,
    accepted_pattern: AcceptedGapPattern | None = None,
) -> DailyCoverage:
    evidence = repo.get_run(run_id)
    if not evidence or not isinstance(evidence.get("manifest"), dict):
        raise ValueError("quote-bar run provenance not found")
    manifest = evidence["manifest"]
    assert isinstance(manifest, dict)
    dataset = QuoteDataset.model_validate(
        {k: manifest[k] for k in QuoteDataset.model_fields if k in manifest}
    )
    bars = repo.get_bars(
        dataset_key=dataset.dataset_key,
        symbol=dataset.canonical_symbol,
        interval=dataset.interval,
        start=dataset.start,
        end=dataset.end,
    )
    return daily_coverage(dataset, bars, accepted_pattern)


def recurring_pattern(
    summaries: tuple[DailyCoverage, ...], candidate_indices: tuple[int, ...]
) -> dict[str, object]:
    """Observation only: never automatically accepts or expands a gap pattern."""
    if not summaries or len({family(s.provenance) for s in summaries}) != 1:
        raise ValueError("recurrence requires one source/provenance family")
    dates = [s.provenance.selected_source_date for s in summaries]
    if len(dates) != len(set(dates)):
        raise ValueError("duplicate dates are not independent observations")
    exact: list[str] = []
    differs: list[str] = []
    for summary in summaries:
        candidate = {
            summary.provenance.start + timedelta(minutes=5 * i)
            for i in candidate_indices
        }
        (exact if set(summary.missing_openings) == candidate else differs).append(
            summary.provenance.selected_source_date
        )
    return {
        "classification": (
            "RECURRING_PROVIDER_GAP_PATTERN"
            if len(exact) >= 2
            else "INSUFFICIENT_RECURRING_EVIDENCE"
        ),
        "exact_days": exact,
        "different_days": differs,
    }
