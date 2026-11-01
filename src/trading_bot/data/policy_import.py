"""Policy-gated quote-bar persistence; no eligibility heuristics or network access."""

from datetime import date

from trading_bot.data.gap_policy import (
    DayType,
    GapEligibility,
    ProviderGapPolicy,
    evaluate_gap_policy,
)
from trading_bot.data.quote_bar_storage import (
    QuoteBarRepository,
    QuoteDataset,
    QuoteImportResult,
)
from trading_bot.data.quote_coverage import DailyCoverage, daily_coverage
from trading_bot.domain.models import DomainModel
from trading_bot.domain.quote_bars import QuoteBar


class PolicyDayAudit(DomainModel):
    coverage: DailyCoverage
    eligibility: GapEligibility
    imported: QuoteImportResult | None = None


def evaluate_policy_day(
    dataset: QuoteDataset,
    bars: tuple[QuoteBar, ...],
    policy: ProviderGapPolicy,
    *,
    raw_ticks: int,
    invalid_ticks: int,
    day_type: DayType = DayType.NORMAL,
) -> PolicyDayAudit:
    """Bind identity to policy, validate observations and evaluate before any write."""
    if (
        type(raw_ticks) is not int
        or type(invalid_ticks) is not int
        or invalid_ticks != 0
        or raw_ticks != sum(b.tick_count for b in bars)
    ):
        raise ValueError(
            "policy import requires consistent counts and zero invalid ticks"
        )
    if dataset.gap_policy_key is not None and (
        dataset.gap_policy_key != policy.policy_key
        or dataset.gap_policy_version != policy.policy_version
    ):
        raise ValueError("dataset is already bound to a different policy")
    bound = QuoteDataset.model_validate(
        dataset.model_dump()
        | {
            "gap_policy_version": policy.policy_version,
            "gap_policy_key": policy.policy_key,
        }
    )
    # Revalidate immutable input models, including any unchecked model_copy changes.
    validated = tuple(QuoteBar.model_validate(b.model_dump()) for b in bars)
    coverage = daily_coverage(bound, validated)
    eligibility = evaluate_gap_policy(
        date.fromisoformat(bound.selected_source_date),
        coverage,
        policy,
        day_type=day_type,
    )
    return PolicyDayAudit(coverage=coverage, eligibility=eligibility)


def import_policy_day(
    repository: QuoteBarRepository,
    dataset: QuoteDataset,
    bars: tuple[QuoteBar, ...],
    policy: ProviderGapPolicy,
    *,
    raw_ticks: int,
    invalid_ticks: int,
    day_type: DayType = DayType.NORMAL,
) -> PolicyDayAudit:
    audit = evaluate_policy_day(
        dataset,
        bars,
        policy,
        raw_ticks=raw_ticks,
        invalid_ticks=invalid_ticks,
        day_type=day_type,
    )
    if not audit.eligibility.eligible:
        return audit
    imported = repository.import_bars(
        audit.coverage.provenance,
        bars,
        raw_ticks=raw_ticks,
        invalid_ticks=invalid_ticks,
    )
    return PolicyDayAudit(
        coverage=audit.coverage, eligibility=audit.eligibility, imported=imported
    )
