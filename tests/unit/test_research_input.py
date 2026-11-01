"""Synthetic offline input semantics; no indicators or historical DB writes."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from trading_bot.data.gap_policy import DayType, load_gap_policy
from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.data.research_input import (
    AnalyticalPriceBasis,
    ResearchFeatureInput,
    approved_research_inputs,
    completed_input,
)
from trading_bot.database.models import BidAskBar
from trading_bot.domain.models import Side
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote

POLICY = load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml"))
START = datetime(2024, 2, 20, 5, tzinfo=UTC)


def bar(opening=START):
    return QuoteBar(
        opening_timestamp=opening,
        tick_count=7,
        bid_open=Decimal("2000.1"),
        bid_high=Decimal("2003"),
        bid_low=Decimal("1998"),
        bid_close=Decimal("2001.1234567890"),
        ask_open=Decimal("2000.3"),
        ask_high=Decimal("2004"),
        ask_low=Decimal("1999"),
        ask_close=Decimal("2001.1234567891"),
    )


def fixture(day="2024-02-20"):
    start = datetime.fromisoformat(day).replace(hour=5, tzinfo=UTC)
    ds = QuoteDataset(
        provider="HISTDATA",
        provider_symbol="XAU/USD",
        source_archive="synthetic.zip",
        source_sha256=POLICY.segments[1].evidence.archive_sha256,
        source_month="2024-02",
        selected_source_date=day,
        start=start,
        end=start + timedelta(days=1),
        source_timezone=POLICY.source_timezone,
        normalization_version="histdata-ticks-v1",
        aggregation_version="bid-ask-utc-5minute-v1",
        gap_policy_version=POLICY.policy_version,
        gap_policy_key=POLICY.policy_key,
    )
    bars = tuple(
        bar(start + timedelta(minutes=5 * i))
        for i in range(288)
        if i not in range(204, 216)
    )
    return ds, bars


def test_preservation_exact_derivations_and_no_invented_extrema():
    b = bar()
    with localcontext() as ctx:
        ctx.prec = 6
        item = completed_input(b, as_of=START + timedelta(minutes=5))
        assert item.spread_open == Decimal("0.2")
        assert item.spread_close == Decimal("0.0000000001")
        assert item.mid_close == Decimal("2001.12345678905")
    for name in QuoteBar.model_fields:
        assert getattr(item, name) == getattr(b, name)
    assert item.exact_spread_min is None and item.exact_spread_max is None
    assert not hasattr(item, "mid_high") and not hasattr(item, "mid_low")
    for basis, expected in [
        (AnalyticalPriceBasis.BID, b.bid_close),
        (AnalyticalPriceBasis.ASK, b.ask_close),
        (AnalyticalPriceBasis.MID_CLOSE, item.mid_close),
    ]:
        assert item.analytical_close(basis) == expected
    with pytest.raises(ValidationError):
        ResearchFeatureInput(**b.model_dump(), exact_spread_min=Decimal("0"))
    with pytest.raises(ValidationError):
        item.tick_count = 8


@pytest.mark.parametrize(
    "field",
    [
        "bid_open",
        "bid_high",
        "bid_low",
        "bid_close",
        "ask_open",
        "ask_high",
        "ask_low",
        "ask_close",
    ],
)
def test_float_rejection(field):
    data = bar().model_dump()
    data[field] = float(data[field])
    with pytest.raises(ValidationError):
        ResearchFeatureInput(**data)


def test_completion_and_utc():
    b = bar()
    with pytest.raises(ValueError):
        completed_input(b, as_of=START + timedelta(minutes=5, microseconds=-1))
    with pytest.raises(ValueError):
        completed_input(b, as_of=START.replace(tzinfo=None))
    with pytest.raises(ValueError):
        completed_input(
            b,
            as_of=START + timedelta(minutes=5),
            previous_observed_timestamp=START.replace(tzinfo=None),
        )
    data = b.model_dump() | {"opening_timestamp": START.replace(tzinfo=None)}
    with pytest.raises(ValidationError):
        ResearchFeatureInput(**data)
    item = completed_input(
        b,
        as_of=(START + timedelta(minutes=5)).astimezone(
            timezone(timedelta(hours=5, minutes=30))
        ),
    )
    assert item.available_at == START + timedelta(minutes=5)
    assert item.opening_timestamp == START
    assert item.discontinuity is None


def test_approved_gap_cutoff_and_no_fill():
    ds, bars = fixture()
    result = approved_research_inputs(ds, bars, POLICY, as_of=ds.end)
    assert len(result.inputs) == 276
    assert result.inputs[1].elapsed_since_previous == timedelta(minutes=5)
    assert result.inputs[1].discontinuity is False
    after_gap = next(i for i in result.inputs if i.opening_timestamp.hour == 23)
    assert after_gap.previous_observed_timestamp.hour == 21
    assert after_gap.previous_observed_timestamp.minute == 55
    assert after_gap.elapsed_since_previous == timedelta(minutes=65)
    assert after_gap.discontinuity is True
    assert all(i.opening_timestamp.hour != 22 for i in result.inputs)
    assert approved_research_inputs(ds, bars, POLICY, as_of=ds.start).inputs == ()
    partial = approved_research_inputs(
        ds, bars, POLICY, as_of=ds.start + timedelta(minutes=5)
    )
    assert len(partial.inputs) == 1 and partial.inputs[0] == result.inputs[0]
    changed = bars[:-1] + (bars[-1].model_copy(update={"tick_count": 999}),)
    assert (
        approved_research_inputs(
            ds, changed, POLICY, as_of=ds.start + timedelta(minutes=5)
        ).inputs
        == partial.inputs
    )


@pytest.mark.parametrize("day", ["2024-02-19", "2024-02-23"])
def test_excluded_days(day):
    ds, bars = fixture(day)
    with pytest.raises(ValueError, match="EXCLUDED_DAY_TYPE"):
        approved_research_inputs(ds, bars, POLICY, as_of=ds.end)


def test_policy_and_order_boundaries():
    ds, bars = fixture()
    for altered in [
        ds.model_copy(update={"gap_policy_key": None, "gap_policy_version": None}),
        ds.model_copy(update={"source_sha256": "a" * 64}),
    ]:
        with pytest.raises(ValueError):
            approved_research_inputs(altered, bars, POLICY, as_of=ds.end)
    with pytest.raises(ValueError):
        approved_research_inputs(
            ds, bars, POLICY, as_of=ds.end, day_type=DayType.UNEXPLAINED
        )
    with pytest.raises(ValueError):
        approved_research_inputs(ds, tuple(reversed(bars)), POLICY, as_of=ds.end)
    with pytest.raises(ValueError):
        approved_research_inputs(ds, bars[:-1], POLICY, as_of=ds.end)


def test_orm_adapter_and_execution_separation():
    ds, bars = fixture()
    rows = tuple(
        BidAskBar(
            **b.model_dump(),
            dataset_key=ds.dataset_key,
            provider=ds.provider,
            provider_symbol=ds.provider_symbol,
        )
        for b in bars
    )
    output = approved_research_inputs(ds, rows, POLICY, as_of=ds.end)
    assert output.inputs[0].bid_close == bars[0].bid_close
    rows[0].dataset_key = "wrong"
    with pytest.raises(ValueError):
        approved_research_inputs(ds, rows, POLICY, as_of=ds.end)
    item = output.inputs[0]
    q = MarketQuote(
        canonical_symbol="XAUUSD",
        timestamp=item.available_at,
        bid=item.bid_close,
        ask=item.ask_close,
    )
    assert q.price_for_side(Side.BUY) == item.ask_close
    assert q.price_for_side(Side.SELL) == item.bid_close
    assert q.price_for_side(Side.BUY) != item.mid_close
    assert q.price_for_side(Side.SELL) != item.mid_close
