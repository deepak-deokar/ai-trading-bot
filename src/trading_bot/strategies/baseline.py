"""Fixed research baseline; no optimization or profitability assertion."""

import math
from datetime import time
from decimal import ROUND_HALF_UP, Decimal
from typing import Self
from zoneinfo import ZoneInfo

from pydantic import ConfigDict, Field, field_validator, model_validator

from trading_bot.backtesting.orders import OrderType, Side, TradeIntent
from trading_bot.domain.models import DomainModel
from trading_bot.strategies.contracts import (
    CancelIntent,
    StrategyContext,
    StrategyError,
    StrategyRequest,
)

REQUIRED = (
    "ema_10",
    "ema_20",
    "momentum_5",
    "rsi_14",
    "atr_14",
    "volume_ratio",
    "session_progress",
)
IST = ZoneInfo("Asia/Kolkata")


class BaselineParameters(DomainModel):
    model_config = ConfigDict(validate_default=True)

    quantity: int = Field(default=10, gt=0, le=1_000_000_000, strict=True)
    rsi_min: float = Field(default=55, ge=0, le=100)
    rsi_max: float = Field(default=70, ge=0, le=100)
    min_volume_ratio: float = Field(default=1.0, ge=0)
    entry_start_time: str = "09:30"
    last_entry_time: str = "14:45"
    stop_atr_multiple: Decimal = Field(default=Decimal("1.5"), gt=0)
    target_atr_multiple: Decimal = Field(default=Decimal("2.0"), gt=0)

    @field_validator("stop_atr_multiple", "target_atr_multiple")
    @classmethod
    def canonical_multiple(cls, value: Decimal) -> Decimal:
        return value.normalize()

    @field_validator("entry_start_time", "last_entry_time")
    @classmethod
    def local_time(cls, value: str) -> str:
        try:
            parsed = time.fromisoformat(value)
        except ValueError as error:
            raise ValueError("entry window must use HH:MM local time") from error
        if parsed.tzinfo or parsed.second or parsed.microsecond or len(value) != 5:
            raise ValueError("entry window must use HH:MM Asia/Kolkata")
        return parsed.strftime("%H:%M")

    @model_validator(mode="after")
    def bounds(self) -> Self:
        if self.rsi_min >= self.rsi_max:
            raise ValueError("rsi_min must be below rsi_max")
        if self.entry_start_time >= self.last_entry_time:
            raise ValueError("entry_start_time must precede last_entry_time")
        return self


class BaselineTrendMomentumStrategy:
    """One instance per symbol/run. Protection uses actual weighted fill basis."""

    display_name = "Baseline Trend Momentum"

    def __init__(self, parameters: BaselineParameters) -> None:
        self.parameters = parameters
        self.cycle = 0
        self.sequence = 0
        self.entry_reference: str | None = None
        self.entry_atr: Decimal | None = None
        self.entry_time: str | None = None
        self.protection: tuple[int, Decimal] | None = None
        self.armed = True

    def reference(self, context: StrategyContext, reason: str) -> str:
        self.sequence += 1
        return f"{context.bar.symbol}:{self.cycle}:{reason}:{self.sequence}"

    def cancel(
        self, context: StrategyContext, targets: tuple[str, ...], reason: str
    ) -> list[StrategyRequest]:
        if not targets:
            return []
        return [
            CancelIntent(
                reference=self.reference(context, "CANCEL"),
                symbol=context.bar.symbol,
                created_at=context.current_time,
                feature_timestamp=context.bar.timestamp,
                targets=targets,
                reason=reason,
            )
        ]

    def request(
        self,
        context: StrategyContext,
        reason: str,
        side: Side,
        quantity: int,
        **kwargs: object,
    ) -> TradeIntent:
        # model_validate keeps the single existing TradeIntent validation contract.
        return TradeIntent.model_validate(
            dict(
                reference=self.reference(context, reason),
                symbol=context.bar.symbol,
                side=side,
                quantity=quantity,
                created_at=context.current_time,
                feature_timestamp=context.bar.timestamp,
                **kwargs,
            )
        )

    def evaluate(self, context: StrategyContext) -> list[StrategyRequest]:
        context.validate()
        p = self.parameters
        values = {
            k: v
            for k, v in context.features.items()
            if v is not None and math.isfinite(v) and k not in context.unavailable
        }
        valid = all(k in values for k in REQUIRED)
        # Missing values stay missing; never substitute zero into a signal.
        signal = False
        if valid:
            signal = bool(
                values["ema_10"] > values["ema_20"]
                and values["momentum_5"] > 0
                and p.rsi_min <= values["rsi_14"] <= p.rsi_max
                and values["volume_ratio"] >= p.min_volume_ratio
                and values["atr_14"] > 0
                and 0 <= values["session_progress"] <= 1
            )
        if not signal:
            self.armed = True
        if context.current_time >= context.session_close:
            return []
        # Leave Phase 4's precommitted session liquidation in sole control.
        if (
            context.execution_cutoff is not None
            and context.current_time >= context.execution_cutoff
        ):
            return []
        active = [o for o in context.orders if o.active and not o.forced]
        buys = tuple(o.reference for o in active if o.side == Side.BUY)
        sells = tuple(o.reference for o in active if o.side == Side.SELL)
        if context.position_quantity:
            if self.entry_atr is None:
                raise StrategyError("baseline position lacks causal entry ATR")
            reversal = (
                values.get("ema_10") is not None
                and values.get("ema_20") is not None
                and values["ema_10"] <= values["ema_20"]
            )
            if any(":REVERSAL:" in r or ":STOP_REMAINDER:" in r for r in sells):
                return []
            if reversal:
                output = self.cancel(context, buys + sells, "TREND_REVERSAL")
                output.append(
                    self.request(
                        context,
                        "REVERSAL",
                        Side.SELL,
                        context.position_quantity,
                        metadata={"reason": "EMA10_LE_EMA20"},
                    )
                )
                return output
            # Once an exit has started, cancel remaining entry to avoid reopening.
            exited = any(
                o.side == Side.SELL
                and o.filled_quantity > 0
                and o.reference.startswith(f"{context.bar.symbol}:{self.cycle}:")
                for o in context.orders
            )
            output = self.cancel(context, buys if exited else (), "EXIT_STARTED")
            triggered_stop = next(
                (
                    o
                    for o in active
                    if ":STOP:" in o.reference and o.filled_quantity > 0
                ),
                None,
            )
            if triggered_stop is not None:
                if triggered_stop.remaining == context.position_quantity:
                    return output  # Preserve Phase 4's persistent stop trigger.
                output += self.cancel(context, sells, "STOP_REMAINDER")
                output.append(
                    self.request(
                        context,
                        "STOP_REMAINDER",
                        Side.SELL,
                        context.position_quantity,
                        metadata={"reason": "TRIGGERED_STOP_REMAINDER"},
                    )
                )
                return output
            basis = (context.position_quantity, context.average_entry_price)
            if self.protection == basis and len(sells) == 2:
                return output
            output += self.cancel(context, sells, "REPLACE_PROTECTION")
            stop = context.average_entry_price - self.entry_atr * p.stop_atr_multiple
            target = (
                context.average_entry_price + self.entry_atr * p.target_atr_multiple
            )
            # Match domain decimal precision, not an exchange tick-size assumption.
            stop = stop.quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP)
            target = target.quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP)
            if stop <= 0:
                raise StrategyError("ATR protection implies nonpositive stop")
            group = self.reference(context, "OCO")
            metadata = {
                "entry_reference": str(self.entry_reference),
                "signal_time": str(self.entry_time),
                "entry_atr": str(self.entry_atr),
                "fill_basis": str(context.average_entry_price),
                "stop": str(stop),
                "target": str(target),
            }
            output += [
                self.request(
                    context,
                    "STOP",
                    Side.SELL,
                    basis[0],
                    order_type=OrderType.STOP_MARKET,
                    trigger_price=stop,
                    oco_group=group,
                    metadata={**metadata, "reason": "ATR_STOP"},
                ),
                self.request(
                    context,
                    "TARGET",
                    Side.SELL,
                    basis[0],
                    order_type=OrderType.LIMIT,
                    limit_price=target,
                    oco_group=group,
                    metadata={**metadata, "reason": "ATR_TARGET"},
                ),
            ]
            self.protection = basis
            return output
        # A terminal entry/exit lifecycle cannot leave stale protective orders.
        if self.entry_reference is not None:
            entry_order = next(
                (o for o in context.orders if o.reference == self.entry_reference), None
            )
            exited = any(
                o.side == Side.SELL
                and o.filled_quantity > 0
                and o.reference.startswith(f"{context.bar.symbol}:{self.cycle}:")
                for o in context.orders
            )
            if exited:
                output = self.cancel(context, buys + sells, "POSITION_FLAT")
            elif buys:
                return []
            else:
                output = self.cancel(context, sells, "POSITION_FLAT")
            if entry_order is None:
                return []  # Pending request not yet observed as an order.
            self.entry_reference = None
            self.entry_atr = None
            self.protection = None
            return output  # Never exit and re-enter in one evaluation.
        if buys or sells:
            return []
        local_time = context.current_time.astimezone(IST).time()
        if not (
            signal
            and self.armed
            and time.fromisoformat(p.entry_start_time)
            <= local_time
            <= time.fromisoformat(p.last_entry_time)
        ):
            return []
        self.cycle += 1
        self.armed = False
        self.entry_atr = Decimal(str(values["atr_14"]))
        self.entry_time = context.current_time.isoformat()
        entry = self.request(
            context,
            "ENTRY",
            Side.BUY,
            p.quantity,
            required_features=REQUIRED,
            metadata={
                "reason": "TREND_MOMENTUM_ENTRY",
                **{k: str(values[k]) for k in REQUIRED},
            },
        )
        self.entry_reference = entry.reference
        return [entry]
