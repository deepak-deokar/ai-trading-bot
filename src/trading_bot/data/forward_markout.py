"""Fixed-horizon research measurements; no orders, sizing or trade management."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.domain.market import utc
from trading_bot.domain.models import Side
from trading_bot.domain.quote_bars import QuoteBar


@dataclass(frozen=True)
class ForwardMarkout:
    horizon: int
    unavailable: str | None
    entry_timestamp: datetime | None = None
    ending_timestamp: datetime | None = None
    entry_price: Decimal | None = None
    markout: Decimal | None = None
    favorable: Decimal | None = None
    adverse: Decimal | None = None


def measure_forward(
    dataset: QuoteDataset,
    bars: Sequence[QuoteBar],
    *,
    signal_opening: datetime,
    side: Side,
    horizon: int,
    boundary_times: tuple[datetime, ...],
) -> ForwardMarkout:
    """Entry bar counts as bar 1; endpoint may equal, never cross, a boundary.

    Caller supplies bars from exactly the stated dataset. Missing windows return
    unavailable, never a shortened measurement. Excursions are nonnegative sizes.
    """
    signal_opening = utc(signal_opening)
    boundaries = tuple(utc(t) for t in boundary_times)
    if type(horizon) is not int or horizon not in (5, 10, 20):
        raise ValueError("only frozen horizons 5, 10, 20 are supported")
    if not isinstance(side, Side):
        raise ValueError("typed BUY/SELL side required")
    if dataset.end not in boundaries:
        raise ValueError("research-day end boundary required")
    if any(t <= dataset.start or t > dataset.end for t in boundaries):
        raise ValueError("boundary outside research day")
    if any(
        b.opening_timestamp < dataset.start or b.closing_timestamp > dataset.end
        for b in bars
    ) or any(
        a.opening_timestamp >= b.opening_timestamp
        for a, b in zip(bars, bars[1:], strict=False)
    ):
        raise ValueError("bars must belong to one ordered dataset day")
    index = next(
        (i for i, b in enumerate(bars) if b.opening_timestamp == signal_opening),
        None,
    )
    if index is None:
        raise ValueError("signal bar absent from dataset")
    completion = bars[index].closing_timestamp
    if completion in boundaries:
        return ForwardMarkout(horizon, "SIGNAL_AT_BOUNDARY")
    window = bars[index + 1 : index + 1 + horizon]
    if len(window) != horizon:
        return ForwardMarkout(horizon, "INCOMPLETE_HORIZON")
    expected = completion
    for bar in window:
        if bar.opening_timestamp != expected:
            return ForwardMarkout(horizon, "DISCONTINUITY")
        if any(expected <= t < bar.closing_timestamp for t in boundaries):
            return ForwardMarkout(horizon, "RESEARCH_BOUNDARY")
        expected = bar.closing_timestamp
    buy = side == Side.BUY
    entry = window[0].ask_open if buy else window[0].bid_open
    end = window[-1].bid_close if buy else window[-1].ask_close
    # QuoteBar bounds are 28 digits / 10 decimals; 60 digits retain exact differences.
    with localcontext() as context:
        context.prec = 60
        markout = end - entry if buy else entry - end
        favorable = (
            max(b.bid_high for b in window) - entry
            if buy
            else entry - min(b.ask_low for b in window)
        )
        adverse = (
            entry - min(b.bid_low for b in window)
            if buy
            else max(b.ask_high for b in window) - entry
        )
    return ForwardMarkout(
        horizon,
        None,
        completion,
        expected,
        entry,
        markout,
        max(Decimal(0), favorable),
        max(Decimal(0), adverse),
    )
