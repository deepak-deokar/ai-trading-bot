"""Small local HistData tick pilot parser; no network, database or NSE calendar."""

import csv
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext

from pydantic import ValidationError

from trading_bot.domain.quotes import MarketQuote, QuoteSource

PROVIDER = "HISTDATA"
CANONICAL_SYMBOL = "XAUUSD"
PROVIDER_SYMBOL = "XAU/USD"
SOURCE_TIMEZONE = timezone(timedelta(hours=-5))


@dataclass(frozen=True)
class HistDataTick:
    quote: MarketQuote
    source_volume: str


@dataclass(frozen=True)
class PilotTicks:
    ticks: tuple[HistDataTick, ...]
    raw_count: int
    invalid_count: int
    crossed_count: int
    duplicate_timestamp_count: int
    rejected_lines: tuple[int, ...]


def parse_timestamp(value: str) -> datetime:
    if not re.fullmatch(r"\d{8} \d{9}", value):
        raise ValueError("expected HistData YYYYMMDD HHMMSSNNN timestamp")
    local = datetime(
        int(value[:4]),
        int(value[4:6]),
        int(value[6:8]),
        int(value[9:11]),
        int(value[11:13]),
        int(value[13:15]),
        int(value[15:18]) * 1000,
    )
    return local.replace(tzinfo=SOURCE_TIMEZONE).astimezone(UTC)


def parse_tick(line: str) -> HistDataTick:
    fields = next(csv.reader([line], strict=True))
    if len(fields) != 4:
        raise ValueError("expected timestamp,bid,ask,volume")
    timestamp, bid, ask, volume = fields
    try:
        bid_value, ask_value = Decimal(bid), Decimal(ask)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal price") from exc
    return HistDataTick(
        MarketQuote(
            canonical_symbol=CANONICAL_SYMBOL,
            timestamp=parse_timestamp(timestamp),
            bid=bid_value,
            ask=ask_value,
            source=QuoteSource.HISTORICAL_PROVIDER,
        ),
        volume,
    )


def read_pilot_day(lines: Iterable[str], pilot_day: date) -> PilotTicks:
    """Select one source-calendar weekday, preserving equal-time source order.

    Duplicate timestamp count is excess valid rows, not removed observations.
    Lines outside the selected date prefix are not analyzed as part of this pilot.
    """
    if pilot_day.weekday() >= 5:
        raise ValueError("pilot requires a weekday")
    prefix = pilot_day.strftime("%Y%m%d")
    ticks = []
    rejected = []
    raw = crossed = 0
    for line_number, line in enumerate(lines, 1):
        if not line.startswith(prefix):
            continue
        raw += 1
        try:
            tick = parse_tick(line)
        except (ValueError, InvalidOperation, ValidationError, csv.Error):
            rejected.append(line_number)
            try:
                fields = next(csv.reader([line], strict=True))
                bid, ask = Decimal(fields[1]), Decimal(fields[2])
                if bid.is_finite() and ask.is_finite() and bid > ask:
                    crossed += 1
            except (ValueError, InvalidOperation, IndexError, csv.Error):
                pass
        else:
            ticks.append(tick)
    ticks.sort(key=lambda tick: tick.quote.timestamp)
    counts = Counter(tick.quote.timestamp for tick in ticks)
    return PilotTicks(
        tuple(ticks),
        raw,
        len(rejected),
        crossed,
        sum(n - 1 for n in counts.values()),
        tuple(rejected),
    )


def five_minute_view(ticks: Iterable[HistDataTick]) -> list[dict[str, object]]:
    """Observed-only UTC opening bins; separate sides, no gap fill or persistence."""
    groups: dict[datetime, list[MarketQuote]] = {}
    for tick in sorted(ticks, key=lambda tick: tick.quote.timestamp):
        q = tick.quote
        opening = q.timestamp.replace(
            minute=q.timestamp.minute // 5 * 5, second=0, microsecond=0
        )
        groups.setdefault(opening, []).append(q)
    bars: list[dict[str, object]] = []
    for opening, quotes in groups.items():
        bar: dict[str, object] = {
            "timestamp": opening.isoformat(),
            "timestamp_convention": "open",
            "ticks": len(quotes),
        }
        for side in ("bid", "ask"):
            values = [getattr(q, side) for q in quotes]
            bar[side] = dict(
                open=values[0], high=max(values), low=min(values), close=values[-1]
            )
        bars.append(bar)
    return bars


def quality_statistics(pilot: PilotTicks) -> dict[str, object]:
    ticks = pilot.ticks
    if not ticks:
        raise ValueError("no valid pilot ticks")
    spreads = sorted(tick.quote.spread for tick in ticks)
    middle = len(spreads) // 2
    with localcontext() as context:
        context.prec = (
            max(s.adjusted() for s in spreads)
            - min(int(s.as_tuple().exponent) for s in spreads)
            + 3
        )
        median = (
            spreads[middle]
            if len(spreads) % 2
            else (spreads[middle - 1] + spreads[middle]) / Decimal(2)
        )
    max_gap = max(
        (
            b.quote.timestamp - a.quote.timestamp
            for a, b in zip(ticks, ticks[1:], strict=False)
        ),
        default=timedelta(0),
    )
    gap_ms = (
        max_gap.days * 86400 + max_gap.seconds
    ) * 1000 + max_gap.microseconds // 1000
    return {
        "raw_count": pilot.raw_count,
        "valid_count": len(ticks),
        "invalid_count": pilot.invalid_count,
        "crossed_quote_count": pilot.crossed_count,
        "duplicate_timestamp_count": pilot.duplicate_timestamp_count,
        "first_quote": ticks[0].quote.model_dump(mode="json"),
        "last_quote": ticks[-1].quote.model_dump(mode="json"),
        "spread_min": str(spreads[0]),
        "spread_median": str(median),
        "spread_max": str(spreads[-1]),
        "maximum_tick_gap_ms": gap_ms,
    }
