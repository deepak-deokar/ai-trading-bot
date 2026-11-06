"""Synthetic offline structure; no strategy simulation or parameter search."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.domain.contracts import ContractSpecification, SpecificationSource
from trading_bot.domain.models import Side
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote, QuoteSource
from trading_bot.execution.accounting import Commission, LinearUSDContract
from trading_bot.strategies.xauusd import XAUUSDSignalDecision
from trading_bot.strategies.xauusd_levels import (
    StructureBar,
    finalize_levels,
    plan_structure,
)

D = Decimal
T = datetime(2024, 2, 20, 10, tzinfo=UTC)
STEP = timedelta(minutes=5)


def dataset(**changes):
    values = dict(
        provider="test_fixture",
        provider_symbol="synthetic_gold",
        source_archive="synthetic",
        source_sha256="a" * 64,
        source_month="2024-02",
        selected_source_date="2024-02-20",
        start=T.replace(hour=5),
        end=T.replace(hour=5) + timedelta(days=1),
        source_timezone="fixed UTC-05:00",
        normalization_version="synthetic-v1",
        aggregation_version="synthetic-v1",
    )
    values.update(changes)
    return QuoteDataset(**values)


def bars(count=12):
    ds = dataset()
    return [
        StructureBar(
            dataset=ds,
            bar=QuoteBar(
                opening_timestamp=T + i * STEP,
                tick_count=10,
                bid_open=D("2000"),
                bid_close=D("2000"),
                bid_high=D("2004"),
                bid_low=D("1990") + D(i) / 10,
                ask_open=D("2001"),
                ask_close=D("2001"),
                ask_low=D("1991") + D(i) / 10,
                ask_high=D("2010") + D(i) / 10,
            ),
        )
        for i in range(count)
    ]


def decision(items, side=Side.BUY):
    last = items[-1]
    return XAUUSDSignalDecision(
        opening_timestamp=last.bar.opening_timestamp,
        available_at=last.bar.closing_timestamp,
        side=side,
        reasons=("SYNTHETIC_ALREADY_ISSUED_DECISION",),
        feature_snapshot=(),
        source_dataset_key=last.dataset.dataset_key,
        source_feature_version="synthetic",
        source_feature_row_hash="synthetic-feature-hash",
    )


def structure(items=None, side=Side.BUY):
    items = bars() if items is None else items
    sig = decision(items, side)
    return plan_structure(sig, items, as_of=sig.available_at)


def finalize(planned, bid="2001", ask="2002", tick="0.01", **changes):
    values = dict(
        source_market_data_id="synthetic:later-entry",
        contract=LinearUSDContract(
            specification=ContractSpecification(
                contract_size=D("10"),
                minimum_volume=D("0.25"),
                maximum_volume=D("2"),
                volume_step=D("0.25"),
                tick_size=D(tick),
                specification_source=SpecificationSource.TEST_FIXTURE,
            ),
            price_unit="USD_PER_TROY_OUNCE",
            contract_size_unit="TROY_OUNCES_PER_VOLUME_UNIT",
            quote_currency="USD",
            account_currency="USD",
        ),
        commission=Commission(currency="USD", fixed_round_trip_usd=D("1.25")),
        account_equity=D("500"),
        risk_fraction=D("0.05"),
    )
    values.update(changes)
    quote = MarketQuote(
        canonical_symbol="XAUUSD",
        timestamp=planned.decision.available_at,
        bid=D(bid),
        ask=D(ask),
        source=QuoteSource.TEST_FIXTURE,
    )
    return finalize_levels(planned, quote, **values)


@pytest.mark.parametrize(
    "side,stop,entry,distance,target",
    [
        (Side.BUY, "1990", "2002", "12", "2026"),
        (Side.SELL, "2011.1", "2001", "10.1", "1980.8"),
    ],
)
def test_side_structure_and_two_r(side, stop, entry, distance, target):
    planned = structure(side=side)
    assert planned.status == "PLANNED"
    assert planned.structural_stop == D(stop)
    assert planned.lookback == len(planned.source_bars) == 12
    assert planned.target_multiple == D("2")
    final = finalize(planned)
    assert final.status == "PLANNED"
    assert final.entry_quote.price_for_side(planned.direction.opening_side) == D(entry)
    assert final.sizing_request.stop_distance == D(distance)
    assert final.target == D(target)
    assert final.trade_plan.stop_price == D(stop)
    assert final.trade_plan.entry_timestamp == planned.decision.available_at
    assert final == finalize(planned)
    assert planned == structure(side=side)


def test_exact_twelve_no_old_outlier_or_future_access():
    items = bars(13)
    old = items[0].bar.model_copy(update={"bid_low": D("1")})
    items[0] = items[0].model_copy(update={"bar": old})
    sig = decision(items)
    expected = plan_structure(sig, items, as_of=sig.available_at)
    assert expected.structural_stop == D("1990.1")
    assert expected.source_bars == tuple(items[-12:])

    def guarded():
        yield from items
        raise AssertionError("planner must not request a future bar")

    assert plan_structure(sig, guarded(), as_of=sig.available_at) == expected
    future = bars(14)[-1]
    future = future.model_copy(
        update={"bar": future.bar.model_copy(update={"bid_low": D("0.01")})}
    )
    assert (
        plan_structure(sig, [*items, future], as_of=sig.available_at + STEP) == expected
    )


@pytest.mark.parametrize("count", [1, 5, 11])
def test_insufficient_structure(count):
    result = structure(bars(count))
    assert result.status == "NO_TRADE_INSUFFICIENT_STRUCTURE"
    assert result.structural_stop is None
    assert finalize(result).trade_plan is None


def test_gap_dataset_and_explicit_discontinuity():
    original = bars(13)
    for changed in (
        original[:5] + original[6:],
        [
            *original[:6],
            original[6].model_copy(update={"discontinuity_before": True}),
            *original[7:],
        ],
        [
            *original[:6],
            *[
                x.model_copy(update={"dataset": dataset(source_sha256="b" * 64)})
                for x in original[6:]
            ],
        ],
    ):
        assert structure(changed).status == "NO_TRADE_INSUFFICIENT_STRUCTURE"
    missing_signal = bars()
    sig = decision(missing_signal)
    assert (
        plan_structure(sig, missing_signal[:-1], as_of=sig.available_at).status
        == "NO_TRADE_INSUFFICIENT_STRUCTURE"
    )


def test_research_day_boundary_not_utc_midnight():
    changed = []
    for i, item in enumerate(bars()):
        opening = T.replace(hour=4, minute=30) + i * STEP
        ds = (
            dataset()
            if i >= 6
            else dataset(
                selected_source_date="2024-02-19",
                start=T.replace(day=19, hour=5),
                end=T.replace(hour=5),
            )
        )
        changed.append(
            StructureBar(
                dataset=ds,
                bar=item.bar.model_copy(update={"opening_timestamp": opening}),
            )
        )
    assert structure(changed).status == "NO_TRADE_INSUFFICIENT_STRUCTURE"


@pytest.mark.parametrize(
    "side,bid,ask",
    [
        (Side.BUY, "1989", "1990"),
        (Side.SELL, "2012", "2013"),
        # Even if entry side is valid, the current protective exit side must be valid.
        (Side.BUY, "1989", "1992"),
        (Side.SELL, "2010", "2013"),
    ],
)
def test_invalid_gap_rejected_before_alignment(side, bid, ask):
    final = finalize(structure(side=side), bid=bid, ask=ask, tick="1")
    assert final.status == "NO_TRADE_INVALID_STOP"
    assert final.aligned_stop is final.target is final.trade_plan is None


@pytest.mark.parametrize(
    "side,raw,aligned",
    [(Side.BUY, "1990.03", "1990.0"), (Side.SELL, "2011.13", "2011.2")],
)
def test_conservative_tick_alignment_and_precision(side, raw, aligned):
    items = bars()
    index, field = (0, "bid_low") if side == Side.BUY else (-1, "ask_high")
    items[index] = items[index].model_copy(
        update={"bar": items[index].bar.model_copy(update={field: D(raw)})}
    )
    planned = structure(items, side)
    with localcontext() as context:
        context.prec = 2
        final = finalize(planned, tick="0.1")
    assert final == finalize(planned, tick="0.1")
    assert final.aligned_stop == D(aligned)
    assert final.structure.structural_stop == D(raw)
    spec = final.sizing_request.contract.specification
    spec.validate_price(final.aligned_stop)
    spec.validate_price(final.target)
    if side == Side.BUY:
        assert final.aligned_stop <= D(raw)
        assert final.target <= final.raw_target
    else:
        assert final.aligned_stop >= D(raw)
        assert final.target >= final.raw_target


def test_off_grid_entry_rejected_and_nonpositive_short_target():
    assert (
        finalize(structure(), ask="2002.03", tick="0.1").status
        == "NO_TRADE_CONTRACT_ALIGNMENT"
    )
    assert (
        finalize(structure(side=Side.SELL), bid="100", ask="101").status
        == "NO_TRADE_INVALID_TARGET"
    )


def test_no_signal_validation_utc_decimal_and_causal_cutoff():
    items = bars()
    sig = decision(items)
    with pytest.raises(ValueError):
        plan_structure(sig, items, as_of=sig.available_at - timedelta(microseconds=1))
    with pytest.raises(ValueError):
        plan_structure(sig, items, as_of=sig.available_at.replace(tzinfo=None))
    assert structure(items, side=None).status == "NO_TRADE_SIGNAL"
    with pytest.raises(ValidationError):
        finalize(structure(), account_equity=500.0)
    forged = structure().model_copy(update={"structural_stop": D("1900")})
    with pytest.raises(ValueError):
        finalize(forged)
    with pytest.raises(ValidationError):
        structure().structural_stop = D("1999")
    with pytest.raises(ValueError):
        structure([items[1], items[0], *items[2:]])


def test_missing_or_wrong_signal_provenance_and_zero_aligned_stop():
    items = bars()
    sig = decision(items)
    assert (
        plan_structure(sig, [], as_of=sig.available_at).status
        == "NO_TRADE_INSUFFICIENT_STRUCTURE"
    )
    wrong = sig.model_copy(update={"source_dataset_key": "unrelated-dataset"})
    assert (
        plan_structure(wrong, items, as_of=sig.available_at).status
        == "NO_TRADE_INSUFFICIENT_STRUCTURE"
    )
    final = finalize(structure(), bid="2999", ask="3000", tick="3000")
    assert final.status == "NO_TRADE_CONTRACT_ALIGNMENT"
    assert final.reason == "ALIGNED_STOP_NOT_POSITIVE"


def test_entry_utc_and_no_entry_before_signal_completion():
    planned = structure()
    final = finalize(planned)
    quote = final.entry_quote.model_copy(
        update={"timestamp": planned.decision.available_at - STEP}
    )
    request = final.sizing_request
    with pytest.raises(ValueError):
        finalize_levels(
            planned,
            quote,
            source_market_data_id="synthetic:early",
            contract=request.contract,
            commission=request.commission,
            account_equity=request.account_equity,
            risk_fraction=request.risk_fraction,
        )
    with pytest.raises(ValidationError):
        MarketQuote(
            canonical_symbol="XAUUSD",
            timestamp=T.replace(tzinfo=None),
            bid=D("2000"),
            ask=D("2001"),
        )
    with pytest.raises(ValidationError):
        MarketQuote(canonical_symbol="XAUUSD", timestamp=T, bid=2000.0, ask=D("2001"))
