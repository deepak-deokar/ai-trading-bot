"""Frozen descriptive taxonomy, independent of strategies and trading outcomes."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Literal, Self

from pydantic import model_validator

from trading_bot.domain.models import DomainModel
from trading_bot.features.market_state import VERSION, MarketStateRow
from trading_bot.features.xauusd import Number

VOL = ("LOW_VOL", "NORMAL_VOL", "HIGH_VOL")
EFF = ("CHOPPY", "MIXED", "DIRECTIONAL")
STATES = tuple(f"{v}_{e}" for v in VOL for e in EFF)
WARMUP = "UNCLASSIFIED_WARMUP"


def quantile(values: tuple[Decimal, ...], probability: Decimal) -> Decimal:
    """Nearest rank; exact decimal probabilities, no interpolation."""
    if not values or not Decimal(0) < probability <= Decimal(1):
        raise ValueError("nonempty sample and probability in (0,1] required")
    if any(not isinstance(v, Decimal) or not v.is_finite() for v in values):
        raise ValueError("finite Decimal sample required")
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
        rank = int(
            (probability * len(values)).to_integral_value(rounding=ROUND_CEILING)
        )
    return sorted(values)[rank - 1]


class MarketTaxonomy(DomainModel):
    taxonomy_version: Literal["xauusd-market-state-taxonomy-v1"] = (
        "xauusd-market-state-taxonomy-v1"
    )
    feature_set_version: Literal["xauusd-market-state-features-v1"] = VERSION
    volatility_low: Number
    volatility_high: Number
    efficiency_low: Number
    efficiency_high: Number
    range_reference: Literal[1] = 1
    range_feature: Literal["bid_range_ratio_12_36"] = "bid_range_ratio_12_36"
    development_hash: str
    methodology: Literal["pooled-nearest-rank-0.333333-0.666667-lower-inclusive"] = (
        "pooled-nearest-rank-0.333333-0.666667-lower-inclusive"
    )

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if not 0 <= self.volatility_low <= self.volatility_high:
            raise ValueError("volatility thresholds must be ordered nonnegative")
        if not 0 <= self.efficiency_low <= self.efficiency_high <= 1:
            raise ValueError("efficiency thresholds must be ordered in [0,1]")
        return self

    def classify(self, row: MarketStateRow) -> tuple[str, str | None]:
        v, e, r = (
            row.value(n)
            for n in ("mid_change_std_36", "mid_efficiency_12", self.range_feature)
        )
        if v is None or e is None or r is None:
            return WARMUP, None
        if v < 0 or not 0 <= e <= 1 or r < 0:
            raise ValueError("invalid market-state measurements")
        vi = 0 if v <= self.volatility_low else 1 if v <= self.volatility_high else 2
        ei = 0 if e <= self.efficiency_low else 1 if e <= self.efficiency_high else 2
        return f"{VOL[vi]}_{EFF[ei]}", range_state(r)


def range_state(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError("nonnegative finite Decimal ratio required")
    return "COMPRESSED" if value < 1 else "NEUTRAL" if value == 1 else "EXPANDED"


@dataclass(frozen=True)
class StateObservation:
    dataset_key: str
    opening: datetime
    state: str
    reset: bool = False


def temporal_summary(
    rows: tuple[StateObservation, ...],
) -> tuple[dict[str, list[int]], dict[str, dict[str, int]]]:
    """Run lengths and adjacent transitions, including self-transitions."""
    runs: dict[str, list[int]] = {s: [] for s in STATES}
    transitions = {s: dict.fromkeys(STATES, 0) for s in STATES}
    previous: StateObservation | None = None
    run_state: str | None = None
    length = 0
    for row in rows:
        if row.opening.tzinfo is None or row.opening.utcoffset() != timedelta(0):
            raise ValueError("UTC observations required")
        if row.state not in (*STATES, WARMUP):
            raise ValueError("unknown taxonomy state")
        adjacent = (
            previous is not None
            and not row.reset
            and row.dataset_key == previous.dataset_key
            and row.opening - previous.opening == timedelta(minutes=5)
            and (row.opening - timedelta(hours=5)).date()
            == (previous.opening - timedelta(hours=5)).date()
            and previous.state != WARMUP
            and row.state != WARMUP
        )
        if adjacent and previous is not None:
            transitions[previous.state][row.state] += 1
        if run_state is not None and (not adjacent or row.state != run_state):
            runs[run_state].append(length)
            run_state, length = None, 0
        if row.state != WARMUP:
            run_state = row.state
            length += 1
        previous = row
    if run_state is not None:
        runs[run_state].append(length)
    return runs, transitions
