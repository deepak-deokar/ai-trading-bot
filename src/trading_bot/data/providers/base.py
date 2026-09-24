"""Raw provider boundary keeps vendor payloads outside domain models."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from trading_bot.data.contracts import HistoryRequest


class ProviderError(Exception):
    """Sanitized provider failure; never attach vendor messages or credentials."""


@dataclass(frozen=True)
class RawCandle:
    values: dict[str, Any]
    row_number: int


class HistoricalDataProvider(Protocol):
    name: str

    def fetch_bars(self, request: HistoryRequest) -> Iterable[RawCandle]:
        """Yield source rows, including invalid rows for auditable rejection."""
        ...
