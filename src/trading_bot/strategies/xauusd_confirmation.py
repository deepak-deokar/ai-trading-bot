"""Fixed transparent signal-only baseline. No orders, positions or execution."""

from datetime import datetime
from typing import Literal

from pydantic import field_validator

from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Side
from trading_bot.features.xauusd import FeatureValue, XAUUSDFeatureRow
from trading_bot.strategies.xauusd import evaluate_xauusd

VERSION = "xauusd-trend-momentum-v2-long-confirmation"


class MomentumConfirmationDecision(DomainModel):
    strategy_version: Literal["xauusd-trend-momentum-v2-long-confirmation"] = (
        "xauusd-trend-momentum-v2-long-confirmation"
    )
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    opening_timestamp: datetime
    available_at: datetime
    side: Side | None
    reasons: tuple[str, ...]
    feature_snapshot: tuple[FeatureValue, ...]
    source_dataset_key: str
    source_feature_version: str
    source_feature_row_hash: str

    @field_validator("opening_timestamp", "available_at")
    @classmethod
    def timestamps(cls, value: datetime) -> datetime:
        return utc(value)

    @property
    def action(self) -> str:
        return self.side.name if self.side is not None else "NO_TRADE"


def evaluate_confirmation(
    row: XAUUSDFeatureRow, *, as_of: datetime
) -> MomentumConfirmationDecision:
    """V1 plus sign-only momentum_12 confirmation from the same causal row."""
    baseline = evaluate_xauusd(row, as_of=as_of)
    momentum = next((v for v in row.values if v.name == "momentum_12"), None)
    values = baseline.model_dump() | {"strategy_version": VERSION}
    if momentum is not None:
        values["feature_snapshot"] = (*baseline.feature_snapshot, momentum)
    if baseline.side is not None:
        if (
            momentum is None
            or momentum.value is None
            or momentum.unavailable is not None
        ):
            values.update(
                side=None, reasons=(*baseline.reasons, "MOMENTUM_12_UNAVAILABLE")
            )
        elif (baseline.side == Side.BUY and momentum.value <= 0) or (
            baseline.side == Side.SELL and momentum.value >= 0
        ):
            values.update(
                side=None, reasons=(*baseline.reasons, "MOMENTUM_12_NOT_CONFIRMED")
            )
        else:
            values["reasons"] = (*baseline.reasons, "MOMENTUM_12_CONFIRMED")
    return MomentumConfirmationDecision.model_validate(values)
