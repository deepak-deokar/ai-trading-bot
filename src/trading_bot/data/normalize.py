"""Lossless conversion of provider scalars into validated opening-time bars."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.providers.base import RawCandle
from trading_bot.domain.models import Bar


def integer(value: object) -> int:
    """Reject bools, fractions, exponents, and rounded floating-point quantities."""
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value):
        return int(value)
    raise ValueError("integer required")


def normalize(row: RawCandle, request: HistoryRequest, source: str) -> Bar:
    """Naive local timestamps are invalid; only vendor adapter may interpret them."""
    values: dict[str, Any] = dict(row.values)
    for key, default in {
        "exchange": request.exchange,
        "segment": request.segment,
        "timeframe": request.timeframe,
        "adjustment_type": request.adjustment_type,
    }.items():
        if not values.get(key):
            values[key] = default
    values["source"] = source
    for key in ("open", "high", "low", "close", "vwap"):
        if values.get(key) not in (None, ""):
            values[key] = Decimal(str(values[key]))
        elif key == "vwap":
            values.pop(key, None)
    for key in ("volume", "trade_count", "open_interest"):
        if values.get(key) not in (None, ""):
            values[key] = integer(values[key])
        elif key != "volume":
            values.pop(key, None)
    if isinstance(values.get("timestamp"), str):
        values["timestamp"] = datetime.fromisoformat(values["timestamp"])
    bar = Bar.model_validate(values)
    if (
        bar.exchange != request.exchange
        or bar.segment != request.segment
        or bar.symbol not in request.symbols
        or bar.timeframe != request.timeframe
        or bar.adjustment_type != request.adjustment_type
    ):
        raise ValueError("candle identity differs from request")
    return bar
