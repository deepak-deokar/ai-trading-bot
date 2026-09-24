"""Raw provider boundary keeps vendor payloads outside domain models."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from trading_bot.data.contracts import HistoryRequest


class ProviderError(Exception):
    """Sanitized provider failure; never attach vendor messages or credentials."""


@dataclass(frozen=True)
class RawCandle:
    """Adapter contract: timestamp is an opening, never a closing label.

    External formats must be interpreted before yielding this record. Declaring
    another convention causes normalization to reject the row, not shift it.
    """

    values: dict[str, Any]
    row_number: int
    timestamp_convention: Literal["open"] = "open"


class HistoricalDataProvider(Protocol):
    name: str

    def fetch_bars(self, request: HistoryRequest) -> Iterable[RawCandle]:
        """Yield source rows, including invalid rows for auditable rejection."""
        ...


@runtime_checkable
class SemanticsProvider(Protocol):
    """Optional structured provenance contract, independent of any vendor."""

    def semantics_manifest(self) -> dict[str, Any]: ...
