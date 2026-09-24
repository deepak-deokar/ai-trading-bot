"""Optional, data-only Groww historical candles transport and adapter.

Uses the documented equivalent of get_historical_candles, never order APIs.
A narrow stdlib transport avoids installing the SDK's trading/feed dependencies.
"""

import json
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import SecretStr

from trading_bot.data.calendar import IST
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.providers.base import ProviderError, RawCandle
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
        adjustment_type: AdjustmentType,
        timestamp_convention: str,
    ) -> None:
        # Documentation does not guarantee these semantics: require operator assertion.
        if timestamp_convention != "open":
            raise ProviderError("Groww timestamp convention must be confirmed as open")
        self.client = client
        self.adjustment_type = adjustment_type

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
        if request.adjustment_type != self.adjustment_type:
            raise ProviderError("Groww adjustment assertion differs from request")
        row_number = 0
        for symbol in request.symbols:
            start = request.start
            while start < request.end:
                end = min(start + self.max_range(request.timeframe), request.end)
                try:
                    payload = self.client.get_historical_candles(
                        exchange=request.exchange.value,
                        segment=request.segment.value,
                        groww_symbol=f"{request.exchange.value}-{symbol}",
                        start_time=str(int(start.timestamp())),
                        end_time=str(int(end.timestamp())),
                        candle_interval=request.timeframe.value,
                    )
                except Exception:
                    raise ProviderError("Groww historical request failed") from None
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
                        timestamp = datetime.fromisoformat(timestamp)
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=IST)
                        # Normalize the inclusive provider end to [start, end).
                        if timestamp == request.end:
                            continue
                    except (ValueError, TypeError):
                        pass  # Invalid scalar is passed to normalizer and audited.
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
