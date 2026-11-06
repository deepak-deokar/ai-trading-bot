"""Synthetic end-to-end strategy decisions, orchestration and realized statistics."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.data.research_input import ResearchFeatureInput
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.execution.research_backtest import (
    ResearchBacktestConfig,
    ResearchDay,
    run_historical,
    summarize,
)
from trading_bot.features.xauusd import FeatureValue, XAUUSDFeatureRow

D = Decimal
T = datetime(2024, 2, 20, 10, tzinfo=UTC)
STEP = timedelta(minutes=5)


def config(risk="0.05"):
    base = ResearchBacktestConfig.model_validate_json(
        Path("config/xauusd_first_backtest.json").read_text()
    )
    return base.model_copy(update={"risk_fraction": D(risk)})


def day(side="BUY", changes=None, signals=(11,), start=T, gap=False):
    ds = QuoteDataset(
        provider="test_fixture",
        provider_symbol="synthetic_gold",
        source_archive="synthetic",
        source_sha256="a" * 64,
        source_month=start.strftime("%Y-%m"),
        selected_source_date=start.date().isoformat(),
        start=start,
        end=start + 24 * STEP,
        source_timezone="UTC",
        normalization_version="synthetic",
        aggregation_version="synthetic",
        gap_policy_version="synthetic-policy",
        gap_policy_key="b" * 64,
    )
    bars, rows = [], []
    previous = None
    for i in range(24):
        if gap and i in (16, 17):
            continue
        values = dict(
            opening_timestamp=start + i * STEP,
            tick_count=10,
            bid_open=D("2000"),
            bid_high=D("2002"),
            bid_low=D("1999"),
            bid_close=D("2000"),
            ask_open=D("2001"),
            ask_high=D("2003"),
            ask_low=D("2000"),
            ask_close=D("2001"),
        )
        if i == 0:
            values.update(bid_low=D("1995"), ask_high=D("2005"))
        values.update({k: D(v) for k, v in (changes or {}).get(i, {}).items()})
        bar = QuoteBar(**values)
        features = dict(
            ema_12="2002",
            ema_26="2000",
            ema_difference="2",
            momentum_3="1",
            rsi_14="60",
            spread_close="0.3",
            relative_spread="0.00015",
        )
        if side == "SELL":
            features.update(
                ema_12="1998", ema_difference="-2", momentum_3="-1", rsi_14="40"
            )
        if i not in signals:
            features.update(ema_12="2000", ema_difference="0")
        row = XAUUSDFeatureRow(
            dataset_key=ds.dataset_key,
            policy_key=ds.gap_policy_key,
            input=ResearchFeatureInput(
                **bar.model_dump(), previous_observed_timestamp=previous
            ),
            sequence_reset=(
                "DATASET_BOUNDARY"
                if i == 0
                else "DISCONTINUITY" if gap and i == 18 else None
            ),
            values=tuple(FeatureValue(name=k, value=D(v)) for k, v in features.items()),
        )
        bars.append(bar)
        rows.append(row)
        previous = bar.opening_timestamp
    return ResearchDay(
        dataset=ds,
        bars=tuple(bars),
        features=tuple(rows),
        boundary_times=(start + 16 * STEP, ds.end) if gap else (ds.end,),
    )


@pytest.mark.parametrize(
    "side,change,status,entry,exit_price",
    [
        (
            "BUY",
            {"bid_high": "2014", "ask_high": "2015"},
            "CLOSED_TARGET",
            "2001",
            "2013",
        ),
        ("BUY", {"bid_low": "1995", "ask_low": "1996"}, "CLOSED_STOP", "2001", "1995"),
        (
            "SELL",
            {"bid_low": "1989", "ask_low": "1990"},
            "CLOSED_TARGET",
            "2000",
            "1990",
        ),
        (
            "SELL",
            {"bid_high": "2004", "ask_high": "2005"},
            "CLOSED_STOP",
            "2000",
            "2005",
        ),
        (
            "BUY",
            {
                "bid_low": "1994",
                "ask_low": "1995",
                "bid_high": "2014",
                "ask_high": "2015",
            },
            "CLOSED_STOP_AMBIGUOUS",
            "2001",
            "1995",
        ),
    ],
)
def test_signal_to_entry_exit_and_accounting(side, change, status, entry, exit_price):
    result = run_historical([day(side, {14: change})], config())
    record = result.records[0]
    assert record.status == status
    assert record.entry_timestamp == T + 12 * STEP
    assert record.entry_timestamp > record.signal_opening
    assert record.entry_fill == D(entry)
    assert record.exit_fill == D(exit_price)
    assert record.commission == D("1.25")
    assert record.net_pnl == record.gross_pnl - record.commission
    assert result.metrics.ending_balance == D("500") + record.net_pnl
    assert record.balance_after == result.metrics.ending_balance
    assert record.planned_stop_risk <= record.risk_budget
    assert record.intrabar_ambiguous == (status == "CLOSED_STOP_AMBIGUOUS")
    assert result == run_historical([day(side, {14: change})], config())
    assert (
        result.report_identity
        == run_historical([day(side, {14: change})], config()).report_identity
    )


def test_risk_rejections_and_gap_breach():
    denied = run_historical([day()], config("0.001"))
    assert denied.records[0].status == "NO_TRADE_RISK"
    assert denied.metrics.no_valid_volume == 1
    assert denied.metrics.trades_opened == 0
    assert denied.metrics.ending_balance == D("500")
    gap = {"bid_open": "1990", "bid_low": "1990", "ask_open": "1991", "ask_low": "1991"}
    result = run_historical([day(changes={14: gap})], config())
    record = result.records[0]
    assert record.exit_fill == D("1990")
    assert record.net_pnl == D("-28.75")
    assert record.risk_budget_breached
    assert result.metrics.gap_risk_breaches == 1
    invalid = run_historical([day(changes={12: gap})], config())
    assert invalid.records[0].status == "NO_TRADE_INVALID_STOP"


def test_one_position_and_day_or_provider_gap_boundary():
    for with_gap in (False, True):
        result = run_historical([day(signals=(11, 12, 13, 23), gap=with_gap)], config())
        trade = result.records[0]
        assert trade.status == "CLOSED_END_OF_RESEARCH_DAY"
        assert trade.exit_timestamp == T + (16 if with_gap else 24) * STEP
        assert trade.exit_fill == D("2000")
        assert result.metrics.ignored_signals == 2
        assert result.metrics.trades_closed == 1
        assert result.metrics.signals_generated == 4
        assert result.metrics.rejected_plans == 1
        assert result.records[-1].status == "NO_TRADE_RESEARCH_BOUNDARY"


def test_next_trade_equity_and_month_continuity():
    feb = day(changes={14: {"bid_high": "2014", "ask_high": "2015"}})
    march = day(start=T.replace(month=3))
    result = run_historical([feb, march], config())
    first, second = result.records
    assert second.balance_at_signal == first.balance_after
    assert second.risk_budget == first.balance_after * D("0.05")
    assert (
        result.months["2024-03"].starting_balance
        == result.months["2024-02"].ending_balance
    )
    assert result.months["2024-03"].ending_balance == result.metrics.ending_balance


def test_drawdown_and_statistics_independent_known_sequence():
    base = run_historical([day()], config()).records[0]
    pnl = [D("10"), D("-5"), D("0"), D("-20"), D("15")]
    records = tuple(
        base.model_copy(
            update={"net_pnl": value, "gross_pnl": value, "commission": D(0)}
        )
        for value in pnl
    )
    m = summarize(records, D("500"))
    assert (m.wins, m.losses, m.breakeven) == (2, 2, 1)
    assert m.win_rate_percent == D("40")
    assert m.gross_profit == m.gross_loss == D("25")
    assert m.net_pnl == m.expectancy == D("0")
    assert m.average_win == m.average_loss == D("12.5")
    assert m.payoff_ratio == m.profit_factor == D("1")
    assert m.max_drawdown_usd == D("25")
    assert abs(m.max_drawdown_percent - D("4.901960784313725490196078431")) < D(
        "0.000000000000000000000001"
    )
    assert m.largest_win == D("15") and m.largest_loss == D("-20")


def test_end_to_end_future_mutation_preserves_closed_prefix():
    early = {14: {"bid_high": "2014", "ask_high": "2015"}}
    original = run_historical([day(changes=early, signals=(11, 18))], config())
    changed = day(
        changes=early | {20: {"bid_high": "9999", "ask_high": "10000"}},
        signals=(11, 19, 20),
    )
    later = run_historical([changed], config())
    cutoff = T + 15 * STEP
    assert original.records[0] == later.records[0]
    assert tuple(d for d in original.decisions if d.timestamp <= cutoff) == tuple(
        d for d in later.decisions if d.timestamp <= cutoff
    )
    assert original.records[0].balance_after == later.records[0].balance_after


def test_every_signal_including_structure_and_alignment_failure_accounted():
    data = day(signals=(5, 11, 23), changes={12: {"ask_open": "2001.001"}})
    result = run_historical([data], config())
    assert [r.status for r in result.records] == [
        "NO_TRADE_INSUFFICIENT_STRUCTURE",
        "NO_TRADE_CONTRACT_ALIGNMENT",
        "NO_TRADE_RESEARCH_BOUNDARY",
    ]
    assert result.metrics.signals_generated == result.metrics.rejected_plans == 3


def test_no_size_from_nonpositive_balance():
    # Extreme synthetic gap deliberately exhausts the account, without clipping.
    data = day(
        changes={
            14: {"bid_open": "1", "bid_low": "1", "ask_open": "2", "ask_low": "2"}
        },
        signals=(11, 20),
    )
    result = run_historical([data], config())
    assert result.records[0].balance_after < 0
    assert result.records[1].status == "NO_TRADE_EQUITY"
    assert result.records[1].entry_fill is None


def test_unexpected_gap_and_missing_boundary_fail():
    data = day()
    with pytest.raises(ValueError):
        run_historical([data.model_copy(update={"boundary_times": ()})], config())
    with pytest.raises(ValueError):
        run_historical(
            [
                data.model_copy(
                    update={
                        "bars": data.bars[:16] + data.bars[17:],
                        "features": data.features[:16] + data.features[17:],
                    }
                )
            ],
            config(),
        )
