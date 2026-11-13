"""Causal continuous research measurements; no execution or regime decisions."""

from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Literal

from trading_bot.data.research_input import ApprovedResearchInputs, ResearchFeatureInput
from trading_bot.domain.models import DomainModel
from trading_bot.features.definitions import FeatureError
from trading_bot.features.xauusd import FeatureValue

VERSION: Literal["xauusd-market-state-features-v1"] = "xauusd-market-state-features-v1"


class MarketStateRow(DomainModel):
    feature_set_version: Literal["xauusd-market-state-features-v1"] = VERSION
    dataset_key: str
    policy_key: str
    input: ResearchFeatureInput
    sequence_reset: Literal["DATASET_BOUNDARY", "DISCONTINUITY", "SOURCE_DAY"] | None
    values: tuple[FeatureValue, ...]

    @property
    def available_at(self) -> datetime:
        return self.input.available_at

    def value(self, name: str) -> Decimal | None:
        return next(v.value for v in self.values if v.name == name)


def calculate_market_state(batch: ApprovedResearchInputs) -> tuple[MarketStateRow, ...]:
    """Fixed 50-digit arithmetic; source-day boundary is HistData fixed UTC-05."""
    batch = ApprovedResearchInputs.model_validate(batch.model_dump())
    output: list[MarketStateRow] = []
    history: list[ResearchFeatureInput] = []
    ranges: dict[str, list[Decimal]] = {"bid": [], "ask": []}
    changes: list[Decimal] = []
    previous: ResearchFeatureInput | None = None
    gap = False
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
        for item in batch.inputs:
            if item.available_at > batch.as_of:
                raise FeatureError("incomplete input at batch cutoff")
            reset: Literal["DATASET_BOUNDARY", "DISCONTINUITY", "SOURCE_DAY"] | None = (
                None
            )
            if previous is None:
                reset = "DATASET_BOUNDARY"
            else:
                elapsed = item.opening_timestamp - previous.opening_timestamp
                if elapsed <= timedelta(0):
                    raise FeatureError("inputs must be strictly chronological")
                if item.previous_observed_timestamp not in (
                    None,
                    previous.opening_timestamp,
                ):
                    raise FeatureError("inconsistent predecessor metadata")
                if (item.opening_timestamp - timedelta(hours=5)).date() != (
                    previous.opening_timestamp - timedelta(hours=5)
                ).date():
                    reset = "SOURCE_DAY"
                elif (
                    elapsed != timedelta(minutes=5)
                    or item.previous_observed_timestamp is None
                ):
                    reset = "DISCONTINUITY"
            if reset:
                history, changes = [], []
                ranges = {"bid": [], "ask": []}
                gap = reset == "DISCONTINUITY"
            values: dict[str, Decimal | None] = {}
            if history:
                changes.append(item.mid_close - history[-1].mid_close)
            for side in ("bid", "ask"):
                high, low = getattr(item, f"{side}_high"), getattr(item, f"{side}_low")
                tr = None
                if history:
                    close = getattr(history[-1], f"{side}_close")
                    tr = max(high - low, abs(high - close), abs(low - close))
                    ranges[side].append(tr)
                values[f"{side}_true_range"] = tr
                values[f"{side}_atr_14"] = (
                    sum(ranges[side][-14:], Decimal(0)) / 14
                    if len(ranges[side]) >= 14
                    else None
                )
            history.append(item)
            for side in ("bid", "ask"):
                for n in (12, 36):
                    values[f"{side}_range_{n}"] = (
                        max(getattr(b, f"{side}_high") for b in history[-n:])
                        - min(getattr(b, f"{side}_low") for b in history[-n:])
                        if len(history) >= n
                        else None
                    )
                short, long = values[f"{side}_range_12"], values[f"{side}_range_36"]
                # Flat longer window has zero compression by explicit convention.
                values[f"{side}_range_ratio_12_36"] = (
                    (short / long if long else Decimal(0))
                    if short is not None and long is not None
                    else None
                )
            for n in (12, 36):
                volatility = None
                if len(changes) >= n:
                    window = changes[-n:]
                    mean = sum(window, Decimal(0)) / n
                    volatility = (
                        sum(((d - mean) ** 2 for d in window), Decimal(0)) / n
                    ).sqrt()
                values[f"mid_change_std_{n}"] = volatility
            efficiency = None
            if len(changes) >= 12:
                path = sum((abs(d) for d in changes[-12:]), Decimal(0))
                efficiency = (
                    abs(sum(changes[-12:], Decimal(0))) / path if path else Decimal(0)
                )
            values["mid_efficiency_12"] = efficiency
            output.append(
                MarketStateRow(
                    dataset_key=batch.dataset_key,
                    policy_key=batch.policy_key,
                    input=item,
                    sequence_reset=reset,
                    values=tuple(
                        FeatureValue(
                            name=k,
                            value=v,
                            unavailable=(
                                ("GAP_WARMUP" if gap else "WARMUP")
                                if v is None
                                else None
                            ),
                        )
                        for k, v in values.items()
                    ),
                )
            )
            history = history[-36:]
            changes = changes[-36:]
            ranges = {side: seq[-14:] for side, seq in ranges.items()}
            previous = item
    return tuple(output)
