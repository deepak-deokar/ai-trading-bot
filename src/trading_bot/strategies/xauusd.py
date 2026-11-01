"""Fixed transparent signal-only baseline. No orders, positions or execution."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import field_validator

from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Side
from trading_bot.features.xauusd import FeatureValue, XAUUSDFeatureRow

VERSION = "xauusd-trend-momentum-v1"
REQUIRED = (
    "ema_12",
    "ema_26",
    "ema_difference",
    "momentum_3",
    "rsi_14",
    "spread_close",
    "relative_spread",
)


class XAUUSDSignalDecision(DomainModel):
    strategy_version: Literal["xauusd-trend-momentum-v1"] = "xauusd-trend-momentum-v1"
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


def evaluate_xauusd(row: XAUUSDFeatureRow, *, as_of: datetime) -> XAUUSDSignalDecision:
    """Evaluate one verified completed row; no access to past/future collections."""
    row = XAUUSDFeatureRow.model_validate(row.model_dump())
    if utc(as_of) < row.available_at:
        raise ValueError("feature row is not yet available")
    features = {v.name: v for v in row.values}
    if len(features) != len(row.values):
        raise ValueError("duplicate feature names")
    snapshot = tuple(features[n] for n in REQUIRED if n in features)

    def decision(side: Side | None, *reasons: str) -> XAUUSDSignalDecision:
        return XAUUSDSignalDecision(
            opening_timestamp=row.opening_timestamp,
            available_at=row.available_at,
            side=side,
            reasons=tuple(reasons),
            feature_snapshot=snapshot,
            source_dataset_key=row.dataset_key,
            source_feature_version=row.feature_set_version,
            source_feature_row_hash=hashlib.sha256(
                json.dumps(
                    row.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
        )

    if any(
        n not in features
        or features[n].value is None
        or features[n].unavailable is not None
        for n in REQUIRED
    ):
        return decision(None, "WARMUP_INCOMPLETE")
    values = {n: features[n].value for n in REQUIRED}
    fast, slow, difference, momentum, rsi, spread, relative = (
        values[n] for n in REQUIRED
    )
    assert fast is not None and slow is not None and difference is not None
    assert (
        momentum is not None
        and rsi is not None
        and spread is not None
        and relative is not None
    )
    if not Decimal(0) <= rsi <= Decimal(100) or spread < 0 or relative < 0:
        raise ValueError("invalid RSI or spread feature")
    if spread > Decimal("0.75") or relative > Decimal("0.0003"):
        return decision(None, "SPREAD_TOO_WIDE")
    bullish = fast > slow and difference > 0
    bearish = fast < slow and difference < 0
    if not bullish and not bearish:
        return decision(None, "NO_SETUP")
    trend = "TREND_BULLISH" if bullish else "TREND_BEARISH"
    if (bullish and momentum <= 0) or (bearish and momentum >= 0):
        return decision(None, trend, "SIGNALS_CONFLICT")
    if (bullish and rsi > 70) or (bearish and rsi < 30):
        return decision(None, trend, "MOMENTUM_CONFIRMATION", "RSI_TOO_EXTENDED")
    if (bullish and rsi < 55) or (bearish and rsi > 45):
        return decision(None, trend, "MOMENTUM_CONFIRMATION", "RSI_NO_CONFIRMATION")
    return decision(
        Side.BUY if bullish else Side.SELL,
        trend,
        "MOMENTUM_CONFIRMATION",
        "RSI_CONFIRMATION",
        "BUY_SETUP" if bullish else "SELL_SETUP",
    )
