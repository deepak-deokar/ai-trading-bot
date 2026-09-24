"""Optional, data-only Groww historical candles transport and adapter.

Uses the documented equivalent of get_historical_candles, never order APIs.
A narrow stdlib transport avoids installing the SDK's trading/feed dependencies.
"""

import json
from collections.abc import Iterable
from datetime import timedelta
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import SecretStr

from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.providers.base import ProviderError, RawCandle
from trading_bot.data.providers.groww_semantics import (
    GrowwSemantics,
    ProviderSemanticsError,
)
from trading_bot.domain.market import AdjustmentType, Timeframe


class CandleClient(Protocol):
    def get_historical_candles(self, **kwargs: str) -> dict[str, Any]: ...


class GrowwHTTPClient:
    """One fixed HTTPS GET endpoint, no trading interface, bounded network timeout."""

    def __init__(self, token: SecretStr) -> None:
        if not token.get_secret_value().strip():
            raise ProviderError("Groww access token required")
        self._token = token

    def get_historical_candles(self, **kwargs: str) -> dict[str, Any]:
        request = Request(
            "https://api.groww.in/v1/historical/candles?" + urlencode(kwargs),
            headers={
                "Authorization": "Bearer " + self._token.get_secret_value(),
                "Accept": "application/json",
                "X-API-VERSION": "1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=30) as response:
                data = json.load(response, parse_float=Decimal)
            if not isinstance(data, dict) or data.get("status") != "SUCCESS":
                raise ProviderError("Groww historical request failed")
            payload = data.get("payload")
            if not isinstance(payload, dict):
                raise ProviderError("Groww historical payload is malformed")
            return payload
        except Exception:
            raise ProviderError("Groww historical request failed") from None


class GrowwProvider:
    name = "groww"

    def __init__(
        self,
        client: CandleClient,
        *,
        adjustment_type: AdjustmentType | None = None,
        timestamp_convention: str | None = None,
        semantics: GrowwSemantics | None = None,
    ) -> None:
        if semantics is None:
            raise ProviderSemanticsError("explicit complete Groww semantics required")
        if timestamp_convention not in (
            None,
            semantics.timestamp_meaning,
        ) or adjustment_type not in (None, semantics.adjustment_type):
            raise ProviderSemanticsError("conflicting Groww semantics configuration")
        self.client = client
        # Take an owned validated snapshot, independent of caller-owned dictionaries.
        self._semantics_json = GrowwSemantics.model_validate(
            semantics.model_dump()
        ).model_dump_json()
        self.adjustment_type = self.semantics.adjustment_type

    @property
    def semantics(self) -> GrowwSemantics:
        """Return a copy; mappings cannot mutate the adapter's recorded contract."""
        return GrowwSemantics.model_validate_json(self._semantics_json)

    def semantics_manifest(self) -> dict[str, Any]:
        return {
            **self.semantics.model_dump(mode="json"),
            "real_api_verification": "UNVERIFIED",
            "adapter_version": "groww-candles-v2",
        }

    @staticmethod
    def max_range(timeframe: Timeframe) -> timedelta:
        """Documented backtesting limits, checked 2026-09-23 (not legacy limits)."""
        if timeframe in (Timeframe.MIN_1, Timeframe.MIN_5):
            return timedelta(days=30)
        if timeframe in (Timeframe.MIN_10, Timeframe.MIN_15, Timeframe.MIN_30):
            return timedelta(days=90)
        return timedelta(days=180)

    def fetch_bars(self, request: HistoryRequest) -> Iterable[RawCandle]:
        """Preserve chunk boundaries for ingestion duplicate/conflict auditing."""
        mappings = {
            symbol: self.semantics.resolve(request, symbol)
            for symbol in request.symbols
        }
        row_number = 0
        for symbol in request.symbols:
            start = request.start
            while start < request.end:
                end = min(start + self.max_range(request.timeframe), request.end)
                try:
                    payload = self.client.get_historical_candles(
                        exchange=request.exchange.value,
                        segment=request.segment.value,
                        groww_symbol=mappings[symbol][0],
                        start_time=str(int(start.timestamp())),
                        end_time=str(int(end.timestamp())),
                        candle_interval=mappings[symbol][1],
                    )
                except Exception:
                    raise ProviderError("Groww historical request failed") from None
                minutes = payload.get("interval_in_minutes")
                if minutes is not None and minutes != int(
                    request.timeframe.duration.total_seconds() / 60
                ):
                    raise ProviderSemanticsError(
                        "Groww response interval contradicts request"
                    )
                candles = payload.get("candles")
                if not isinstance(candles, list):
                    raise ProviderError("Groww candle collection is malformed")
                for candle in candles:
                    row_number += 1
                    if not isinstance(candle, list) or len(candle) not in (6, 7):
                        yield RawCandle({}, row_number)
                        continue
                    timestamp = candle[0]
                    try:
                        timestamp = self.semantics.timestamp(timestamp)
                        # Normalize the inclusive provider end to [start, end).
                        if timestamp == request.end:
                            continue
                    except (ValueError, TypeError):
                        # Numeric/unknown formats must not fall through to Pydantic's
                        # automatic epoch parsing, which would guess vendor semantics.
                        yield RawCandle({}, row_number)
                        continue
                    values = dict(
                        zip(
                            (
                                "timestamp",
                                "open",
                                "high",
                                "low",
                                "close",
                                "volume",
                                "open_interest",
                            ),
                            candle,
                            strict=False,
                        )
                    )
                    values.update(timestamp=timestamp, symbol=symbol)
                    yield RawCandle(values, row_number)
                start = end
