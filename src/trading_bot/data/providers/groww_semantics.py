"""Explicit vendor-to-domain interpretation; assertions are not live verification."""

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.providers.base import ProviderError
from trading_bot.domain.market import AdjustmentType, Timeframe


class ProviderSemanticsError(ProviderError):
    """Vendor data cannot be interpreted under a complete explicit contract."""


class GrowwSemantics(BaseModel):
    """All mappings must be supplied. No inferred timezone, adjustment or identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    timestamp_meaning: Literal["open"]
    timezone: Literal["Asia/Kolkata"]
    adjustment_type: AdjustmentType
    interval_mapping: dict[Timeframe, str] = Field(min_length=1)
    # Keys are generic exchange:segment:symbol; values are provider identifiers.
    instrument_mapping: dict[str, str] = Field(min_length=1)
    acknowledgement: Literal["UNVERIFIED_PROVIDER_SEMANTICS_ACCEPTED"]

    @model_validator(mode="after")
    def valid_mappings(self) -> "GrowwSemantics":
        for timeframe, label in self.interval_mapping.items():
            if label != timeframe.value:
                raise ValueError(
                    "interval mapping contradicts documented Groww intervals"
                )
        for key, value in self.instrument_mapping.items():
            parts = key.split(":")
            if len(parts) != 3 or parts[:2] != ["NSE", "CASH"] or not parts[2]:
                raise ValueError("instrument key must be NSE:CASH:SYMBOL")
            if value != f"NSE-{parts[2]}":
                raise ValueError("instrument mapping contradicts NSE CASH identity")
        return self

    def resolve(self, request: HistoryRequest, symbol: str) -> tuple[str, str]:
        """Fail before network access if any requested mapping is absent."""
        if request.adjustment_type != self.adjustment_type:
            raise ProviderSemanticsError("Groww adjustment policy differs from request")
        try:
            return (
                self.instrument_mapping[
                    f"{request.exchange}:{request.segment}:{symbol}"
                ],
                self.interval_mapping[request.timeframe],
            )
        except KeyError:
            raise ProviderSemanticsError(
                "Groww instrument/interval mapping missing"
            ) from None

    def timestamp(self, value: str) -> datetime:
        """Naive vendor wall times use the explicitly asserted exchange timezone."""
        timestamp = datetime.fromisoformat(value)
        zone = ZoneInfo(self.timezone)
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=zone)
        return timestamp.astimezone(zone)
