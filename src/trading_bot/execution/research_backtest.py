"""Bounded, realized-balance research orchestration; no broker execution."""

from collections import Counter, deque
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal, localcontext
from typing import Annotated, Literal

from pydantic import Field

from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.domain.contracts import ExactPositive
from trading_bot.domain.models import DomainModel
from trading_bot.domain.positions import PositionDirection
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote
from trading_bot.execution.accounting import Commission, LinearUSDContract, realize_usd
from trading_bot.execution.protection import ProtectiveInstruction, ProtectiveTrigger
from trading_bot.execution.protective_exits import evaluate_bar
from trading_bot.execution.simulator import SimulationBar, simulate_trade
from trading_bot.execution.sizing import SizingResult
from trading_bot.execution.xauusd import XAUUSDExecution
from trading_bot.features.research_repository import content_hash
from trading_bot.features.xauusd import XAUUSDFeatureRow
from trading_bot.strategies.xauusd import evaluate_xauusd
from trading_bot.strategies.xauusd_levels import (
    PlanningStatus,
    StructureBar,
    StructurePlan,
    finalize_levels,
    plan_structure,
)


class ResearchBacktestConfig(DomainModel):
    research_only: Literal[True] = True
    starting_balance: ExactPositive
    risk_fraction: Annotated[
        Decimal, Field(strict=True, gt=0, le=1, allow_inf_nan=False)
    ]
    contract: LinearUSDContract
    commission: Commission


class ResearchDay(DomainModel):
    """Preselected approved data; boundary times come from policy, not future prices."""

    dataset: QuoteDataset
    bars: tuple[QuoteBar, ...]
    features: tuple[XAUUSDFeatureRow, ...]
    boundary_times: tuple[datetime, ...]


class SignalRecord(DomainModel):
    decision_key: str
    strategy_version: str
    dataset_key: str
    research_date: str
    signal_timestamp: datetime
    signal_opening: datetime
    direction: PositionDirection
    signal_reasons: tuple[str, ...]
    status: str
    reason: str
    balance_at_signal: Decimal
    structural_stop: Decimal | None = None
    source_bar_identities: tuple[str, ...] = ()
    effective_stop: Decimal | None = None
    target: Decimal | None = None
    candidate_entry_timestamp: datetime | None = None
    candidate_entry_bid: Decimal | None = None
    candidate_entry_ask: Decimal | None = None
    candidate_source_id: str | None = None
    entry_timestamp: datetime | None = None
    entry_fill: Decimal | None = None
    entry_fill_id: str | None = None
    entry_source_id: str | None = None
    risk_budget: Decimal | None = None
    selected_volume: Decimal | None = None
    planned_stop_risk: Decimal | None = None
    exit_timestamp: datetime | None = None
    exit_fill: Decimal | None = None
    exit_fill_id: str | None = None
    exit_source_id: str | None = None
    gross_pnl: Decimal | None = None
    commission: Decimal | None = None
    net_pnl: Decimal | None = None
    balance_after: Decimal | None = None
    risk_budget_breached: bool = False
    intrabar_ambiguous: bool = False


class DecisionAudit(DomainModel):
    timestamp: datetime
    action: str
    decision_key: str


class PerformanceMetrics(DomainModel):
    starting_balance: Decimal
    ending_balance: Decimal
    signals_generated: int
    trade_plans_attempted: int
    trades_opened: int
    trades_closed: int
    rejected_plans: int
    rejection_reasons: dict[str, int]
    ignored_signals: int
    no_valid_volume: int
    long_trades: int
    short_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate_percent: Decimal | None
    gross_profit: Decimal
    gross_loss: Decimal
    gross_trading_pnl: Decimal
    commissions: Decimal
    net_pnl: Decimal
    return_percent: Decimal
    average_win: Decimal | None
    average_loss: Decimal | None
    payoff_ratio: Decimal | None
    expectancy: Decimal | None
    profit_factor: Decimal | None
    max_drawdown_usd: Decimal
    max_drawdown_percent: Decimal
    largest_win: Decimal | None
    largest_loss: Decimal | None
    exit_reasons: dict[str, int]
    gap_risk_breaches: int


def _add(a: Decimal, b: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = (
            max(a.adjusted(), b.adjusted())
            - min(int(a.as_tuple().exponent), int(b.as_tuple().exponent))
            + 3
        )
        return a + b


def _sum(values: Iterable[Decimal]) -> Decimal:
    result = Decimal(0)
    for value in values:
        result = _add(result, value)
    return result


def _ratio(a: Decimal, b: Decimal) -> Decimal | None:
    if b == 0:
        return None
    with localcontext() as context:
        context.prec = 50
        return a / b


def summarize(
    records: tuple[SignalRecord, ...], starting_balance: Decimal
) -> PerformanceMetrics:
    closed = [r for r in records if r.net_pnl is not None]
    pnl = [r.net_pnl for r in closed if r.net_pnl is not None]
    wins, losses = [v for v in pnl if v > 0], [v for v in pnl if v < 0]
    profit, loss = _sum(wins), _sum(losses).copy_abs()
    net = _sum(pnl)
    average_win = _ratio(profit, Decimal(len(wins)))
    average_loss = _ratio(loss, Decimal(len(losses)))
    peak = balance = starting_balance
    max_dd = max_pct = Decimal(0)
    for r in closed:
        assert r.net_pnl is not None
        balance = _add(balance, r.net_pnl)
        peak = max(peak, balance)
        dd = _add(peak, balance.copy_negate())
        percent = _ratio(dd, peak)
        assert percent is not None
        max_dd = max(max_dd, dd)
        max_pct = max(max_pct, percent)
    ignored = sum(r.status == "SIGNAL_IGNORED_POSITION_OPEN" for r in records)
    rejected = [
        r
        for r in records
        if r.entry_timestamp is None and r.status != "SIGNAL_IGNORED_POSITION_OPEN"
    ]
    returned = _ratio(net, starting_balance)
    assert returned is not None
    win_rate = _ratio(Decimal(len(wins)), Decimal(len(closed)))
    # Decimal scaleb can round in ambient context; use a fixed reporting context.
    with localcontext() as context:
        context.prec = 50
        return PerformanceMetrics(
            starting_balance=starting_balance,
            ending_balance=balance,
            signals_generated=len(records),
            trade_plans_attempted=len(records) - ignored,
            trades_opened=sum(r.entry_timestamp is not None for r in records),
            trades_closed=len(closed),
            rejected_plans=len(rejected),
            rejection_reasons=dict(Counter(r.reason for r in rejected)),
            ignored_signals=ignored,
            no_valid_volume=sum(r.status == "NO_TRADE_RISK" for r in records),
            long_trades=sum(r.direction == PositionDirection.LONG for r in closed),
            short_trades=sum(r.direction == PositionDirection.SHORT for r in closed),
            wins=len(wins),
            losses=len(losses),
            breakeven=sum(v == 0 for v in pnl),
            win_rate_percent=win_rate * 100 if win_rate is not None else None,
            gross_profit=profit,
            gross_loss=loss,
            gross_trading_pnl=_sum(
                r.gross_pnl for r in closed if r.gross_pnl is not None
            ),
            commissions=_sum(r.commission for r in closed if r.commission is not None),
            net_pnl=net,
            return_percent=returned * 100,
            average_win=average_win,
            average_loss=average_loss,
            payoff_ratio=(
                _ratio(average_win, average_loss)
                if average_win is not None and average_loss is not None
                else None
            ),
            expectancy=_ratio(net, Decimal(len(closed))),
            profit_factor=_ratio(profit, loss),
            max_drawdown_usd=max_dd,
            max_drawdown_percent=max_pct * 100,
            largest_win=max(wins, default=None),
            largest_loss=min(losses, default=None),
            exit_reasons={
                status: sum(r.status == status for r in closed)
                for status in (
                    "CLOSED_STOP",
                    "CLOSED_TARGET",
                    "CLOSED_STOP_AMBIGUOUS",
                    "CLOSED_END_OF_RESEARCH_DAY",
                )
            },
            gap_risk_breaches=sum(r.risk_budget_breached for r in closed),
        )


class HistoricalResult(DomainModel):
    config: ResearchBacktestConfig
    backtest_version: Literal["xauusd-first-historical-v1"] = (
        "xauusd-first-historical-v1"
    )
    strategy_version: Literal["xauusd-trend-momentum-v1"] = "xauusd-trend-momentum-v1"
    feature_version: Literal["xauusd-baseline-features-v1"] = (
        "xauusd-baseline-features-v1"
    )
    records: tuple[SignalRecord, ...]
    decisions: tuple[DecisionAudit, ...]
    metrics: PerformanceMetrics
    months: dict[str, PerformanceMetrics]
    dataset_keys: tuple[str, ...]

    @property
    def report_identity(self) -> str:
        return content_hash(self.model_dump(mode="json"))


def run_historical(
    days: Iterable[ResearchDay], config: ResearchBacktestConfig
) -> HistoricalResult:
    """Opening pending entry -> completion protection/boundary close -> signal.

    Boundary schedules are fixed research policy inputs, never inferred by
    peeking at future bars. Unexpected missing observations fail, not carry.
    """
    config = ResearchBacktestConfig.model_validate(config.model_dump())
    balance = config.starting_balance
    records: list[SignalRecord] = []
    decisions: list[DecisionAudit] = []
    datasets: list[str] = []
    prior_end: datetime | None = None
    months: list[str] = []

    def update(index: int, **values: object) -> None:
        records[index] = SignalRecord.model_validate(
            records[index].model_dump() | values
        )

    def close_record(
        index: int,
        life: XAUUSDExecution,
        sizing: SizingResult,
        status: str,
        ambiguous: bool = False,
    ) -> None:
        nonlocal balance
        accounting = realize_usd(life, config.contract, config.commission)
        balance = _add(balance, accounting.net_usd)
        fill = life.fills[-1]
        breached = accounting.net_usd < sizing.risk_budget_usd.copy_negate()
        update(
            index,
            status=status,
            reason="RISK_BUDGET_EXCEEDED_BY_GAP" if breached else status,
            exit_timestamp=fill.timestamp,
            exit_fill=fill.executed_price,
            exit_fill_id=str(fill.execution_id),
            exit_source_id=fill.source_market_data_id,
            gross_pnl=accounting.gross_usd,
            commission=accounting.commission_usd,
            net_pnl=accounting.net_usd,
            balance_after=balance,
            risk_budget_breached=breached,
            intrabar_ambiguous=ambiguous,
        )

    for supplied in days:
        day = ResearchDay.model_validate(supplied.model_dump())
        ds = day.dataset
        if prior_end is not None and ds.start < prior_end:
            raise ValueError("research datasets must be nonoverlapping and ordered")
        if (
            ds.dataset_key in datasets
            or len(day.bars) != len(day.features)
            or not day.bars
        ):
            raise ValueError("duplicate or incomplete research dataset")
        prior_end = ds.end
        datasets.append(ds.dataset_key)
        if ds.source_month not in months:
            months.append(ds.source_month)
        boundaries = set(day.boundary_times)
        if ds.end not in boundaries or any(
            t.tzinfo is None or not ds.start < t <= ds.end for t in boundaries
        ):
            raise ValueError("explicit in-range UTC research boundaries required")
        pending: tuple[int, StructurePlan] | None = None
        active: (
            tuple[int, XAUUSDExecution, ProtectiveInstruction, SizingResult] | None
        ) = None
        history: deque[StructureBar] = deque(maxlen=12)
        previous: QuoteBar | None = None
        for bar, row in zip(day.bars, day.features, strict=True):
            if not ds.start <= bar.opening_timestamp < bar.closing_timestamp <= ds.end:
                raise ValueError("bar outside research dataset")
            if previous is None:
                if row.sequence_reset != "DATASET_BOUNDARY":
                    raise ValueError(
                        "persisted feature state must reset at dataset boundary"
                    )
            else:
                if bar.opening_timestamp <= previous.opening_timestamp:
                    raise ValueError("bars must be strictly chronological")
                if bar.opening_timestamp != previous.closing_timestamp:
                    if (
                        previous.closing_timestamp not in boundaries
                        or row.sequence_reset != "DISCONTINUITY"
                    ):
                        raise ValueError("unexpected data gap or missing feature reset")
                    history.clear()
                    if active is not None or pending is not None:
                        raise ValueError(
                            "position/plan carried across a research boundary"
                        )
            input_bar = QuoteBar.model_validate(
                {k: getattr(row.input, k) for k in QuoteBar.model_fields}
            )
            if (
                row.dataset_key != ds.dataset_key
                or input_bar != bar
                or row.policy_key != ds.gap_policy_key
            ):
                raise ValueError("persisted feature/bar provenance mismatch")
            if previous is not None and previous.closing_timestamp in boundaries:
                history.clear()
            source_id = f"{ds.dataset_key}:{bar.opening_timestamp.isoformat()}"
            monitored = False
            if pending is not None:
                index, structure = pending
                pending = None
                update(
                    index,
                    candidate_entry_timestamp=bar.opening_timestamp,
                    candidate_entry_bid=bar.bid_open,
                    candidate_entry_ask=bar.ask_open,
                    candidate_source_id=source_id,
                )
                if balance <= 0:
                    update(
                        index,
                        status="NO_TRADE_EQUITY",
                        reason="NONPOSITIVE_REALIZED_BALANCE",
                        balance_after=balance,
                    )
                else:
                    opening = MarketQuote(
                        canonical_symbol="XAUUSD",
                        timestamp=bar.opening_timestamp,
                        bid=bar.bid_open,
                        ask=bar.ask_open,
                    )
                    final = finalize_levels(
                        structure,
                        opening,
                        source_market_data_id=source_id,
                        contract=config.contract,
                        commission=config.commission,
                        account_equity=balance,
                        risk_fraction=config.risk_fraction,
                    )
                    if final.status != PlanningStatus.PLANNED:
                        update(
                            index,
                            status=final.status.value,
                            reason=final.reason,
                            balance_after=balance,
                        )
                    else:
                        assert final.trade_plan is not None
                        sim = simulate_trade(
                            final.trade_plan,
                            [SimulationBar(bar=bar, source_market_data_id=source_id)],
                            as_of=bar.closing_timestamp,
                        )
                        assert sim.sizing is not None
                        update(
                            index,
                            effective_stop=final.aligned_stop,
                            target=final.target,
                            risk_budget=sim.risk_budget,
                            planned_stop_risk=sim.projected_stop_risk,
                        )
                        if sim.entry_fill is None:
                            update(
                                index,
                                status=sim.status.value,
                                reason=sim.sizing.reason.value,
                                balance_after=balance,
                            )
                        else:
                            assert sim.protection is not None
                            update(
                                index,
                                entry_timestamp=sim.entry_fill.timestamp,
                                entry_fill=sim.entry_fill.executed_price,
                                entry_fill_id=str(sim.entry_fill.execution_id),
                                entry_source_id=source_id,
                                selected_volume=sim.volume,
                                status="OPEN",
                                reason="ENTERED",
                            )
                            if sim.lifecycle.status == "CLOSED":
                                close_record(
                                    index,
                                    sim.lifecycle,
                                    sim.sizing,
                                    sim.status.value,
                                    sim.evaluations[-1].intrabar_ambiguous,
                                )
                            else:
                                active = (
                                    index,
                                    sim.lifecycle,
                                    sim.protection,
                                    sim.sizing,
                                )
                            monitored = True
            if active is not None and not monitored:
                index, life, protection, sizing = active
                evaluation = evaluate_bar(
                    life,
                    protection,
                    bar,
                    evaluated_at=bar.closing_timestamp,
                    source_market_data_id=source_id,
                )
                if evaluation.lifecycle.status == "CLOSED":
                    status = (
                        "CLOSED_TARGET"
                        if evaluation.trigger == ProtectiveTrigger.TARGET_TRIGGERED
                        else (
                            "CLOSED_STOP_AMBIGUOUS"
                            if evaluation.intrabar_ambiguous
                            else "CLOSED_STOP"
                        )
                    )
                    close_record(
                        index,
                        evaluation.lifecycle,
                        sizing,
                        status,
                        evaluation.intrabar_ambiguous,
                    )
                    active = None
            if bar.closing_timestamp in boundaries and active is not None:
                index, life, _, sizing = active
                closing = MarketQuote(
                    canonical_symbol="XAUUSD",
                    timestamp=bar.closing_timestamp,
                    bid=bar.bid_close,
                    ask=bar.ask_close,
                )
                life = life.close(
                    closing,
                    timestamp=bar.closing_timestamp,
                    source_market_data_id=source_id,
                )
                close_record(index, life, sizing, "CLOSED_END_OF_RESEARCH_DAY")
                active = None
            history.append(
                StructureBar(
                    dataset=ds,
                    bar=bar,
                    discontinuity_before=row.sequence_reset is not None,
                )
            )
            decision = evaluate_xauusd(row, as_of=bar.closing_timestamp)
            key = content_hash(decision.model_dump(mode="json"))
            decisions.append(
                DecisionAudit(
                    timestamp=decision.available_at,
                    action=decision.action,
                    decision_key=key,
                )
            )
            if decision.side is not None:
                direction = (
                    PositionDirection.LONG
                    if decision.action == "BUY"
                    else PositionDirection.SHORT
                )
                record = SignalRecord(
                    decision_key=key,
                    strategy_version=decision.strategy_version,
                    dataset_key=ds.dataset_key,
                    research_date=ds.selected_source_date,
                    signal_timestamp=decision.available_at,
                    signal_opening=decision.opening_timestamp,
                    direction=direction,
                    signal_reasons=decision.reasons,
                    status="PENDING",
                    reason="STRUCTURE_PENDING",
                    balance_at_signal=balance,
                )
                records.append(record)
                index = len(records) - 1
                if active is not None:
                    update(
                        index,
                        status="SIGNAL_IGNORED_POSITION_OPEN",
                        reason="SIGNAL_IGNORED_POSITION_OPEN",
                        balance_after=balance,
                    )
                elif bar.closing_timestamp in boundaries:
                    update(
                        index,
                        status="NO_TRADE_RESEARCH_BOUNDARY",
                        reason="NO_ENTRY_ACROSS_RESEARCH_BOUNDARY",
                        balance_after=balance,
                    )
                else:
                    structure = plan_structure(
                        decision, tuple(history), as_of=decision.available_at
                    )
                    update(
                        index,
                        structural_stop=structure.structural_stop,
                        source_bar_identities=tuple(
                            item.source_identity for item in structure.source_bars
                        ),
                    )
                    if structure.status != PlanningStatus.PLANNED:
                        update(
                            index,
                            status=structure.status.value,
                            reason=structure.reason,
                            balance_after=balance,
                        )
                    else:
                        pending = (index, structure)
            previous = bar
        if (
            active is not None
            or pending is not None
            or day.bars[-1].closing_timestamp != ds.end
        ):
            raise ValueError(
                "incomplete day; do not invent an exit from truncated data"
            )
    frozen = tuple(records)
    metrics = summarize(frozen, config.starting_balance)
    monthly: dict[str, PerformanceMetrics] = {}
    month_balance = config.starting_balance
    for month in months:
        part = tuple(r for r in frozen if r.research_date.startswith(month))
        monthly[month] = summarize(part, month_balance)
        month_balance = monthly[month].ending_balance
    if balance != metrics.ending_balance or month_balance != balance:
        raise ValueError("realized balance reconciliation failed")
    if (
        metrics.signals_generated
        != metrics.trades_closed + metrics.rejected_plans + metrics.ignored_signals
    ):
        raise ValueError("unaccounted strategy signal")
    return HistoricalResult(
        config=config,
        records=frozen,
        decisions=tuple(decisions),
        metrics=metrics,
        months=monthly,
        dataset_keys=tuple(datasets),
    )
