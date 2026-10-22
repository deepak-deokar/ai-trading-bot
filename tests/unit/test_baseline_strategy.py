from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from uuid import uuid4

import pytest
from pydantic import ValidationError

from trading_bot.backtesting.costs import ZeroCostModel
from trading_bot.backtesting.decisions import ScriptedDecisionSource
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.backtesting.orders import Side, Status, TradeIntent
from trading_bot.backtesting.slippage import ZeroSlippageModel
from trading_bot.data.calendar import NSECalendar
from trading_bot.domain.models import Bar
from trading_bot.strategies.baseline import (
    REQUIRED,
    BaselineParameters,
    BaselineTrendMomentumStrategy,
)
from trading_bot.strategies.contracts import (
    CancelIntent,
    IntentValidationError,
    OrderSnapshot,
    StrategyContext,
)
from trading_bot.strategies.registry import StrategyConfig, builtin_registry
from trading_bot.strategies.runtime import StrategyRuntime


def context(**changes):
    now = datetime.fromisoformat("2026-01-05T10:55:00+05:30")
    bar = Bar(
        symbol="RELIANCE",
        timestamp=now - timedelta(minutes=5),
        open=1490,
        high=1492,
        low=1488,
        close=1490,
        volume=1000,
    )
    ctx = StrategyContext(
        current_time=now,
        bar=bar,
        available_at=now,
        features=MappingProxyType(
            dict(
                ema_10=1501.0,
                ema_20=1499.0,
                momentum_5=1.0,
                rsi_14=61.0,
                atr_14=10.0,
                volume_ratio=1.22,
                session_progress=0.3,
            )
        ),
        unavailable={},
        position_quantity=0,
        average_entry_price=Decimal(0),
        cash=Decimal(200000),
        equity=Decimal(200000),
        session_open=now.replace(hour=9, minute=15),
        session_close=now.replace(hour=15, minute=30),
        strategy_identity="test",
        parameters={},
    )
    return replace(ctx, **changes)


def observed(intent, status=Status.FILLED, filled=10, remaining=0):
    return OrderSnapshot(
        intent.reference,
        intent.side,
        status,
        status in (Status.PENDING, Status.PARTIALLY_FILLED),
        filled,
        remaining,
        False,
    )


def strategy():
    return BaselineTrendMomentumStrategy(BaselineParameters())


def protection():
    instance = strategy()
    ctx = context()
    entry = instance.evaluate(ctx)[0]
    after = replace(
        ctx,
        current_time=ctx.current_time + timedelta(minutes=10),
        position_quantity=10,
        average_entry_price=Decimal(1500),
        features={**ctx.features, "atr_14": 999.0},
        orders=(observed(entry),),
    )
    requests = instance.evaluate(after)
    stop, target = [r for r in requests if isinstance(r, TradeIntent)]
    return instance, after, entry, stop, target


def test_registry_default_and_identity():
    registry = builtin_registry()
    cfg = StrategyConfig(name="baseline_trend_momentum_v1", version="1")
    plan = registry.resolve(cfg)
    assert isinstance(plan.create(), BaselineTrendMomentumStrategy)
    assert plan.manifest() == registry.resolve(cfg).manifest()
    for parameter, value in [("stop_atr_multiple", "2.0"), ("rsi_min", 56)]:
        other = registry.resolve(
            cfg.model_copy(update={"parameters": {parameter: value}})
        )
        assert other.manifest()["identity"] != plan.manifest()["identity"]
    assert plan.manifest()["parameters"]["quantity"] == 10


@pytest.mark.parametrize(
    "params",
    [
        {"quantity": 0},
        {"quantity": -1},
        {"quantity": 1.5},
        {"quantity": True},
        {"rsi_min": -1},
        {"rsi_max": 101},
        {"rsi_min": 70, "rsi_max": 70},
        {"min_volume_ratio": -1},
        {"stop_atr_multiple": 0},
        {"target_atr_multiple": -1},
        {"entry_start_time": "14:45", "last_entry_time": "09:30"},
        {"entry_start_time": "09:30:01"},
        {"last_entry_time": "bad"},
        {"rsi_min": float("nan")},
        {"target_atr_multiple": "Infinity"},
    ],
)
def test_invalid_parameters(params):
    with pytest.raises(ValidationError):
        BaselineParameters(**params)


@pytest.mark.parametrize("feature", REQUIRED)
def test_warmup_no_trade(feature):
    ctx = context()
    assert (
        strategy().evaluate(replace(ctx, features={**ctx.features, feature: None}))
        == []
    )
    assert strategy().evaluate(replace(ctx, unavailable={feature: "WARMUP"})) == []


@pytest.mark.parametrize(
    "feature,value",
    [
        ("ema_10", 1498),
        ("momentum_5", 0),
        ("rsi_14", 54),
        ("rsi_14", 71),
        ("volume_ratio", 0.9),
        ("atr_14", 0),
        ("session_progress", 2),
    ],
)
def test_failed_condition_no_trade(feature, value):
    ctx = context()
    assert (
        strategy().evaluate(replace(ctx, features={**ctx.features, feature: value}))
        == []
    )


@pytest.mark.parametrize("hour,minute", [(9, 20), (14, 50)])
def test_outside_window(hour, minute):
    ctx = context()
    now = ctx.current_time.replace(hour=hour, minute=minute)
    ctx = replace(
        ctx,
        current_time=now,
        available_at=now,
        bar=ctx.bar.model_copy(update={"timestamp": now - timedelta(minutes=5)}),
    )
    assert strategy().evaluate(ctx) == []


def test_single_buy_and_pending_prevents_duplicates():
    instance = strategy()
    ctx = context()
    requests = instance.evaluate(ctx)
    assert len(requests) == 1 and requests[0].side == Side.BUY
    assert requests[0].quantity == 10
    assert requests[0].metadata["atr_14"] == "10.0"
    assert instance.evaluate(ctx) == []
    assert (
        instance.evaluate(
            replace(ctx, orders=(observed(requests[0], Status.PENDING, 0, 10),))
        )
        == []
    )


def test_fill_based_protection_not_signal_close_and_no_future_atr():
    instance, ctx, entry, stop, target = protection()
    assert stop.trigger_price == Decimal(1485)
    assert target.limit_price == Decimal(1520)
    assert stop.oco_group == target.oco_group
    assert stop.metadata["entry_atr"] == "10.0"
    assert stop.metadata["fill_basis"] == "1500"
    assert stop.trigger_price != ctx.bar.close - 15
    assert target.limit_price != ctx.bar.close + 20
    assert not any(r.side == Side.BUY for r in (stop, target))
    ctx = replace(
        ctx,
        orders=ctx.orders
        + (
            observed(stop, Status.PENDING, 0, 10),
            observed(target, Status.PENDING, 0, 10),
        ),
    )
    assert instance.evaluate(ctx) == []


def test_reversal_cancels_protection_before_market_exit():
    instance, ctx, entry, stop, target = protection()
    ctx = replace(
        ctx,
        features={**ctx.features, "ema_10": 1490},
        orders=ctx.orders
        + (
            observed(stop, Status.PENDING, 0, 10),
            observed(target, Status.PENDING, 0, 10),
        ),
    )
    requests = instance.evaluate(ctx)
    assert isinstance(requests[0], CancelIntent)
    assert set(requests[0].targets) == {stop.reference, target.reference}
    assert requests[1].side == Side.SELL and requests[1].quantity == 10
    assert requests[1].metadata["reason"] == "EMA10_LE_EMA20"
    ctx = replace(
        ctx, orders=(observed(entry), observed(requests[1], Status.PENDING, 0, 10))
    )
    assert instance.evaluate(ctx) == []


def test_partial_fill_replaces_quantity_and_weighted_basis():
    instance = strategy()
    ctx = context()
    entry = instance.evaluate(ctx)[0]
    ctx = replace(
        ctx,
        position_quantity=4,
        average_entry_price=Decimal(1500),
        orders=(observed(entry, Status.PARTIALLY_FILLED, 4, 6),),
    )
    stop, target = instance.evaluate(ctx)
    assert stop.quantity == target.quantity == 4
    ctx = replace(
        ctx,
        position_quantity=10,
        average_entry_price=Decimal(1506),
        orders=(
            observed(entry),
            observed(stop, Status.PENDING, 0, 4),
            observed(target, Status.PENDING, 0, 4),
        ),
    )
    requests = instance.evaluate(ctx)
    assert isinstance(requests[0], CancelIntent)
    assert requests[1].quantity == requests[2].quantity == 10
    assert requests[1].trigger_price == 1491
    assert requests[2].limit_price == 1526


def test_terminal_lifecycle_no_reentry_on_unchanged_signal():
    instance, ctx, entry, stop, target = protection()
    ctx = replace(
        ctx,
        position_quantity=0,
        average_entry_price=Decimal(0),
        orders=(
            observed(entry),
            observed(stop),
            observed(target, Status.CANCELLED, 0, 10),
        ),
    )
    assert instance.evaluate(ctx) == []
    assert instance.evaluate(ctx) == []
    instance.evaluate(replace(ctx, features={**ctx.features, "momentum_5": -1}))
    assert instance.evaluate(ctx)[0].side == Side.BUY


def test_partial_exit_cancels_remaining_entry_and_reprotects():
    instance, ctx, entry, stop, target = protection()
    ctx = replace(
        ctx,
        position_quantity=3,
        orders=(
            observed(entry, Status.PARTIALLY_FILLED, 5, 5),
            observed(stop, Status.PARTIALLY_FILLED, 2, 3),
            observed(target, Status.CANCELLED, 0, 10),
        ),
    )
    output = instance.evaluate(ctx)
    assert output[0].targets == (entry.reference,)
    assert len(output) == 1  # Keep triggered residual stop; do not reset its trigger.


def test_cancellation_cannot_target_another_symbol():
    cfg = StrategyConfig(name="baseline_trend_momentum_v1", version="1")
    runtime = StrategyRuntime(builtin_registry().resolve(cfg), ("RELIANCE",))

    class Invalid:
        def evaluate(self, ctx):
            return [
                CancelIntent(
                    reference="cancel",
                    symbol="RELIANCE",
                    created_at=ctx.current_time,
                    feature_timestamp=ctx.bar.timestamp,
                    targets=("TCS:entry",),
                    reason="test",
                )
            ]

    runtime.instances["RELIANCE"] = Invalid()
    with pytest.raises(IntentValidationError):
        runtime.evaluate(context())


def controlled_inputs(backtest_inputs, exit_kind):
    cfg, inputs = backtest_inputs(closes=[1500] * 75)
    rows = []
    for index, row in enumerate(inputs.features):
        values = dict(context().features)
        if index < 3:
            values["atr_14"] = None
        if exit_kind == "reversal" and index >= 8:
            values["ema_10"] = 1490
        rows.append(row.model_copy(update={"values": values, "unavailable": {}}))
    bars = list(inputs.snapshot.bars)
    # Signal at 09:35, entry eligible 09:40, published at 09:45.
    # Protection eligible 09:50; subsequent deterministic stop/target at 10:00.
    item = bars[9]
    price = 1480 if exit_kind == "stop" else 1530 if exit_kind == "target" else 1500
    bars[9] = replace(
        item,
        bar=item.bar.model_copy(
            update={
                "open": Decimal(price),
                "high": Decimal(price + 1),
                "low": Decimal(price - 1),
                "close": Decimal(price),
            }
        ),
    )
    return cfg, replace(
        inputs,
        features=tuple(rows),
        snapshot=replace(inputs.snapshot, bars=tuple(bars)),
    )


def simulate(cfg, inputs):
    plan = builtin_registry().resolve(
        StrategyConfig(name="baseline_trend_momentum_v1", version="1")
    )
    return BacktestEngine(NSECalendar(), ZeroCostModel(), ZeroSlippageModel()).run(
        uuid4(), inputs, cfg, ScriptedDecisionSource(), plan
    )


@pytest.mark.parametrize("exit_kind", ["stop", "target", "reversal"])
def test_engine_protection_oco_and_reversal(backtest_inputs, exit_kind):
    cfg, inputs = controlled_inputs(backtest_inputs, exit_kind)
    result = simulate(cfg, inputs)
    assert len(result.trades) == 1
    buys = [o for o in result.orders if o.intent.side == Side.BUY]
    assert len(buys) == 1 and buys[0].status == Status.FILLED
    stop = next(o for o in result.orders if ":STOP:" in o.intent.reference)
    target = next(o for o in result.orders if ":TARGET:" in o.intent.reference)
    if exit_kind == "stop":
        assert stop.status == Status.FILLED and target.status == Status.CANCELLED
    elif exit_kind == "target":
        assert target.status == Status.FILLED and stop.status == Status.CANCELLED
    else:
        assert stop.status == target.status == Status.CANCELLED
        assert ":REVERSAL:" in result.trades[0].exit_reason
    assert result.fills[0].bar_open > buys[0].intent.created_at
    assert result.fills[0].timestamp > result.fills[0].bar_open
    assert (
        result.deterministic_payload() == simulate(cfg, inputs).deterministic_payload()
    )


def test_future_mutation_and_multisymbol_baseline_isolation(backtest_inputs):
    cfg, inputs = controlled_inputs(backtest_inputs, "target")
    result = simulate(cfg, inputs)
    rows = list(inputs.features)
    for i in range(10, 75):
        rows[i] = rows[i].model_copy(
            update={"values": {**rows[i].values, "atr_14": 999.0}}
        )
    changed = simulate(cfg, replace(inputs, features=tuple(rows)))
    future_bars = list(inputs.snapshot.bars)
    for i in range(10, 75):
        future_bars[i] = replace(
            future_bars[i],
            bar=future_bars[i].bar.model_copy(
                update={
                    "open": Decimal(2000),
                    "high": Decimal(2001),
                    "low": Decimal(1999),
                    "close": Decimal(2000),
                }
            ),
        )
    mutated = simulate(
        cfg,
        replace(
            inputs,
            features=tuple(rows),
            snapshot=replace(inputs.snapshot, bars=tuple(future_bars)),
        ),
    )
    assert result.orders[0] == mutated.orders[0]
    assert result.fills[0] == mutated.fills[0]
    assert result.orders[0] == changed.orders[0]
    assert result.orders[1] == changed.orders[1]
    assert result.orders[2] == changed.orders[2]
    cfg = cfg.model_copy(
        update={
            "history": cfg.history.model_copy(update={"symbols": ("RELIANCE", "TCS")})
        }
    )
    extra = tuple(
        replace(b, bar=b.bar.model_copy(update={"symbol": "TCS"}))
        for b in inputs.snapshot.bars
    )
    inputs = replace(
        inputs,
        snapshot=replace(inputs.snapshot, bars=inputs.snapshot.bars + extra),
        features=inputs.features
        + tuple(r.model_copy(update={"symbol": "TCS"}) for r in inputs.features),
    )
    combined = simulate(cfg, inputs)
    assert len(combined.trades) == 2
    assert {t.symbol for t in combined.trades} == {"RELIANCE", "TCS"}


def test_partial_fills_through_engine_keep_stop_trigger(backtest_inputs):
    cfg, inputs = controlled_inputs(backtest_inputs, "stop")
    cfg = cfg.model_copy(update={"participation_rate": Decimal("0.1")})
    bars = tuple(
        replace(b, bar=b.bar.model_copy(update={"volume": 40}))
        for b in inputs.snapshot.bars
    )
    result = simulate(
        cfg, replace(inputs, snapshot=replace(inputs.snapshot, bars=bars))
    )
    assert len(result.trades) == 1
    assert sum(f.quantity for f in result.fills if f.side == Side.BUY) == 10
    assert sum(f.quantity for f in result.fills if f.side == Side.SELL) == 10
    assert all(f.quantity <= 4 for f in result.fills)
    exit_order = next(
        o for o in result.orders if ":STOP:" in o.intent.reference and o.filled_quantity
    )
    assert exit_order.status == Status.FILLED
    assert len([f for f in result.fills if f.order_id == exit_order.order_id]) == 3


@pytest.mark.parametrize("second,expected", [(0, 1), (1, 0)])
def test_last_entry_exact_boundary(second, expected):
    ctx = context()
    now = ctx.current_time.replace(hour=14, minute=45, second=second)
    ctx = replace(
        ctx,
        current_time=now,
        available_at=now,
        bar=ctx.bar.model_copy(update={"timestamp": now - timedelta(minutes=5)}),
    )
    assert len(strategy().evaluate(ctx)) == expected


def test_equivalent_numeric_parameters_same_identity():
    registry = builtin_registry()
    default = registry.resolve(
        StrategyConfig(name="baseline_trend_momentum_v1", version="1")
    )
    explicit = registry.resolve(
        StrategyConfig(
            name="baseline_trend_momentum_v1",
            version="1",
            parameters={"stop_atr_multiple": "1.50", "target_atr_multiple": "2.00"},
        )
    )
    assert default.manifest() == explicit.manifest()


def test_empty_metadata_preserves_legacy_intent_serialization():
    ctx = context()
    intent = TradeIntent(
        reference="legacy",
        symbol=ctx.bar.symbol,
        side="BUY",
        quantity=1,
        created_at=ctx.current_time,
        feature_timestamp=ctx.bar.timestamp,
    )
    assert "metadata" not in intent.model_dump(mode="json")
    assert TradeIntent.model_validate(intent.model_dump()) == intent
