"""Deterministic bar-completion simulator with strict subsequent-open eligibility."""

from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from types import MappingProxyType
from typing import Any
from uuid import UUID

from trading_bot.backtesting.accounting import Portfolio
from trading_bot.backtesting.clock import timeline
from trading_bot.backtesting.config import BacktestConfig
from trading_bot.backtesting.costs import TradingCostModel
from trading_bot.backtesting.decisions import ScriptedDecisionSource
from trading_bot.backtesting.events import Event
from trading_bot.backtesting.execution import base_price, execution_price
from trading_bot.backtesting.inputs import BacktestInputs
from trading_bot.backtesting.metrics import performance
from trading_bot.backtesting.orders import (
    BacktestError,
    OrderType,
    Side,
    SimOrder,
    Status,
    TradeIntent,
)
from trading_bot.backtesting.results import BacktestResult, EquityPoint, Fill
from trading_bot.backtesting.slippage import SlippageModel
from trading_bot.data.identity import digest
from trading_bot.data.snapshot import SnapshotBar
from trading_bot.domain.market import Timeframe
from trading_bot.features.engine import FeatureCalendar
from trading_bot.strategies.contracts import StrategyContext, StrategyError
from trading_bot.strategies.registry import StrategyPlan
from trading_bot.strategies.runtime import StrategyRuntime


class BacktestEngine:
    def __init__(
        self,
        calendar: FeatureCalendar,
        costs: TradingCostModel,
        slippage: SlippageModel,
    ) -> None:
        self.calendar, self.costs, self.slippage = calendar, costs, slippage

    def run(
        self,
        run_id: UUID,
        inputs: BacktestInputs,
        config: BacktestConfig,
        script: ScriptedDecisionSource,
        strategy: StrategyPlan | None = None,
    ) -> BacktestResult:
        # Isolate accounting precision from caller-modified decimal contexts.
        with localcontext() as context:
            context.prec = 40
            return Simulation(self, run_id, inputs, config, script, strategy).run()


class Simulation:
    """Per-run mutable state; never shared between runs or symbols."""

    def __init__(
        self,
        engine: BacktestEngine,
        run_id: UUID,
        inputs: BacktestInputs,
        config: BacktestConfig,
        script: ScriptedDecisionSource,
        strategy: StrategyPlan | None = None,
    ) -> None:
        self.engine, self.run_id, self.inputs, self.config, self.script = (
            engine,
            run_id,
            inputs,
            config,
            script,
        )
        if strategy is not None and script.intents:
            raise StrategyError(
                "strategy and scripted decisions are mutually exclusive"
            )
        self.strategy_plan = strategy
        self.strategy_runtime: StrategyRuntime | None = None
        self.portfolio = Portfolio(config.starting_capital)
        self.orders: list[SimOrder] = []
        self.fills: list[Fill] = []
        self.events: list[Event] = []
        self.equity: list[EquityPoint] = []
        self.prices: dict[str, Decimal] = {}
        self.warnings: set[str] = set()
        self.features = {(r.symbol, r.timestamp): r for r in inputs.features}
        self.sessions = engine.calendar.sessions(
            config.history.start, config.history.end
        )
        self.cutoffs: dict[datetime, datetime] = {}
        self.openings: dict[datetime, list[datetime]] = {}

    def emit(
        self,
        timestamp: datetime,
        kind: Any,
        symbol: str | None = None,
        reference: str | None = None,
        **details: Any,
    ) -> None:
        self.events.append(
            Event(
                sequence=len(self.events),
                timestamp=timestamp,
                kind=kind,
                symbol=symbol,
                reference=reference,
                details=details,
            )
        )

    def validate(self) -> None:
        cfg = self.config
        if cfg.history.timeframe == Timeframe.DAY_1 or not self.sessions:
            raise BacktestError("intraday timeframe and sessions required")
        if any(
            s.opens < cfg.history.start or s.closes > cfg.history.end
            for s in self.sessions
        ):
            raise BacktestError("run must contain complete selected sessions")
        slots = self.engine.calendar.expected_bars(
            cfg.history.start, cfg.history.end, cfg.history.timeframe
        )
        actual = {
            (i.bar.symbol, i.bar.timestamp): i.available_at
            for i in self.inputs.snapshot.bars
        }
        expected = {(s, t): a for s in cfg.history.symbols for t, a in slots.items()}
        if actual != expected or len(actual) != len(self.inputs.snapshot.bars):
            raise BacktestError(
                "MISSING_MARKET_DATA: complete aligned candles required"
            )
        if set(self.features) != set(expected):
            raise BacktestError("missing feature rows")
        for session in self.sessions:
            openings = sorted(t for t in slots if session.opens <= t < session.closes)
            self.openings[session.opens] = openings
            desired = session.closes - timedelta(minutes=cfg.exit_minutes_before_close)
            # A cutoff at close precommits liquidation to the last execution bar.
            cutoff = next((t for t in openings if t >= desired), openings[-1])
            self.cutoffs[session.opens] = cutoff
        for intent in self.script.intents:
            row = self.features.get((intent.symbol, intent.feature_timestamp))
            if row is None or row.available_at > intent.created_at:
                raise BacktestError("decision requests unavailable feature")
            if any(row.values.get(name) is None for name in intent.required_features):
                raise BacktestError("decision requests invalid or warming-up features")
            if not any(s.opens <= intent.created_at < s.closes for s in self.sessions):
                raise BacktestError("decision outside requested sessions")
        raw_warnings = self.engine.costs.manifest().get("warnings", [])
        if not isinstance(raw_warnings, tuple | list):
            raise BacktestError("invalid cost warning metadata")
        self.warnings.update(str(w) for w in raw_warnings)
        dataset = self.inputs.manifest["dataset"]
        if dataset["calendar"]["authority"] != "REVIEWED_POLICY":
            self.warnings.add("CALENDAR_AUTHORITY_UNKNOWN")
        if cfg.source == "groww":
            self.warnings.add("GROWW_SEMANTICS_UNVERIFIED")

    def new_order(
        self, intent: TradeIntent, timestamp: datetime, *, forced: bool = False
    ) -> int:
        session = next(s for s in self.sessions if s.opens <= timestamp < s.closes)
        openings = self.openings[session.opens]
        index = (
            bisect_left(openings, timestamp)
            if forced
            else bisect_right(openings, timestamp)
        )
        eligible = openings[index] if index < len(openings) else None
        order = SimOrder(
            order_id=f"order-{len(self.orders)+1:06}",
            intent=intent,
            eligible_from=eligible,
            forced=forced,
        )
        order = order.transition(
            Status.CREATED,
            timestamp,
            (
                ("STRATEGY_INTENT" if self.strategy_plan else "SCRIPTED_TEST_INTENT")
                if not forced
                else "FORCED_SESSION_EXIT"
            ),
        )
        order = order.transition(Status.ACCEPTED, timestamp, "SIMULATED_ONLY")
        order = order.transition(Status.PENDING, timestamp, "WAIT_FOR_ELIGIBLE_BAR")
        if not forced and timestamp >= self.cutoffs[session.opens]:
            order = order.transition(Status.REJECTED, timestamp, "SESSION_EXIT_CUTOFF")
        elif intent.side == Side.SELL and intent.quantity > self.portfolio.quantity(
            intent.symbol
        ):
            order = order.transition(
                Status.REJECTED, timestamp, "INSUFFICIENT_LONG_INVENTORY"
            )
        self.orders.append(order)
        self.emit(
            timestamp,
            "ORDER",
            intent.symbol,
            order.order_id,
            status=order.status.value,
            eligible_from=eligible.isoformat() if eligible else None,
        )
        return len(self.orders) - 1

    def transition(
        self, index: int, status: Status, timestamp: datetime, reason: str
    ) -> None:
        self.orders[index] = self.orders[index].transition(status, timestamp, reason)
        self.emit(
            timestamp,
            "ORDER",
            self.orders[index].intent.symbol,
            self.orders[index].order_id,
            status=status.value,
            reason=reason,
        )

    def complete(self, item: SnapshotBar) -> None:
        bar, now = item.bar, item.available_at
        self.emit(now, "BAR_COMPLETE", bar.symbol, opening=bar.timestamp.isoformat())
        session = next(s for s in self.sessions if s.opens <= bar.timestamp < s.closes)
        eligible = [
            i
            for i, o in enumerate(self.orders)
            if o.active
            and o.intent.symbol == bar.symbol
            and o.eligible_from is not None
            and o.eligible_from <= bar.timestamp
            and (o.forced or bar.timestamp < self.cutoffs[session.opens])
        ]
        reachable = {i: base_price(self.orders[i], bar) for i in eligible}
        stops = [
            i
            for i in eligible
            if self.orders[i].intent.side == Side.SELL
            and self.orders[i].intent.order_type == OrderType.STOP_MARKET
            and reachable[i] is not None
        ]
        limits = [
            i
            for i in eligible
            if self.orders[i].intent.side == Side.SELL
            and self.orders[i].intent.order_type == OrderType.LIMIT
            and reachable[i] is not None
        ]
        if stops and limits and self.portfolio.quantity(bar.symbol) > 0:
            self.warnings.add("INTRABAR_AMBIGUITY")
            self.emit(
                now,
                "WARNING",
                bar.symbol,
                reason="INTRABAR_AMBIGUITY",
                policy="STOP_FIRST_SUPPRESS_FAVORABLE_LIMIT",
            )
            eligible = [i for i in eligible if i not in limits]
        eligible.sort(key=lambda i: (i not in stops, i))
        remaining_volume = (
            int(Decimal(bar.volume) * self.config.participation_rate)
            if self.config.participation_rate is not None
            else None
        )
        for index in eligible:
            order = self.orders[index]
            base = reachable[index]
            if not order.active or base is None:
                continue
            if order.intent.order_type == OrderType.STOP_MARKET and not any(
                t.status == Status.TRIGGERED for t in order.transitions
            ):
                self.transition(index, Status.TRIGGERED, now, "STOP_REACHED")
                order = self.orders[index]
            quantity = (
                min(order.remaining, remaining_volume)
                if remaining_volume is not None
                else order.remaining
            )
            if not quantity:
                continue
            price = execution_price(order, base, self.engine.slippage)
            if price <= 0 or not price.is_finite():
                raise BacktestError("invalid simulated execution price")
            previous = self.engine.costs.cumulative(
                order.intent.side, order.executed_turnover, forced=order.forced
            )
            full = self.engine.costs.cumulative(
                order.intent.side,
                order.executed_turnover + order.remaining * price,
                forced=order.forced,
            ).difference(previous)
            if (
                order.intent.side == Side.BUY
                and order.remaining * price + full.total > self.portfolio.cash
            ):
                self.transition(
                    index, Status.REJECTED, now, "INSUFFICIENT_CASH_NO_LEVERAGE"
                )
                continue
            if (
                order.intent.side == Side.SELL
                and order.remaining > self.portfolio.quantity(bar.symbol)
            ):
                self.transition(
                    index, Status.REJECTED, now, "INSUFFICIENT_LONG_INVENTORY"
                )
                continue
            cumulative = order.executed_turnover + quantity * price
            costs = self.engine.costs.cumulative(
                order.intent.side, cumulative, forced=order.forced
            ).difference(previous)
            reason = "FORCED_SESSION_EXIT" if order.forced else order.intent.reference
            fill = Fill(
                fill_id=f"fill-{len(self.fills)+1:06}",
                order_id=order.order_id,
                symbol=bar.symbol,
                side=order.intent.side,
                quantity=quantity,
                timestamp=now,
                bar_open=bar.timestamp,
                base_price=base,
                price=price,
                costs=costs,
                slippage_cost=abs(price - base) * quantity,
                reason=reason,
            )
            self.portfolio.apply(fill)
            self.fills.append(fill)
            self.emit(
                now,
                "FILL",
                bar.symbol,
                order.order_id,
                fill=fill.model_dump(mode="json"),
            )
            self.orders[index] = order.model_copy(
                update={
                    "filled_quantity": order.filled_quantity + quantity,
                    "executed_turnover": cumulative,
                }
            )
            self.transition(
                index,
                (
                    Status.FILLED
                    if self.orders[index].remaining == 0
                    else Status.PARTIALLY_FILLED
                ),
                now,
                reason,
            )
            if remaining_volume is not None:
                remaining_volume -= quantity
            if order.intent.oco_group:
                for other, candidate in enumerate(self.orders):
                    if (
                        other != index
                        and candidate.active
                        and candidate.intent.symbol == bar.symbol
                        and candidate.intent.oco_group == order.intent.oco_group
                    ):
                        self.transition(
                            other, Status.CANCELLED, now, "OCO_SIBLING_FILLED"
                        )
        self.prices[bar.symbol] = bar.close
        self.emit(now, "FEATURE", bar.symbol, opening=bar.timestamp.isoformat())
        self.record_equity(now)
        self.evaluate_strategy(item, session.opens, session.closes)

    def evaluate_strategy(
        self, item: SnapshotBar, session_open: datetime, session_close: datetime
    ) -> None:
        runtime = self.strategy_runtime
        if runtime is None:
            return
        bar, now = item.bar, item.available_at
        row = self.features[(bar.symbol, bar.timestamp)]
        if row.available_at > now:
            raise StrategyError("feature is not available at strategy evaluation")
        position = self.portfolio.positions.get(bar.symbol)
        context = StrategyContext(
            current_time=now,
            bar=bar.model_copy(deep=True),
            available_at=max(item.available_at, row.available_at),
            features=MappingProxyType(dict(row.values)),
            unavailable=MappingProxyType(dict(row.unavailable)),
            position_quantity=position.quantity if position else 0,
            average_entry_price=position.average_price if position else Decimal(0),
            cash=self.portfolio.cash,
            equity=self.equity[-1].equity,
            session_open=session_open,
            session_close=session_close,
            strategy_identity=runtime.plan.manifest()["identity"],
            parameters=runtime.parameters,
        )
        intents = runtime.evaluate(context)
        self.emit(
            now,
            "STRATEGY",
            bar.symbol,
            strategy_identity=context.strategy_identity,
            feature_timestamp=bar.timestamp.isoformat(),
            available_at=context.available_at.isoformat(),
            intent_count=len(intents),
        )
        for intent in intents:
            self.emit(
                now,
                "DECISION",
                bar.symbol,
                intent.reference,
                strategy_identity=context.strategy_identity,
                feature_timestamp=intent.feature_timestamp.isoformat(),
            )
            self.new_order(intent, now)

    def record_equity(self, now: datetime) -> None:
        point = self.portfolio.mark(now, self.prices)
        self.equity.append(point)
        self.emit(now, "PORTFOLIO", equity=str(point.equity), cash=str(point.cash))

    def run(self) -> BacktestResult:
        self.validate()
        if self.strategy_plan is not None:
            self.strategy_runtime = StrategyRuntime(
                self.strategy_plan, self.config.history.symbols
            )
        self.record_equity(self.sessions[0].opens)
        for tick in timeline(self.inputs.snapshot, self.sessions, self.script):
            now = tick.timestamp
            if tick.kind == "BAR_COMPLETE":
                self.complete(self.inputs.snapshot.bars[int(tick.reference)])
            elif tick.kind == "DECISION":
                intent = self.script.intents[int(tick.reference)]
                self.emit(
                    now,
                    "DECISION",
                    intent.symbol,
                    intent.reference,
                    feature_timestamp=intent.feature_timestamp.isoformat(),
                )
                self.new_order(intent, now)
            elif tick.kind == "BAR_OPEN":
                item = self.inputs.snapshot.bars[int(tick.reference)]
                symbol = item.bar.symbol
                self.emit(now, "BAR_OPEN", symbol, open=str(item.bar.open))
                session = next(s for s in self.sessions if s.opens <= now < s.closes)
                if now == self.cutoffs[session.opens]:
                    for index, order in enumerate(self.orders):
                        if (
                            order.active
                            and order.intent.symbol == symbol
                            and self.portfolio.quantity(symbol)
                        ):
                            self.transition(
                                index, Status.CANCELLED, now, "SESSION_EXIT_CUTOFF"
                            )
                    quantity = self.portfolio.quantity(symbol)
                    if quantity:
                        self.warnings.add("FORCED_SESSION_EXIT")
                        intent = TradeIntent(
                            reference="FORCED_SESSION_EXIT",
                            symbol=symbol,
                            side=Side.SELL,
                            quantity=quantity,
                            created_at=now,
                            feature_timestamp=now - timedelta(microseconds=1),
                        )
                        self.new_order(intent, now, forced=True)
            else:
                self.emit(now, tick.kind)
                if tick.kind == "SESSION_OPEN" and self.equity[-1].timestamp != now:
                    self.record_equity(now)
                if tick.kind == "SESSION_CLOSE":
                    for index, order in enumerate(self.orders):
                        if order.active:
                            self.transition(
                                index, Status.EXPIRED, now, "DAY_SESSION_ENDED"
                            )
                    if any(p.quantity for p in self.portfolio.positions.values()):
                        raise BacktestError(
                            "FORCED_EXIT_INCOMPLETE: no overnight positions allowed"
                        )
                    self.record_equity(now)
        manifest = {
            "config": self.config.model_dump(mode="json"),
            "feature_manifest": self.inputs.manifest,
            "script": self.script.model_dump(mode="json"),
            "costs": self.engine.costs.manifest(),
            "slippage": self.engine.slippage.manifest(),
            "version": "backtest-v1",
        }
        if self.strategy_plan is not None:
            manifest["strategy"] = self.strategy_plan.manifest()
        # Ingestion UUIDs are provenance only; exclude them from numerical identity.
        canonical = {
            **manifest,
            "feature_manifest": {
                k: v
                for k, v in self.inputs.manifest.items()
                if k != "historical_identities"
            },
        }
        return BacktestResult(
            run_id=self.run_id,
            config_key=digest(canonical),
            manifest=manifest,
            status="COMPLETED_WITH_WARNINGS" if self.warnings else "COMPLETED",
            orders=tuple(self.orders),
            fills=tuple(self.fills),
            trades=tuple(self.portfolio.trades),
            equity=tuple(self.equity),
            events=tuple(self.events),
            metrics=performance(self.equity, self.fills, self.portfolio.trades),
            warnings=tuple(sorted(self.warnings)),
        )
