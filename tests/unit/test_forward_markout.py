from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from decimal import localcontext

import pytest

from trading_bot.data.forward_markout import measure_forward
from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.domain.models import Side
from trading_bot.domain.quote_bars import QuoteBar

T = datetime(2024, 2, 1, 5, tzinfo=UTC)
STEP = timedelta(minutes=5)
DS = QuoteDataset(
    provider="test_fixture",
    provider_symbol="gold",
    source_archive="synthetic",
    source_sha256="a" * 64,
    source_month="2024-02",
    selected_source_date="2024-02-01",
    start=T,
    end=T + 30 * STEP,
    source_timezone="fixed UTC-05:00",
    normalization_version="synthetic",
    aggregation_version="synthetic",
)


def bars():
    return tuple(
        QuoteBar(
            opening_timestamp=T + i * STEP,
            bid_open=D("100.123"),
            ask_open=D("100.323"),
            bid_high=D("102"),
            ask_high=D("102.2"),
            bid_low=D("99"),
            ask_low=D("99.2"),
            bid_close=D("101"),
            ask_close=D("101.2"),
            tick_count=1,
        )
        for i in range(30)
    )


def run(data=None, side=Side.BUY, horizon=5, **changes):
    args = dict(signal_opening=T, side=side, horizon=horizon, boundary_times=(DS.end,))
    args.update(changes)
    return measure_forward(DS, bars() if data is None else data, **args)


@pytest.mark.parametrize(
    "side,entry,markout,favorable,adverse",
    [
        (Side.BUY, "100.323", "0.677", "1.677", "1.323"),
        (Side.SELL, "100.123", "-1.077", "0.923", "2.077"),
    ],
)
def test_exact_sides_and_horizon(side, entry, markout, favorable, adverse):
    with localcontext() as ctx:
        ctx.prec = 2
        result = run(side=side)
    assert result.entry_price == D(entry)
    assert result.markout == D(markout)
    assert result.favorable == D(favorable) and result.adverse == D(adverse)
    assert result.entry_timestamp == T + STEP
    assert result.ending_timestamp == T + 6 * STEP


@pytest.mark.parametrize("horizon", [5, 10, 20])
def test_suffix_mutation_cannot_change_horizon(horizon):
    source = bars()
    changed = list(source)
    for i in range(horizon + 1, len(changed)):
        changed[i] = changed[i].model_copy(
            update={"bid_high": D("9999"), "ask_high": D("10000")}
        )
    assert run(source, horizon=horizon) == run(changed, horizon=horizon)
    changed[0] = changed[0].model_copy(update={"ask_open": D("500")})
    assert run(source, horizon=horizon) == run(changed, horizon=horizon)


def test_no_shortening_or_gap_crossing():
    assert run(bars()[:5]).unavailable == "INCOMPLETE_HORIZON"
    assert run(bars()[:3] + bars()[4:]).unavailable == "DISCONTINUITY"
    assert run(boundary_times=(T + 3 * STEP, DS.end)).unavailable == "RESEARCH_BOUNDARY"
    assert run(boundary_times=(T + STEP, DS.end)).unavailable == "SIGNAL_AT_BOUNDARY"
    assert run(boundary_times=(T + 6 * STEP, DS.end)).unavailable is None
    assert run(signal_opening=T + 29 * STEP).unavailable == "SIGNAL_AT_BOUNDARY"


def test_validation_and_repeated_independent_measurement():
    for kwargs in (
        {"horizon": 6},
        {"signal_opening": T.replace(tzinfo=None)},
        {"boundary_times": ()},
    ):
        with pytest.raises(ValueError):
            run(**kwargs)
    with pytest.raises(ValueError):
        run(tuple(reversed(bars())))
    with pytest.raises(ValueError):
        run(bars() + (bars()[-1].model_copy(update={"opening_timestamp": DS.end}),))
    assert run() == run()
    assert run(signal_opening=T + STEP).entry_timestamp == T + 2 * STEP


def test_inversion_recomputes_source_sides_not_negated_markout():
    original_buy = run(side=Side.BUY)
    original_sell = run(side=Side.SELL)
    assert original_buy.entry_price == D("100.323")
    assert original_sell.entry_price == D("100.123")
    assert original_sell.markout == D("-1.077")
    assert original_buy.markout == D("0.677")
    assert original_buy.markout != -original_sell.markout
    # Opposite markouts sum to minus the sum of entry and endpoint spreads.
    assert original_buy.markout + original_sell.markout == D("-0.4")
    assert original_buy.entry_timestamp == original_sell.entry_timestamp
    assert original_buy.ending_timestamp == original_sell.ending_timestamp


@pytest.mark.parametrize("horizon", [5, 10, 20])
def test_inverted_directions_share_unavailable_window(horizon):
    source = bars()[:3] + bars()[4:]
    assert run(source, Side.BUY, horizon).unavailable == "DISCONTINUITY"
    assert run(source, Side.SELL, horizon).unavailable == "DISCONTINUITY"
