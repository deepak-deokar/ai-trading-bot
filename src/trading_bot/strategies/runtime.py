"""Per-run callbacks receive detached observations, never the simulator itself."""

from collections.abc import Sequence
from types import MappingProxyType

from pydantic import ValidationError

from trading_bot.backtesting.orders import TradeIntent
from trading_bot.strategies.contracts import (
    CancelIntent,
    IntentValidationError,
    StrategyContext,
    StrategyError,
    StrategyRequest,
)
from trading_bot.strategies.registry import StrategyPlan


class StrategyRuntime:
    def __init__(self, plan: StrategyPlan, symbols: tuple[str, ...]) -> None:
        self.plan = plan
        self.instances = {symbol: plan.create() for symbol in sorted(symbols)}
        if len({id(s) for s in self.instances.values()}) != len(self.instances):
            raise StrategyError("strategy factory must create isolated instances")
        self.references: set[str] = set()
        self.parameters = MappingProxyType(dict(plan.manifest()["parameters"]))

    def evaluate(self, context: StrategyContext) -> tuple[StrategyRequest, ...]:
        context.validate()
        output = self.instances[context.bar.symbol].evaluate(context)
        if not isinstance(output, Sequence) or isinstance(output, str | bytes):
            raise IntentValidationError("strategy must return an intent sequence")
        if len(output) > 10000 or len(output) + len(self.references) > 10000:
            raise IntentValidationError("strategy intent limit exceeded")
        result: list[StrategyRequest] = []
        references = set(self.references)
        for raw in output:
            try:
                if not isinstance(raw, TradeIntent | CancelIntent):
                    raise IntentValidationError("strategy returned a non-intent")
                # Revalidate even model_construct/model_copy values before execution.
                intent = type(raw).model_validate(raw.model_dump(warnings=False))
            except ValidationError as error:
                raise IntentValidationError("malformed strategy intent") from error
            if (
                intent.symbol != context.bar.symbol
                or intent.created_at != context.current_time
                or intent.feature_timestamp != context.bar.timestamp
                or intent.reference in references
                or context.current_time >= context.session_close
            ):
                raise IntentValidationError(
                    "intent symbol/time/reference violates context"
                )
            if isinstance(intent, CancelIntent):
                known = {o.reference for o in context.orders if not o.forced}
                if not set(intent.targets) <= known:
                    raise IntentValidationError(
                        "cancellation targets unknown symbol orders"
                    )
            if isinstance(intent, TradeIntent) and any(
                context.features.get(f) is None for f in intent.required_features
            ):
                raise IntentValidationError("intent requires unavailable feature")
            references.add(intent.reference)
            result.append(intent)
        self.references = references
        return tuple(result)
