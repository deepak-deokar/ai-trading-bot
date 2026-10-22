from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from trading_bot.backtesting.costs import ZeroCostModel
from trading_bot.backtesting.decisions import ScriptedDecisionSource
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.backtesting.orders import TradeIntent
from trading_bot.backtesting.slippage import ZeroSlippageModel
from trading_bot.data.calendar import NSECalendar
from trading_bot.domain.models import DomainModel
from trading_bot.strategies.contracts import (
    IntentValidationError,
    Strategy,
    StrategyError,
)
from trading_bot.strategies.registry import (
    Definition,
    NoOpParameters,
    NoOpStrategy,
    StrategyConfig,
    StrategyRegistry,
    builtin_registry,
)


def plan(factory, params=None, config=None):
    registry = StrategyRegistry()
    registry.register(
        Definition("test_only", "1", "test-only-v1", params or NoOpParameters, factory)
    )
    return registry.resolve(config or StrategyConfig(name="test_only", version="1"))


def run(config, inputs, strategy):
    return BacktestEngine(NSECalendar(), ZeroCostModel(), ZeroSlippageModel()).run(
        uuid4(), inputs, config, ScriptedDecisionSource(), strategy
    )


def test_noop_protocol_pipeline_and_repeat(backtest_inputs):
    config, inputs = backtest_inputs()
    strategy = builtin_registry().resolve(StrategyConfig(name="noop", version="1"))
    assert isinstance(strategy.create(), Strategy)
    first = run(config, inputs, strategy)
    second = run(config, inputs, strategy)
    assert first.deterministic_payload() == second.deterministic_payload()
    assert first.run_id != second.run_id
    assert not first.orders and not first.fills and not first.trades
    assert first.metrics["ending_equity"] == config.starting_capital
    assert first.manifest["strategy"] == strategy.manifest()
    events = [e for e in first.events if e.kind == "STRATEGY"]
    assert len(events) == 75
    assert all(e.details["intent_count"] == 0 for e in events)
    assert events[0].timestamp == config.history.start + timedelta(minutes=5)


@pytest.mark.parametrize("name,version", [("missing", "1"), ("noop", "2")])
def test_unknown_registry(name, version):
    with pytest.raises(StrategyError, match="unknown"):
        builtin_registry().resolve(StrategyConfig(name=name, version=version))


def test_registry_invalid_parameters_and_duplicate():
    with pytest.raises(StrategyError, match="parameters"):
        builtin_registry().resolve(
            StrategyConfig(name="noop", version="1", parameters={"period": 5})
        )
    registry = builtin_registry()
    with pytest.raises(StrategyError, match="registered"):
        registry.register(
            Definition("noop", "1", "noop-v1", NoOpParameters, lambda _: NoOpStrategy())
        )
    with pytest.raises(ValidationError):
        StrategyConfig(name="arbitrary.module:execute", version="1")
    with pytest.raises(ValidationError):
        StrategyConfig(name="noop", version="1", extra="bad")


def test_identity_parameters_version_implementation_and_defensive_snapshot():
    class Parameters(DomainModel):
        count: int = 1
        label: str = "test"

    cfg = StrategyConfig(
        name="test_only", version="1", parameters={"count": 2, "label": "test"}
    )
    a = plan(lambda _: NoOpStrategy(), Parameters, cfg)
    b = plan(
        lambda _: NoOpStrategy(),
        Parameters,
        cfg.model_copy(update={"parameters": {"label": "test", "count": 2}}),
    )
    assert a.manifest() == b.manifest()
    cfg.parameters["count"] = 3
    c = plan(lambda _: NoOpStrategy(), Parameters, cfg)
    assert a.manifest()["identity"] != c.manifest()["identity"]
    assert a.manifest()["parameters"]["count"] == 2
    for field in ("version", "implementation"):
        definition = replace(a.definition, **{field: "2"})
        registry = StrategyRegistry()
        registry.register(definition)
        changed = registry.resolve(
            StrategyConfig(
                name="test_only",
                version=definition.version,
                parameters={"count": 2, "label": "test"},
            )
        )
        assert a.manifest()["identity"] != changed.manifest()["identity"]


def test_context_is_detached_current_only_and_immutable(backtest_inputs):
    config, inputs = backtest_inputs()
    observations = []

    class Inspect:
        def evaluate(self, context):
            context.validate()
            assert context.current_time >= context.available_at
            assert context.bar.timestamp < context.current_time
            assert not hasattr(context, "database")
            assert not hasattr(context, "history")
            assert not hasattr(context, "portfolio")
            with pytest.raises(TypeError):
                context.features["injected"] = 123
            with pytest.raises(TypeError):
                context.parameters["injected"] = 123
            with pytest.raises(ValidationError):
                context.bar.close = Decimal(999)
            observations.append(context)
            return []

    run(config, inputs, plan(lambda _: Inspect()))
    assert len(observations) == 75
    assert observations[0].bar == inputs.snapshot.bars[0].bar
    assert observations[0].bar is not inputs.snapshot.bars[0].bar
    assert dict(observations[0].features) == inputs.features[0].values
    with pytest.raises(StrategyError):
        replace(observations[0], current_time=config.history.start).validate()


def test_future_features_and_candles_cannot_change_earlier_output(backtest_inputs):
    config, inputs = backtest_inputs()
    observed = []

    class Probe:
        def evaluate(self, context):
            observed.append((context.current_time, context.bar, dict(context.features)))
            if context.bar.timestamp == config.history.start:
                return [intent(context)]
            return []

    strategy = plan(lambda _: Probe())
    first = run(config, inputs, strategy)
    before = observed[:20]
    bars = list(inputs.snapshot.bars)
    rows = list(inputs.features)
    for index in range(20, 75):
        bars[index] = replace(
            bars[index],
            bar=bars[index].bar.model_copy(
                update={
                    "open": Decimal(200),
                    "high": Decimal(200),
                    "low": Decimal(200),
                    "close": Decimal(200),
                }
            ),
        )
        rows[index] = rows[index].model_copy(update={"values": {"future": 999.0}})
    changed = replace(
        inputs,
        snapshot=replace(inputs.snapshot, bars=tuple(bars)),
        features=tuple(rows),
    )
    observed.clear()
    second = run(config, changed, strategy)
    assert before == observed[:20]
    cutoff = bars[20].bar.timestamp
    assert [e for e in first.events if e.timestamp < cutoff] == [
        e for e in second.events if e.timestamp < cutoff
    ]
    assert first.orders[0] == second.orders[0]
    assert first.fills[0] == second.fills[0]
    assert first.fills[0].bar_open > first.orders[0].intent.created_at


def intent(context):
    return TradeIntent(
        reference="test-buy",
        symbol=context.bar.symbol,
        side="BUY",
        quantity=1,
        created_at=context.current_time,
        feature_timestamp=context.bar.timestamp,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": 0},
        {"quantity": -1},
        {"quantity": 1.5},
        {"order_type": "BAD"},
        {"side": "BAD"},
        {"symbol": "bad symbol"},
        {"symbol": "TCS"},
        {"order_type": "LIMIT"},
        {"order_type": "STOP_MARKET"},
        {"required_features": ("missing",)},
        {"reference": ""},
        {"created_at": "future"},
        {"created_at": "past"},
        {"feature_timestamp": "future"},
    ],
)
def test_intent_boundary_rejects_malformed_or_unavailable(backtest_inputs, changes):
    config, inputs = backtest_inputs()

    class Invalid:
        def evaluate(self, context):
            altered = dict(changes)
            for key in ("created_at", "feature_timestamp"):
                if altered.get(key) in ("future", "past"):
                    altered[key] = context.current_time + timedelta(
                        minutes=1 if altered[key] == "future" else -1
                    )
            return [intent(context).model_copy(update=altered)]

    with pytest.raises(IntentValidationError):
        run(config, inputs, plan(lambda _: Invalid()))


def test_unavailable_feature_row_fails_before_callback(backtest_inputs):
    config, inputs = backtest_inputs()
    rows = list(inputs.features)
    rows[0] = rows[0].model_copy(
        update={"available_at": rows[0].available_at + timedelta(minutes=5)}
    )
    with pytest.raises(StrategyError, match="not available"):
        run(
            config,
            replace(inputs, features=tuple(rows)),
            builtin_registry().resolve(StrategyConfig(name="noop", version="1")),
        )


def test_per_symbol_and_per_run_state_isolated(backtest_inputs):
    config, inputs = backtest_inputs()
    config = config.model_copy(
        update={
            "history": config.history.model_copy(
                update={"symbols": ("RELIANCE", "TCS")}
            )
        }
    )
    extra_bars = tuple(
        replace(b, bar=b.bar.model_copy(update={"symbol": "TCS"}))
        for b in inputs.snapshot.bars
    )
    extra_rows = tuple(r.model_copy(update={"symbol": "TCS"}) for r in inputs.features)
    inputs = replace(
        inputs,
        snapshot=replace(inputs.snapshot, bars=inputs.snapshot.bars + extra_bars),
        features=inputs.features + extra_rows,
    )
    observations = []
    instances = []

    class Stateful:
        def __init__(self):
            self.symbol = None
            self.count = 0
            instances.append(self)

        def evaluate(self, context):
            self.count += 1
            if self.symbol is None:
                self.symbol = context.bar.symbol
            assert self.symbol == context.bar.symbol
            observations.append((self.symbol, self.count, context.bar.timestamp))
            return []

    strategy = plan(lambda _: Stateful())
    first = run(config, inputs, strategy)
    previous = observations[:]
    observations.clear()
    second = run(config, inputs, strategy)
    assert observations == previous
    assert len(instances) == 4 and all(s.count == 75 for s in instances)
    assert first.deterministic_payload() == second.deterministic_payload()
