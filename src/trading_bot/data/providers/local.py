"""Strict CSV structure; individual value errors are rejected by normalization."""

import csv
from collections.abc import Iterable
from pathlib import Path

from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.providers.base import ProviderError, RawCandle


class LocalCSVProvider:
    name = "local"
    required = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
    optional = {
        "timestamp_convention",
        "exchange",
        "segment",
        "timeframe",
        "adjustment_type",
        "trade_count",
        "open_interest",
        "vwap",
    }

    def __init__(self, path: Path) -> None:
        self.path = path

    def fetch_bars(self, request: HistoryRequest) -> Iterable[RawCandle]:
        """File describes exactly the requested dataset; extra rows are not hidden."""
        try:
            with self.path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle, strict=True)
                fields = reader.fieldnames
                if (
                    not fields
                    or len(set(fields)) != len(fields)
                    or not self.required.issubset(fields)
                    or set(fields) - self.required - self.optional
                ):
                    raise ProviderError("CSV header does not match the candle schema")
                for number, row in enumerate(reader, 2):
                    if None in row or any(value is None for value in row.values()):
                        raise ProviderError("CSV row has an incorrect column count")
                    yield RawCandle(dict(row), number)
        except (OSError, UnicodeError, csv.Error):
            raise ProviderError("CSV could not be read or parsed") from None
