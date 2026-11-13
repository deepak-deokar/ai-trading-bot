"""Causal structural breakout events; no orders, protective levels or risk logic."""

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Side
from trading_bot.features.xauusd import XAUUSDFeatureRow

VERSION: Literal["xauusd-structural-breakout-v1"] = "xauusd-structural-breakout-v1"


class BreakoutDecision(DomainModel):
    strategy_version: Literal["xauusd-structural-breakout-v1"] = VERSION
    side: Side | None
    reason: str
    opening_timestamp: datetime
    available_at: datetime
    dataset_key: str
    bid_reference: Decimal | None = None
    ask_reference: Decimal | None = None
    previous_bid_reference: Decimal | None = None
    previous_ask_reference: Decimal | None = None

    @property
    def action(self) -> str:
        return self.side.name if self.side is not None else "NO_TRADE"


def evaluate_breakout(
    current: XAUUSDFeatureRow,
    history: Sequence[XAUUSDFeatureRow],
    *,
    as_of: datetime,
) -> BreakoutDecision:
    """Two rolling 12-bar comparisons need 13 prior continuous completed bars."""
    current = XAUUSDFeatureRow.model_validate(current.model_dump())
    if utc(as_of) < current.available_at:
        raise ValueError("signal row is not yet complete")
    references: dict[str, Decimal] = {}

    def result(side: Side | None, reason: str) -> BreakoutDecision:
        return BreakoutDecision(
            side=side,
            reason=reason,
            opening_timestamp=current.opening_timestamp,
            available_at=current.available_at,
            dataset_key=current.dataset_key,
            **references,
        )

    if len(history) < 13:
        return result(None, "INSUFFICIENT_FRESHNESS_HISTORY")
    prior = tuple(
        XAUUSDFeatureRow.model_validate(r.model_dump()) for r in history[-13:]
    )
    chain = (*prior, current)
    if any(
        r.dataset_key != current.dataset_key or r.policy_key != current.policy_key
        for r in prior
    ) or any(
        b.sequence_reset is not None
        or b.opening_timestamp - a.opening_timestamp != timedelta(minutes=5)
        or a.available_at != b.opening_timestamp
        or b.input.previous_observed_timestamp != a.opening_timestamp
        for a, b in zip(chain, chain[1:], strict=False)
    ):
        return result(None, "DISCONTINUITY")
    values = {v.name: v for v in current.values}
    if len(values) != len(current.values):
        raise ValueError("duplicate feature names")
    required = ("spread_close", "relative_spread")
    if any(
        n not in values or values[n].value is None or values[n].unavailable is not None
        for n in required
    ):
        return result(None, "SPREAD_UNAVAILABLE")
    spread, relative = (values[n].value for n in required)
    assert spread is not None and relative is not None
    if spread < 0 or relative < 0:
        raise ValueError("negative spread feature")
    if spread > Decimal("0.75") or relative > Decimal("0.0003"):
        return result(None, "SPREAD_TOO_WIDE")
    references.update(
        bid_reference=max(r.input.bid_high for r in prior[1:]),
        ask_reference=min(r.input.ask_low for r in prior[1:]),
        previous_bid_reference=max(r.input.bid_high for r in prior[:-1]),
        previous_ask_reference=min(r.input.ask_low for r in prior[:-1]),
    )
    buy = (
        current.input.bid_close > references["bid_reference"]
        and prior[-1].input.bid_close <= references["previous_bid_reference"]
    )
    sell = (
        current.input.ask_close < references["ask_reference"]
        and prior[-1].input.ask_close >= references["previous_ask_reference"]
    )
    if buy and sell:
        raise ValueError("ambiguous simultaneous breakout directions")
    if buy:
        return result(Side.BUY, "FRESH_BID_BREAKOUT")
    if sell:
        return result(Side.SELL, "FRESH_ASK_BREAKOUT")
    return result(None, "NO_FRESH_BREAKOUT")
