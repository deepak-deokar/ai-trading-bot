"""Versioned correction; all historical v1 measurements remain intact."""

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Literal, Self

from pydantic import model_validator

from trading_bot.data.research_input import ApprovedResearchInputs
from trading_bot.domain.models import DomainModel
from trading_bot.features.market_state import MarketStateRow, calculate_market_state
from trading_bot.features.market_taxonomy import EFF, VOL, WARMUP, range_state
from trading_bot.features.xauusd import Number

VERSION: Literal["xauusd-market-state-features-v2"] = "xauusd-market-state-features-v2"


class MarketStateV2Row(DomainModel):
    feature_set_version: Literal["xauusd-market-state-features-v2"] = VERSION
    baseline: MarketStateRow
    volatility_ratio_12_36: Number | None
    ratio_unavailable: Literal["WARMUP", "GAP_WARMUP", "ZERO_DENOMINATOR"] | None

    @property
    def available_at(self) -> datetime:
        return self.baseline.available_at

    def value(self, name: str) -> Decimal | None:
        if name == "volatility_ratio_12_36":
            return self.volatility_ratio_12_36
        return self.baseline.value(name)


def calculate_market_state_v2(
    batch: ApprovedResearchInputs,
) -> tuple[MarketStateV2Row, ...]:
    result = []
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
        for row in calculate_market_state(batch):
            short, long = row.value("mid_change_std_12"), row.value("mid_change_std_36")
            ratio = None
            reason: Literal["WARMUP", "GAP_WARMUP", "ZERO_DENOMINATOR"] | None = None
            if long is None or short is None:
                reason = next(
                    v.unavailable for v in row.values if v.name == "mid_change_std_36"
                )
            elif long == 0:
                reason = "ZERO_DENOMINATOR"
            else:
                ratio = short / long
            result.append(
                MarketStateV2Row(
                    baseline=row, volatility_ratio_12_36=ratio, ratio_unavailable=reason
                )
            )
    return tuple(result)


class MarketTaxonomyV2(DomainModel):
    taxonomy_version: Literal["xauusd-market-state-taxonomy-v2"] = (
        "xauusd-market-state-taxonomy-v2"
    )
    feature_set_version: Literal["xauusd-market-state-features-v2"] = VERSION
    volatility_low: Number
    volatility_high: Number
    efficiency_low: Number
    efficiency_high: Number
    range_reference: Literal[1] = 1
    range_feature: Literal["volatility_ratio_12_36"] = "volatility_ratio_12_36"
    development_hash: str
    methodology: Literal["pooled-nearest-rank-0.333333-0.666667-lower-inclusive"] = (
        "pooled-nearest-rank-0.333333-0.666667-lower-inclusive"
    )

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if not 0 <= self.volatility_low <= self.volatility_high:
            raise ValueError("invalid volatility thresholds")
        if not 0 <= self.efficiency_low <= self.efficiency_high <= 1:
            raise ValueError("invalid efficiency thresholds")
        return self

    def classify(self, row: MarketStateV2Row) -> tuple[str, str | None]:
        v, e = row.value("mid_change_std_36"), row.value("mid_efficiency_12")
        # The additional attribute cannot suppress an otherwise valid core state.
        if v is None or e is None:
            return WARMUP, None
        if v < 0 or not 0 <= e <= 1:
            raise ValueError("invalid core measurements")
        vi = 0 if v <= self.volatility_low else 1 if v <= self.volatility_high else 2
        ei = 0 if e <= self.efficiency_low else 1 if e <= self.efficiency_high else 2
        ratio = row.volatility_ratio_12_36
        return f"{VOL[vi]}_{EFF[ei]}", range_state(ratio) if ratio is not None else None
