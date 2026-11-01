"""Completed bid/ask research inputs; no indicators or execution prices."""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import field_validator, model_validator

from trading_bot.data.gap_policy import DayType, ProviderGapPolicy
from trading_bot.data.policy_import import evaluate_policy_day
from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.database.models import BidAskBar
from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote


class AnalyticalPriceBasis(StrEnum):
    BID = "BID"
    ASK = "ASK"
    MID_CLOSE = "MID_CLOSE_ANALYTICAL_ONLY"


class ResearchFeatureInput(QuoteBar):
    """Bar [T,T+5m), usable at its close; no reconstructed midpoint OHLC."""

    previous_observed_timestamp: datetime | None = None
    exact_spread_min: Literal[None] = None
    exact_spread_max: Literal[None] = None

    @field_validator("previous_observed_timestamp")
    @classmethod
    def previous_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        value = utc(value)
        if value.minute % 5 or value.second or value.microsecond:
            raise ValueError("previous opening must align to five minutes")
        return value

    @model_validator(mode="after")
    def earlier(self) -> Self:
        if (
            self.previous_observed_timestamp is not None
            and self.previous_observed_timestamp >= self.opening_timestamp
        ):
            raise ValueError("previous observed opening must precede current opening")
        return self

    def _endpoint(self, endpoint: Literal["open", "close"]) -> MarketQuote:
        return MarketQuote(
            canonical_symbol=self.canonical_symbol,
            timestamp=self.closing_timestamp,
            bid=getattr(self, f"bid_{endpoint}"),
            ask=getattr(self, f"ask_{endpoint}"),
        )

    @property
    def spread_open(self) -> Decimal:
        return self._endpoint("open").spread

    @property
    def spread_close(self) -> Decimal:
        return self._endpoint("close").spread

    @property
    def mid_close(self) -> Decimal:
        return self._endpoint("close").mid

    @property
    def available_at(self) -> datetime:
        return self.closing_timestamp

    @property
    def elapsed_since_previous(self) -> timedelta | None:
        if self.previous_observed_timestamp is None:
            return None
        return self.opening_timestamp - self.previous_observed_timestamp

    @property
    def discontinuity(self) -> bool | None:
        elapsed = self.elapsed_since_previous
        return None if elapsed is None else elapsed != timedelta(minutes=5)

    def analytical_close(self, basis: AnalyticalPriceBasis) -> Decimal:
        basis = AnalyticalPriceBasis(basis)
        if basis == AnalyticalPriceBasis.BID:
            return self.bid_close
        if basis == AnalyticalPriceBasis.ASK:
            return self.ask_close
        return self.mid_close


def _bar(row: QuoteBar | BidAskBar) -> QuoteBar:
    return QuoteBar.model_validate(
        {name: getattr(row, name) for name in QuoteBar.model_fields}
    )


def completed_input(
    row: QuoteBar | BidAskBar,
    *,
    as_of: datetime,
    previous_observed_timestamp: datetime | None = None,
) -> ResearchFeatureInput:
    """Mathematical adapter only; does not confer research-policy approval."""
    cutoff = utc(as_of)
    bar = _bar(row)
    if bar.closing_timestamp > cutoff:
        raise ValueError("bar is not complete as of cutoff")
    return ResearchFeatureInput(
        **bar.model_dump(), previous_observed_timestamp=previous_observed_timestamp
    )


class ApprovedResearchInputs(DomainModel):
    dataset_key: str
    policy_version: str
    policy_key: str
    as_of: datetime
    inputs: tuple[ResearchFeatureInput, ...]

    @field_validator("as_of")
    @classmethod
    def cutoff_utc(cls, value: datetime) -> datetime:
        return utc(value)


def approved_research_inputs(
    dataset: QuoteDataset,
    rows: tuple[QuoteBar | BidAskBar, ...],
    policy: ProviderGapPolicy,
    *,
    as_of: datetime,
    day_type: DayType = DayType.NORMAL,
) -> ApprovedResearchInputs:
    """Offline approved-day gate followed by causal completed-bar conversion.

    Supply the full source day for policy evaluation. Eligibility is retrospective
    dataset selection, not information that was known live at each bar close.
    """
    cutoff = utc(as_of)
    if (
        dataset.gap_policy_version != policy.policy_version
        or dataset.gap_policy_key != policy.policy_key
    ):
        raise ValueError(
            "dataset must already be bound to the selected research policy"
        )
    for row in rows:
        if isinstance(row, BidAskBar) and (
            row.dataset_key != dataset.dataset_key
            or row.provider != dataset.provider
            or row.provider_symbol != dataset.provider_symbol
        ):
            raise ValueError("persisted row provenance differs from dataset")
    bars = tuple(_bar(row) for row in rows)
    if any(
        b.opening_timestamp <= a.opening_timestamp
        for a, b in zip(bars, bars[1:], strict=False)
    ):
        raise ValueError("observed bars must be strictly chronological")
    audit = evaluate_policy_day(
        dataset,
        bars,
        policy,
        raw_ticks=sum(b.tick_count for b in bars),
        invalid_ticks=0,
        day_type=day_type,
    )
    if not audit.eligibility.eligible:
        raise ValueError(f"research day rejected: {audit.eligibility.status.value}")
    inputs = []
    previous = None
    for bar in bars:
        if bar.closing_timestamp > cutoff:
            break
        item = completed_input(bar, as_of=cutoff, previous_observed_timestamp=previous)
        inputs.append(item)
        previous = bar.opening_timestamp
    return ApprovedResearchInputs(
        dataset_key=dataset.dataset_key,
        policy_version=policy.policy_version,
        policy_key=policy.policy_key,
        as_of=cutoff,
        inputs=tuple(inputs),
    )
