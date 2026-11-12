"""Frozen pullback/resumption signal hypothesis; no execution or risk logic."""

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Side
from trading_bot.features.xauusd import FeatureValue, XAUUSDFeatureRow

VERSION: Literal["xauusd-pullback-resumption-v1"] = "xauusd-pullback-resumption-v1"
REQUIRED = (
    "ema_12",
    "ema_26",
    "momentum_3",
    "momentum_12",
    "spread_close",
    "relative_spread",
)


class PullbackDecision(DomainModel):
    strategy_version: Literal["xauusd-pullback-resumption-v1"] = VERSION
    side: Side | None
    reason: str
    opening_timestamp: datetime
    available_at: datetime
    dataset_key: str
    current_row_hash: str
    previous_row_hash: str | None
    current_snapshot: tuple[FeatureValue, ...]
    previous_momentum: FeatureValue | None

    @property
    def action(self) -> str:
        return self.side.name if self.side is not None else "NO_TRADE"


def _hash(row: XAUUSDFeatureRow) -> str:
    return hashlib.sha256(
        json.dumps(
            row.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def _values(row: XAUUSDFeatureRow) -> dict[str, FeatureValue]:
    values = {v.name: v for v in row.values}
    if len(values) != len(row.values):
        raise ValueError("duplicate feature names")
    return values


def evaluate_pullback(
    current: XAUUSDFeatureRow,
    previous: XAUUSDFeatureRow | None,
    *,
    as_of: datetime,
) -> PullbackDecision:
    """Read exactly two completed rows; reset/key/predecessor guards prevent gaps."""
    current = XAUUSDFeatureRow.model_validate(current.model_dump())
    if utc(as_of) < current.available_at:
        raise ValueError("current feature row is not yet available")
    if previous is not None:
        previous = XAUUSDFeatureRow.model_validate(previous.model_dump())
    values = _values(current)
    prior = _values(previous).get("momentum_3") if previous is not None else None

    def result(side: Side | None, reason: str) -> PullbackDecision:
        return PullbackDecision(
            side=side,
            reason=reason,
            opening_timestamp=current.opening_timestamp,
            available_at=current.available_at,
            dataset_key=current.dataset_key,
            current_row_hash=_hash(current),
            previous_row_hash=_hash(previous) if previous else None,
            current_snapshot=tuple(values[n] for n in REQUIRED if n in values),
            previous_momentum=prior,
        )

    if previous is None:
        return result(None, "MISSING_PREVIOUS_ROW")
    if (
        previous.dataset_key != current.dataset_key
        or previous.policy_key != current.policy_key
        or current.sequence_reset is not None
        or current.opening_timestamp - previous.opening_timestamp
        != timedelta(minutes=5)
        or previous.available_at != current.opening_timestamp
        or current.input.previous_observed_timestamp != previous.opening_timestamp
    ):
        return result(None, "DISCONTINUITY")
    if (
        prior is None
        or prior.value is None
        or prior.unavailable is not None
        or any(
            n not in values
            or values[n].value is None
            or values[n].unavailable is not None
            for n in REQUIRED
        )
    ):
        return result(None, "FEATURES_UNAVAILABLE")
    fast, slow, short, long, spread, relative = (values[n].value for n in REQUIRED)
    assert fast is not None and slow is not None and short is not None
    assert long is not None and spread is not None and relative is not None
    if spread < 0 or relative < 0:
        raise ValueError("negative spread feature")
    if spread > Decimal("0.75") or relative > Decimal("0.0003"):
        return result(None, "SPREAD_TOO_WIDE")
    if fast > slow and long > 0 and prior.value <= 0 and short > 0:
        return result(Side.BUY, "BUY_PULLBACK_RESUMPTION")
    if fast < slow and long < 0 and prior.value >= 0 and short < 0:
        return result(Side.SELL, "SELL_PULLBACK_RESUMPTION")
    return result(None, "NO_RESUMPTION")
