"""Bounded Yahoo research adapter. Native prices are explicitly unverified."""

import math
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from importlib.metadata import version
from typing import Any

from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.providers.base import ProviderError, RawCandle
from trading_bot.domain.market import AdjustmentType, Timeframe, utc

SYMBOLS = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
}
OPTIONS = dict(
    interval="5m",
    auto_adjust=False,
    back_adjust=False,
    actions=True,
    repair=False,
    keepna=True,
    prepost=False,
    rounding=False,
    timeout=20,
)


def yahoo_history(
    symbol: str, start: datetime, end: datetime
) -> tuple[Any, dict[str, Any]]:
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    frame = ticker.history(start=start, end=end, **OPTIONS)
    metadata = ticker.get_history_metadata()
    return frame, {
        key: metadata.get(key)
        for key in (
            "symbol",
            "exchangeName",
            "instrumentType",
            "currency",
            "dataGranularity",
            "exchangeTimezoneName",
        )
    }


class YahooHistoricalDataProvider:
    name = "yahoo_finance"

    def __init__(
        self,
        calendar: NSECalendar,
        *,
        loader: Callable[
            [str, datetime, datetime], tuple[Any, dict[str, Any]]
        ] = yahoo_history,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.calendar = calendar
        self.loader = loader
        self.now = now
        self._request: HistoryRequest | None = None
        self._rows: tuple[RawCandle, ...] = ()
        self.evidence: dict[str, Any] = {}

    def semantics_manifest(self) -> dict[str, Any]:
        return {
            "adapter_version": "yahoo-native-v1",
            "library": "yfinance",
            "library_version": version("yfinance"),
            "symbol_mapping": dict(SYMBOLS),
            "interval_mapping": {"5minute": "5m"},
            "options": dict(OPTIONS),
            "adjustment_type": "YAHOO_NATIVE",
            "adjustment_status": "UNVERIFIED",
            "real_api_verification": "UNVERIFIED",
            "timestamp_convention": "open",
            "timestamp_gate": "aware NSE session-open anchors and aligned 5m labels",
            "price_precision": "Decimal 10 places; not exchange tick rounding",
            "evidence": dict(self.evidence),
        }

    def prepare(self, request: HistoryRequest) -> None:
        """Preflight once before ingestion; reuse the same sample without refetching."""
        self._request = None
        self._rows = ()
        self.evidence = {}
        now = utc(self.now())
        if (
            request.adjustment_type != AdjustmentType.YAHOO_NATIVE
            or request.timeframe != Timeframe.MIN_5
            or len(request.symbols) != 1
            or request.symbols[0] not in SYMBOLS
        ):
            raise ProviderError(
                "Yahoo requires one mapped symbol, 5minute, YAHOO_NATIVE"
            )
        if request.start < now - timedelta(days=59) or request.end > now - timedelta(
            minutes=30
        ):
            raise ProviderError("Yahoo pilot requires recent finalized sessions")
        sessions = self.calendar.sessions(request.start, request.end)
        if not 1 <= len(sessions) <= 5 or any(
            s.opens < request.start or s.closes > request.end for s in sessions
        ):
            raise ProviderError("Yahoo pilot requires one to five complete sessions")
        symbol = request.symbols[0]
        try:
            frame, metadata = self.loader(SYMBOLS[symbol], request.start, request.end)
        except Exception:
            raise ProviderError(
                "Yahoo historical request failed; no data ingested"
            ) from None
        columns = ["Open", "High", "Low", "Close", "Volume"]
        if frame is None or frame.empty:
            raise ProviderError(
                "Yahoo returned empty data; timestamp semantics unverified"
            )
        if not frame.columns.is_unique or not set(columns).issubset(frame.columns):
            raise ProviderError("Yahoo response lacks unique OHLCV columns")
        if len(frame) > 1000:
            raise ProviderError("Yahoo response exceeds pilot bound")
        if (
            metadata.get("symbol") != SYMBOLS[symbol]
            or metadata.get("exchangeName") != "NSI"
            or metadata.get("instrumentType") != "EQUITY"
            or metadata.get("currency") != "INR"
            or metadata.get("dataGranularity") != "5m"
            or metadata.get("exchangeTimezoneName")
            not in ("Asia/Kolkata", "Asia/Calcutta")
        ):
            raise ProviderError(
                "Yahoo instrument/interval/timezone metadata unverified"
            )
        zone = str(getattr(frame.index, "tz", None))
        if zone not in ("Asia/Kolkata", "Asia/Calcutta"):
            raise ProviderError("Yahoo timestamp timezone unverified")
        expected = self.calendar.expected_bars(
            request.start, request.end, request.timeframe
        )
        try:
            stamps = [utc(t.to_pydatetime()) for t in frame.index]
        except (AttributeError, ValueError, TypeError):
            raise ProviderError("Yahoo timestamps invalid or naive") from None
        unique = set(stamps)
        if any(t not in expected for t in stamps) or any(
            s.opens not in unique for s in sessions
        ):
            raise ProviderError(
                "Yahoo opening-label evidence insufficient or timestamps unexpected"
            )
        # Preserve ordering and duplicates for normal ingestion quality checks.
        rows = []
        for number, (stamp, values) in enumerate(
            zip(stamps, frame[columns].itertuples(index=False, name=None), strict=True),
            1,
        ):
            payload: dict[str, Any] = {
                "symbol": symbol,
                "timestamp": stamp,
                "adjustment_type": AdjustmentType.YAHOO_NATIVE,
            }
            for key, value in zip(
                ("open", "high", "low", "close"), values[:4], strict=True
            ):
                try:
                    payload[key] = str(
                        Decimal(str(value)).quantize(Decimal("0.0000000001"))
                    )
                except InvalidOperation:
                    payload[key] = str(
                        value
                    )  # Normal ingestion rejects invalid prices.
            volume = values[4]
            try:
                payload["volume"] = (
                    int(volume)
                    if math.isfinite(volume) and int(volume) == volume
                    else str(volume)
                )
            except (ValueError, TypeError, OverflowError):
                payload["volume"] = str(volume)
            rows.append(RawCandle(payload, number))
        ordered = sorted(unique)
        gaps = sum(
            (b - a).total_seconds() > 300
            for a, b in zip(ordered, ordered[1:], strict=False)
            if a.date() == b.date()
        )
        self.evidence = {
            "provider_symbol": SYMBOLS[symbol],
            "timezone": zone,
            "first_open": min(stamps).isoformat(),
            "last_open": max(stamps).isoformat(),
            "rows_received": len(rows),
            "sessions": len(sessions),
            "opening_labels": "CONSISTENT_WITH_SESSION_OPEN_ANCHORS",
            "missing_expected_slots": len(set(expected) - unique),
            "intraday_spacing_gaps": gaps,
            "actions_columns": [
                c
                for c in ("Dividends", "Stock Splits", "Capital Gains")
                if c in frame.columns
            ],
            "corporate_actions_observed": any(
                bool((frame[c].fillna(0) != 0).any())
                for c in ("Dividends", "Stock Splits", "Capital Gains")
                if c in frame.columns
            ),
        }
        self._rows = tuple(rows)
        self._request = request

    def fetch_bars(self, request: HistoryRequest) -> Iterable[RawCandle]:
        if self._request != request:
            self.prepare(request)
        return iter(self._rows)
