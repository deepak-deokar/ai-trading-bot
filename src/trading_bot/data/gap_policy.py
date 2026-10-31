"""Explicit research acceptance only; no broker schedule or persistence operations."""

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import Field, model_validator

from trading_bot.data.quote_coverage import DailyCoverage
from trading_bot.domain.models import DomainModel


class MissingOpeningRange(DomainModel):
    """Inclusive UTC opening labels within a fixed 05:00-to-05:00 research day."""

    start: time
    end: time

    @property
    def indices(self) -> tuple[int, ...]:
        first = (self.start.hour * 60 + self.start.minute - 300) % 1440 // 5
        last = (self.end.hour * 60 + self.end.minute - 300) % 1440 // 5
        return tuple(range(first, last + 1))

    @model_validator(mode="after")
    def aligned(self) -> Self:
        for value in (self.start, self.end):
            if value.tzinfo or value.second or value.microsecond or value.minute % 5:
                raise ValueError("UTC clock labels must align to five minutes")
        if not self.indices:
            raise ValueError("range must be ordered within the research day")
        return self


class GapEvidence(DomainModel):
    archive_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    report_reference: str = Field(min_length=1)
    report_version: str = Field(min_length=1)
    report_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    normalization_version: str = Field(min_length=1)
    aggregation_version: str = Field(min_length=1)


class GapPolicySegment(DomainModel):
    segment_id: str = Field(min_length=1)
    effective_start_date: date
    effective_end_date: date
    allowed_missing_ranges: tuple[MissingOpeningRange, ...] = Field(min_length=1)
    category: str = Field(min_length=1)
    evidence: GapEvidence

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.effective_end_date < self.effective_start_date:
            raise ValueError("segment dates must be ordered")
        if any(
            d.strftime("%Y-%m") != self.evidence.source_month
            for d in (self.effective_start_date, self.effective_end_date)
        ):
            raise ValueError("segment must be bound to its archive month")
        indices = [i for r in self.allowed_missing_ranges for i in r.indices]
        if len(indices) != len(set(indices)):
            raise ValueError("overlapping missing ranges")
        return self


class DayType(StrEnum):
    NORMAL = "NORMAL"
    HOLIDAY = "HOLIDAY_ASSOCIATED"
    PARTIAL = "FRIDAY_OR_WEEKEND_PARTIAL"
    UNEXPLAINED = "UNEXPLAINED"


class ExcludedDate(DomainModel):
    source_date: date
    day_type: DayType
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def excluded(self) -> Self:
        if self.day_type == DayType.NORMAL:
            raise ValueError("exclusion cannot be NORMAL")
        return self


class ProviderGapPolicy(DomainModel):
    provider: str = Field(min_length=1)
    canonical_symbol: str = Field(min_length=1)
    provider_symbol: str = Field(min_length=1)
    source_timezone: Literal["UTC-05:00 fixed; no DST"]
    interval: Literal["5minute"]
    policy_version: str = Field(min_length=1)
    segments: tuple[GapPolicySegment, ...] = Field(min_length=1)
    excluded_dates: tuple[ExcludedDate, ...] = ()

    @model_validator(mode="after")
    def unambiguous(self) -> Self:
        ordered = sorted(self.segments, key=lambda s: s.effective_start_date)
        if len({s.segment_id for s in ordered}) != len(ordered):
            raise ValueError("duplicate segment identity")
        if any(
            b.effective_start_date <= a.effective_end_date
            for a, b in zip(ordered, ordered[1:], strict=False)
        ):
            raise ValueError("policy segments overlap")
        if len({d.source_date for d in self.excluded_dates}) != len(
            self.excluded_dates
        ):
            raise ValueError("duplicate excluded date")
        return self

    @property
    def policy_key(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


def load_gap_policy(path: Path) -> ProviderGapPolicy:
    return ProviderGapPolicy.model_validate(yaml.safe_load(path.read_text()))


class EligibilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE_UNDER_RESEARCH_POLICY"
    NO_SEGMENT = "NO_MATCHING_POLICY_SEGMENT"
    MISMATCH = "MISSING_SET_MISMATCH"
    UNEXPECTED = "UNEXPECTED_GAPS"
    EXCLUDED = "EXCLUDED_DAY_TYPE"
    NO_DATA = "NO_DATA"
    PROVENANCE = "PROVENANCE_MISMATCH"
    INVALID = "INVALID_COVERAGE"


class GapEligibility(DomainModel):
    status: EligibilityStatus
    reason: str
    source_date: date
    dataset_key: str
    policy_version: str
    policy_key: str
    segment_id: str | None

    @property
    def eligible(self) -> bool:
        return self.status == EligibilityStatus.ELIGIBLE


def evaluate_gap_policy(
    source_date: date,
    coverage: DailyCoverage,
    policy: ProviderGapPolicy,
    *,
    day_type: DayType = DayType.NORMAL,
) -> GapEligibility:
    """Evaluate supplied coverage/provenance; never infer acceptance from old flags."""
    day_type = DayType(day_type)
    ds = coverage.provenance
    segment = next(
        (
            s
            for s in policy.segments
            if s.effective_start_date <= source_date <= s.effective_end_date
        ),
        None,
    )

    def result(status: EligibilityStatus, reason: str) -> GapEligibility:
        return GapEligibility(
            status=status,
            reason=reason,
            source_date=source_date,
            dataset_key=coverage.dataset_key,
            policy_version=policy.policy_version,
            policy_key=policy.policy_key,
            segment_id=segment.segment_id if segment else None,
        )

    if coverage.dataset_key != ds.dataset_key or any(
        getattr(ds, name) != getattr(policy, name)
        for name in (
            "provider",
            "canonical_symbol",
            "provider_symbol",
            "source_timezone",
            "interval",
        )
    ):
        return result(EligibilityStatus.PROVENANCE, "dataset_identity_mismatch")
    start = datetime.combine(source_date, time(5), UTC)
    if (
        ds.selected_source_date != source_date.isoformat()
        or ds.source_month != source_date.strftime("%Y-%m")
        or ds.start != start
        or ds.end != start + timedelta(days=1)
    ):
        return result(EligibilityStatus.PROVENANCE, "source_day_mismatch")
    expected = {start + timedelta(minutes=5 * i) for i in range(288)}
    missing = set(coverage.missing_openings)
    observed = expected - missing
    if (
        coverage.expected_bins != 288
        or len(missing) != len(coverage.missing_openings)
        or not missing <= expected
        or coverage.observed_bars != len(observed)
        or coverage.first_observed_bar != min(observed, default=None)
        or coverage.last_observed_bar != max(observed, default=None)
        or coverage.tick_count < coverage.observed_bars
        or (not observed and coverage.tick_count != 0)
    ):
        return result(EligibilityStatus.INVALID, "inconsistent_coverage")
    if not observed:
        return result(EligibilityStatus.NO_DATA, "no_valid_observations")
    if (
        source_date.weekday() >= 4
        or day_type != DayType.NORMAL
        or any(d.source_date == source_date for d in policy.excluded_dates)
    ):
        return result(EligibilityStatus.EXCLUDED, "excluded_research_day")
    if segment is None:
        return result(EligibilityStatus.NO_SEGMENT, "date_not_evidenced")
    evidence = segment.evidence
    if (
        ds.source_sha256 != evidence.archive_sha256
        or ds.source_month != evidence.source_month
        or ds.normalization_version != evidence.normalization_version
        or ds.aggregation_version != evidence.aggregation_version
    ):
        return result(EligibilityStatus.PROVENANCE, "evidence_binding_mismatch")
    allowed = {
        start + timedelta(minutes=5 * i)
        for r in segment.allowed_missing_ranges
        for i in r.indices
    }
    if missing - allowed:
        return result(EligibilityStatus.UNEXPECTED, "additional_missing_openings")
    if missing != allowed:
        return result(EligibilityStatus.MISMATCH, "missing_openings_differ")
    return result(EligibilityStatus.ELIGIBLE, "exact_evidenced_pattern")
