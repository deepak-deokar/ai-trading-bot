"""Small Decimal baseline over approved bid/ask research inputs; no persistence."""

from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from typing import Annotated, Literal

from pydantic import Field

from trading_bot.data.research_input import ApprovedResearchInputs, ResearchFeatureInput
from trading_bot.domain.models import DomainModel
from trading_bot.features.definitions import FeatureError

VERSION: Literal["xauusd-baseline-features-v1"] = "xauusd-baseline-features-v1"
Number = Annotated[Decimal, Field(strict=True, allow_inf_nan=False)]


class FeatureValue(DomainModel):
    name: str
    value: Number | None
    unavailable: Literal["WARMUP", "GAP_WARMUP"] | None = None


class XAUUSDFeatureRow(DomainModel):
    feature_set_version: Literal["xauusd-baseline-features-v1"] = VERSION
    dataset_key: str
    policy_key: str
    input: ResearchFeatureInput
    sequence_reset: Literal["DATASET_BOUNDARY", "DISCONTINUITY"] | None
    values: tuple[FeatureValue, ...]

    @property
    def canonical_symbol(self) -> str:
        return self.input.canonical_symbol

    @property
    def opening_timestamp(self) -> datetime:
        return self.input.opening_timestamp

    @property
    def available_at(self) -> datetime:
        return self.input.available_at

    def value(self, name: str) -> Decimal | None:
        return next(v.value for v in self.values if v.name == name)


def calculate_xauusd(batch: ApprovedResearchInputs) -> tuple[XAUUSDFeatureRow, ...]:
    """Each call resets all state; consume only completed G2C3A typed inputs."""
    batch = ApprovedResearchInputs.model_validate(batch.model_dump())
    output: list[XAUUSDFeatureRow] = []
    closes: list[Decimal] = []
    ema: dict[int, Decimal] = {}
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    gain_average = loss_average = Decimal(0)
    previous: ResearchFeatureInput | None = None
    gap_warmup = False
    # Fixed local context, independent of caller precision/rounding settings.
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
        for item in batch.inputs:
            if item.available_at > batch.as_of:
                raise FeatureError("incomplete input at batch cutoff")
            reset: Literal["DATASET_BOUNDARY", "DISCONTINUITY"] | None = None
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
                if (
                    elapsed != timedelta(minutes=5)
                    or item.previous_observed_timestamp is None
                ):
                    reset = "DISCONTINUITY"
            if reset:
                closes, gains, losses, ema = [], [], [], {}
                gain_average = loss_average = Decimal(0)
                gap_warmup = reset == "DISCONTINUITY"
            close = item.mid_close
            values: dict[str, Decimal | None] = {
                "mid_close": close,
                "bid_range": item.bid_high - item.bid_low,
                "ask_range": item.ask_high - item.ask_low,
                "bid_body": item.bid_close - item.bid_open,
                "ask_body": item.ask_close - item.ask_open,
                "spread_open": item.spread_open,
                "spread_close": item.spread_close,
                "spread_change": item.spread_close - item.spread_open,
                "relative_spread": item.spread_close / close,
                "tick_count": Decimal(item.tick_count),
            }
            for period in (1, 3, 12):
                old = closes[-period] if len(closes) >= period else None
                values[f"return_{period}"] = (
                    close / old - 1 if old is not None else None
                )
                if period != 1:
                    values[f"momentum_{period}"] = (
                        close - old if old is not None else None
                    )
            if closes:
                change = close - closes[-1]
                gains.append(max(change, Decimal(0)))
                losses.append(max(-change, Decimal(0)))
            closes.append(close)
            for period in (12, 26):
                if len(closes) == period:
                    ema[period] = sum(closes, Decimal(0)) / period
                elif len(closes) > period:
                    alpha = Decimal(2) / (period + 1)
                    ema[period] = alpha * close + (1 - alpha) * ema[period]
                values[f"ema_{period}"] = ema.get(period)
            values["ema_difference"] = ema[12] - ema[26] if 26 in ema else None
            rsi = None
            if len(gains) >= 14:
                if len(gains) == 14:
                    gain_average = sum(gains, Decimal(0)) / 14
                    loss_average = sum(losses, Decimal(0)) / 14
                else:
                    gain_average = (13 * gain_average + gains[-1]) / 14
                    loss_average = (13 * loss_average + losses[-1]) / 14
                total = gain_average + loss_average
                rsi = 100 * gain_average / total if total else Decimal(50)
            values["rsi_14"] = rsi
            output.append(
                XAUUSDFeatureRow(
                    dataset_key=batch.dataset_key,
                    policy_key=batch.policy_key,
                    input=item,
                    sequence_reset=reset,
                    values=tuple(
                        FeatureValue(
                            name=name,
                            value=value,
                            unavailable=(
                                ("GAP_WARMUP" if gap_warmup else "WARMUP")
                                if value is None
                                else None
                            ),
                        )
                        for name, value in values.items()
                    ),
                )
            )
            previous = item
    return tuple(output)
