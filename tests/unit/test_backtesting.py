from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from trading_bot.backtesting.accounting import Portfolio
from trading_bot.backtesting.costs import (
    CostBreakdown,
    ReferenceCostModel,
    ZeroCostModel,
)
from trading_bot.backtesting.decisions import ScriptedDecisionSource
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.backtesting.execution import base_price, execution_price
from trading_bot.backtesting.metrics import performance
from trading_bot.backtesting.orders import (
    BacktestError,
    Side,
    SimOrder,
    Status,
    TradeIntent,
)
from trading_bot.backtesting.results import Fill
from trading_bot.backtesting.slippage import BasisPointsSlippageModel
from trading_bot.data.calendar import NSECalendar

D = Decimal


def intent(config, index=1, side="BUY", quantity=10, **changes):
    return TradeIntent(
        reference=f"{side}-{index}",
        symbol="RELIANCE",
        side=side,
        quantity=quantity,
        created_at=config.history.start + timedelta(minutes=5 * index),
        feature_timestamp=config.history.start + timedelta(minutes=5 * (index - 1)),
        **changes,
    )


def run(config, inputs, intents=(), costs=None, bps=0):
    return BacktestEngine(
        NSECalendar(), costs or ZeroCostModel(), BasisPointsSlippageModel(D(bps))
    ).run(uuid4(), inputs, config, ScriptedDecisionSource(intents=tuple(intents)))


@pytest.fixture
def fees():
    return ReferenceCostModel.load(Path("config/groww_nse_intraday_reference_v1.yaml"))


@pytest.mark.parametrize(
    "side,stt,stamp,total",
    [(Side.BUY, "0", "0.30", "12.48"), (Side.SELL, "2.50", "0", "14.68")],
)
def test_reference_fee_components(fees, side, stt, stamp, total):
    costs = fees.cumulative(side, D("10000"))
    assert costs.brokerage == 10
    assert costs.stt == D(stt) and costs.stamp_duty == D(stamp)
    assert (
        costs.exchange == D("0.30")
        and costs.sebi == D("0.01")
        and costs.ipft == D("0.01")
    )
    assert costs.gst == D("1.86") and costs.other == 0
    assert costs.total == D(total)


@pytest.mark.parametrize(
    "turnover,brokerage",
    [
        (0, 0),
        (100, D("2.50")),
        (200, 5),
        (1000, 5),
        (5000, 5),
        (10000, 10),
        (20000, 20),
        (100000, 20),
    ],
)
def test_brokerage_minimum_cap_and_zero(fees, turnover, brokerage):
    assert fees.cumulative(Side.BUY, D(turnover)).brokerage == brokerage


def test_incremental_fees_do_not_repeat_minimum(fees):
    first = fees.cumulative(Side.BUY, D(1000))
    second = fees.cumulative(Side.BUY, D(2000)).difference(first)
    assert first.brokerage == 5 and second.brokerage == 0
    assert first.plus(second) == fees.cumulative(Side.BUY, D(2000))


def test_gst_base_explicit_and_squareoff_optional(fees):
    model = ReferenceCostModel(
        fees.profile.model_copy(
            update={"gst_components": ("brokerage",), "square_off_charge": D(50)}
        )
    )
    costs = model.cumulative(Side.SELL, D(10000), forced=True)
    assert costs.gst == D("1.80") and costs.other == 50
    assert fees.cumulative(Side.SELL, D(10000), forced=True).other == 0


def test_same_bar_anti_cheating_and_strict_ordering(backtest_inputs):
    config, inputs = backtest_inputs()
    items = list(inputs.snapshot.bars)
    items[0] = replace(
        items[0],
        bar=items[0].bar.model_copy(
            update={"open": D(100), "high": D(200), "low": D(90), "close": D(190)}
        ),
    )
    inputs = replace(inputs, snapshot=replace(inputs.snapshot, bars=tuple(items)))
    result = run(config, inputs, [intent(config)])
    buy = result.fills[0]
    assert buy.base_price == 102 and buy.base_price not in (100, 90, 190)
    assert buy.bar_open == config.history.start + timedelta(minutes=10)
    assert buy.timestamp == config.history.start + timedelta(minutes=15)
    assert result.orders[0].eligible_from > result.orders[0].intent.created_at
    assert all(
        f.bar_open > result.orders[0].intent.feature_timestamp for f in result.fills
    )
    assert [e.timestamp for e in result.events] == sorted(
        e.timestamp for e in result.events
    )


def test_future_mutation_preserves_earlier_events_orders_fills_equity(backtest_inputs):
    config, inputs = backtest_inputs()
    script = [intent(config), intent(config, 6, "SELL")]
    before = run(config, inputs, script)
    changed = list(inputs.snapshot.bars)
    cutoff = changed[20].bar.timestamp
    for i in range(20, len(changed)):
        b = changed[i].bar
        changed[i] = replace(
            changed[i],
            bar=b.model_copy(
                update={f: getattr(b, f) * 2 for f in ("open", "high", "low", "close")}
                | {"volume": 1}
            ),
        )
    after = run(
        config,
        replace(inputs, snapshot=replace(inputs.snapshot, bars=tuple(changed))),
        script,
    )
    assert before.orders == after.orders and before.fills == after.fills
    assert [p for p in before.equity if p.timestamp < cutoff] == [
        p for p in after.equity if p.timestamp < cutoff
    ]
    assert [e for e in before.events if e.timestamp < cutoff] == [
        e for e in after.events if e.timestamp < cutoff
    ]


def test_slippage_exact_cost_comparison_and_determinism(backtest_inputs, fees):
    config, inputs = backtest_inputs()
    script = [intent(config), intent(config, 6, "SELL")]
    zero = run(config, inputs, script)
    again = run(config, inputs, script)
    adverse = run(config, inputs, script, bps=10)
    charged = run(config, inputs, script, costs=fees)
    assert zero.deterministic_payload() == again.deterministic_payload()
    assert zero.run_id != again.run_id
    assert zero.metrics["net_pnl"] == 50
    assert adverse.metrics["estimated_slippage_cost"] == D("2.090")
    assert adverse.metrics["net_pnl"] == D("47.910")
    assert (
        adverse.fills[0].price > zero.fills[0].price
        and adverse.fills[1].price < zero.fills[1].price
    )
    assert adverse.config_key != zero.config_key
    assert charged.metrics["gross_pnl"] == zero.metrics["gross_pnl"]
    assert charged.metrics["net_pnl"] == 50 - charged.metrics["total_costs"]
    modified = ReferenceCostModel(
        fees.profile.model_copy(update={"version": "different"})
    )
    assert run(config, inputs, script, costs=modified).config_key != charged.config_key


@pytest.mark.parametrize(
    "side,kind,level,expected",
    [
        ("BUY", "LIMIT", 101, 100),
        ("BUY", "LIMIT", 95, 95),
        ("BUY", "LIMIT", 89, None),
        ("SELL", "LIMIT", 99, 100),
        ("SELL", "LIMIT", 108, 108),
        ("SELL", "LIMIT", 111, None),
        ("SELL", "STOP_MARKET", 105, 100),
        ("SELL", "STOP_MARKET", 95, 95),
        ("BUY", "STOP_MARKET", 95, 100),
        ("BUY", "STOP_MARKET", 108, 108),
    ],
)
def test_order_price_reachability(backtest_inputs, side, kind, level, expected):
    config, inputs = backtest_inputs()
    key = "limit_price" if kind == "LIMIT" else "trigger_price"
    order = SimOrder(
        order_id="test",
        intent=intent(config, side=side, order_type=kind, **{key: D(level)}),
        eligible_from=None,
    )
    bar = inputs.snapshot.bars[0].bar.model_copy(
        update={"open": D(100), "high": D(110), "low": D(90), "close": D(105)}
    )
    assert base_price(order, bar) == expected
    if expected is not None and kind == "LIMIT":
        slipped = execution_price(order, D(expected), BasisPointsSlippageModel(D(100)))
        assert slipped <= level if side == "BUY" else slipped >= level


def test_stop_gap_and_ambiguity_conservative(backtest_inputs):
    config, inputs = backtest_inputs()
    items = list(inputs.snapshot.bars)
    items[5] = replace(
        items[5],
        bar=items[5].bar.model_copy(
            update={"open": D(95), "high": D(110), "low": D(90), "close": D(105)}
        ),
    )
    inputs = replace(inputs, snapshot=replace(inputs.snapshot, bars=tuple(items)))
    stop = intent(
        config,
        4,
        "SELL",
        order_type="STOP_MARKET",
        trigger_price="100",
        oco_group="exits",
    )
    limit = intent(
        config, 4, "SELL", order_type="LIMIT", limit_price="108", oco_group="exits"
    ).model_copy(update={"reference": "target-fixture"})
    result = run(config, inputs, [intent(config), limit, stop], bps=10)
    assert result.fills[1].base_price == 95 and result.fills[1].price == D("94.905")
    assert "INTRABAR_AMBIGUITY" in result.warnings
    assert result.orders[1].status == Status.CANCELLED
    assert result.orders[2].status == Status.FILLED
    assert any(t.status == Status.TRIGGERED for t in result.orders[2].transitions)


def test_partial_fill_shared_volume_and_cumulative_brokerage(backtest_inputs, fees):
    config, inputs = backtest_inputs(volumes=[100] * 75)
    config = config.model_copy(
        update={"participation_rate": D("0.1"), "exit_minutes_before_close": 15}
    )
    script = [intent(config, quantity=25)]
    result = run(config, inputs, script, costs=fees)
    buys = [f for f in result.fills if f.side == Side.BUY]
    assert [f.quantity for f in buys] == [10, 10, 5]
    assert sum(f.costs.brokerage for f in buys) == 5
    assert any(
        t.status == Status.PARTIALLY_FILLED for t in result.orders[0].transitions
    )
    for time in {f.timestamp for f in result.fills}:
        assert sum(f.quantity for f in result.fills if f.timestamp == time) <= 10
    assert "FORCED_SESSION_EXIT" in result.warnings


def test_insufficient_cash_rejection_no_short_and_day_expiry(backtest_inputs):
    config, inputs = backtest_inputs()
    config = config.model_copy(update={"starting_capital": D(50)})
    result = run(
        config,
        inputs,
        [
            intent(config),
            intent(config, 2, "SELL"),
            intent(config, 3, order_type="LIMIT", limit_price="1"),
        ],
    )
    assert result.orders[0].status == Status.REJECTED
    assert result.orders[1].status == Status.REJECTED
    assert result.orders[2].status == Status.EXPIRED
    assert result.metrics["ending_equity"] == 50


def test_missing_data_unavailable_features_and_forced_exit_failure(backtest_inputs):
    config, inputs = backtest_inputs()
    missing = replace(
        inputs,
        snapshot=replace(
            inputs.snapshot, bars=inputs.snapshot.bars[:10] + inputs.snapshot.bars[11:]
        ),
    )
    with pytest.raises(BacktestError, match="MISSING_MARKET_DATA"):
        run(config, missing)
    unavailable = intent(config).model_copy(
        update={"created_at": config.history.start + timedelta(minutes=4)}
    )
    with pytest.raises(BacktestError, match="unavailable feature"):
        run(config, inputs, [unavailable])
    with pytest.raises(BacktestError, match="warming-up"):
        run(config, inputs, [intent(config, required_features=("rsi_14",))])
    items = list(inputs.snapshot.bars)
    for i in (73, 74):
        items[i] = replace(items[i], bar=items[i].bar.model_copy(update={"volume": 0}))
    illiquid = replace(inputs, snapshot=replace(inputs.snapshot, bars=tuple(items)))
    with pytest.raises(BacktestError, match="FORCED_EXIT_INCOMPLETE"):
        run(
            config.model_copy(update={"participation_rate": D("0.1")}),
            illiquid,
            [intent(config)],
        )


def test_accounting_multiple_entries_partial_full_exit_and_fees(backtest_inputs):
    config, _ = backtest_inputs()
    portfolio = Portfolio(D(10000))

    def fill(side, qty, price):
        return Fill(
            fill_id="fill",
            order_id="order",
            symbol="RELIANCE",
            side=side,
            quantity=qty,
            timestamp=config.history.start,
            bar_open=config.history.start,
            base_price=D(price),
            price=D(price),
            costs=CostBreakdown(brokerage=D(1)),
            slippage_cost=D(0),
            reason="test",
        )

    portfolio.apply(fill("BUY", 10, 100))
    portfolio.apply(fill("BUY", 10, 120))
    assert portfolio.positions["RELIANCE"].average_price == 110
    portfolio.apply(fill("SELL", 5, 130))
    assert portfolio.realized == 100 and portfolio.quantity("RELIANCE") == 15
    point = portfolio.mark(config.history.start, {"RELIANCE": D(120)})
    assert point.unrealized_pnl == 150 and point.equity == D(10247)
    portfolio.apply(fill("SELL", 15, 100))
    assert portfolio.realized == -50 and portfolio.cash == 9946
    assert portfolio.quantity("RELIANCE") == 0 and portfolio.fees == 4
    trade = portfolio.trades[0]
    assert (
        trade.execution_pnl == -50
        and trade.net_pnl == -54
        and trade.entry_quantity == 20
    )


def test_drawdown_from_open_position_equity_and_insufficient_ratios(backtest_inputs):
    config, _ = backtest_inputs()
    portfolio = Portfolio(D(100))
    points = []
    for i, value in enumerate((100, 120, 90, 110, 80)):
        portfolio.cash = D(value)
        points.append(
            portfolio.mark(config.history.start + timedelta(minutes=5 * i), {})
        )
    metrics = performance(points, [], [])
    assert metrics["max_drawdown"] == 40
    assert metrics["max_drawdown_pct"] == D(40) / 120
    assert metrics["sharpe"] is None and metrics["sortino"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": 0},
        {"quantity": 1.5},
        {"order_type": "STOP_LIMIT"},
        {"order_type": "LIMIT"},
        {"limit_price": "100"},
    ],
)
def test_invalid_order_validation(backtest_inputs, changes):
    config, _ = backtest_inputs()
    data = intent(config).model_dump() | changes
    with pytest.raises(ValidationError):
        TradeIntent.model_validate(data)


def test_triggered_partial_stop_remains_market_without_retouch(backtest_inputs):
    config, inputs = backtest_inputs(volumes=[100] * 75)
    config = config.model_copy(update={"participation_rate": D("0.1")})
    items = list(inputs.snapshot.bars)
    items[5] = replace(items[5], bar=items[5].bar.model_copy(update={"low": D(90)}))
    result = run(
        config,
        replace(inputs, snapshot=replace(inputs.snapshot, bars=tuple(items))),
        [
            intent(config, quantity=15),
            intent(
                config,
                4,
                "SELL",
                quantity=15,
                order_type="STOP_MARKET",
                trigger_price="100",
            ),
        ],
    )
    sells = [f for f in result.fills if f.side == Side.SELL]
    assert [(f.quantity, f.base_price) for f in sells] == [(10, D(100)), (5, D(106))]


def test_shared_participation_across_orders(backtest_inputs):
    config, inputs = backtest_inputs(volumes=[100] * 75)
    config = config.model_copy(
        update={"participation_rate": D("0.1"), "exit_minutes_before_close": 20}
    )
    second = intent(config, quantity=10).model_copy(update={"reference": "second"})
    result = run(config, inputs, [intent(config, quantity=10), second])
    buys = [f for f in result.fills if f.side == Side.BUY]
    assert len(buys) == 2 and buys[0].timestamp < buys[1].timestamp


def test_two_sessions_weekend_and_multisymbol_inventory(backtest_inputs):
    config, inputs = backtest_inputs(
        symbols=("RELIANCE", "TCS"),
        start="2026-01-09T09:15:00+05:30",
        end="2026-01-12T15:30:00+05:30",
    )
    first = intent(config)
    other = first.model_copy(update={"reference": "TCS-entry", "symbol": "TCS"})
    result = run(config, inputs, [first, other])
    assert len(result.trades) == 2
    assert {f.symbol for f in result.fills} == {"RELIANCE", "TCS"}
    assert all(t.exit_time.date() == config.history.start.date() for t in result.trades)
    assert all(
        p.market_value == 0
        for p in result.equity
        if p.timestamp.date() > config.history.start.date()
    )
    assert sum(e.kind == "SESSION_OPEN" for e in result.events) == 2


def test_sharpe_sortino_valid_daily_frequency(backtest_inputs):
    config, _ = backtest_inputs()
    portfolio = Portfolio(D(10000))
    points = [portfolio.mark(config.history.start, {})]
    for i in range(20):
        portfolio.cash *= D("1.01") if i % 2 == 0 else D("0.995")
        points.append(
            portfolio.mark(config.history.start + timedelta(days=i, minutes=5), {})
        )
    result = performance(points, [], [])
    assert result["sharpe"] is not None and result["sortino"] is not None
    assert result["sharpe"] > 0 and result["sortino"] > 0


@pytest.mark.parametrize("bps", ["-1", "10000", "NaN", "Infinity"])
def test_slippage_invalid_configuration(bps):
    with pytest.raises(ValueError):
        BasisPointsSlippageModel(D(bps))
