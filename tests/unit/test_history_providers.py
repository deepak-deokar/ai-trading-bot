from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.normalize import normalize
from trading_bot.data.providers.base import ProviderError
from trading_bot.data.providers.groww import GrowwHTTPClient, GrowwProvider
from trading_bot.data.providers.local import LocalCSVProvider
from trading_bot.domain.market import AdjustmentType, Timeframe


def request(end="2026-01-05T10:00:00+05:30"):
    return HistoryRequest(
        symbols=("RELIANCE",),
        start=datetime.fromisoformat("2026-01-05T09:15:00+05:30"),
        end=datetime.fromisoformat(end),
    )


def provider(client):
    return GrowwProvider(
        client, adjustment_type=AdjustmentType.RAW, timestamp_convention="open"
    )


def test_groww_current_response_parsing():
    client = Mock(spec=["get_historical_candles"])
    client.get_historical_candles.return_value = {
        "candles": [
            ["2026-01-05T09:15:00", Decimal("1500.10"), 1502, 1499, 1501, 100, None]
        ]
    }
    req = request()
    bar = normalize(list(provider(client).fetch_bars(req))[0], req, "groww")
    assert bar.open == Decimal("1500.10")
    assert bar.timestamp.hour == 3 and bar.timestamp.minute == 45
    assert (
        client.get_historical_candles.call_args.kwargs["groww_symbol"] == "NSE-RELIANCE"
    )
    assert (
        client.get_historical_candles.call_args.kwargs["candle_interval"] == "5minute"
    )


def test_groww_chunk_boundaries_preserved_for_conflict_audit():
    client = Mock(spec=["get_historical_candles"])
    candle = ["2026-02-04T09:15:00", 1500, 1502, 1499, 1501, 100, None]
    client.get_historical_candles.side_effect = [
        {"candles": [candle]},
        {"candles": [candle]},
    ]
    rows = list(provider(client).fetch_bars(request("2026-02-05T10:00:00+05:30")))
    assert len(rows) == 2 and rows[0].values == rows[1].values
    calls = client.get_historical_candles.call_args_list
    assert calls[0].kwargs["end_time"] == calls[1].kwargs["start_time"]
    assert (
        int(calls[0].kwargs["end_time"]) - int(calls[0].kwargs["start_time"])
        == 30 * 86400
    )


@pytest.mark.parametrize(
    "tf,days",
    [
        (Timeframe.MIN_1, 30),
        (Timeframe.MIN_5, 30),
        (Timeframe.MIN_10, 90),
        (Timeframe.MIN_15, 90),
        (Timeframe.MIN_30, 90),
        (Timeframe.HOUR_1, 180),
        (Timeframe.DAY_1, 180),
    ],
)
def test_documented_groww_limits(tf, days):
    assert GrowwProvider.max_range(tf).days == days


def test_groww_failure_hides_vendor_secrets():
    client = Mock(spec=["get_historical_candles"])
    client.get_historical_candles.side_effect = RuntimeError("SECRET-TOKEN")
    with pytest.raises(ProviderError) as error:
        list(provider(client).fetch_bars(request()))
    assert "SECRET-TOKEN" not in str(error.value)


def test_groww_http_fixed_read_only_endpoint(monkeypatch):
    import io

    opener = Mock(
        return_value=io.BytesIO(b'{"status":"SUCCESS","payload":{"candles":[]}}')
    )
    monkeypatch.setattr("trading_bot.data.providers.groww.urlopen", opener)
    client = GrowwHTTPClient(SecretStr("not-a-real-token"))
    assert client.get_historical_candles(exchange="NSE") == {"candles": []}
    sent = opener.call_args.args[0]
    assert sent.get_method() == "GET"
    assert sent.full_url.startswith("https://api.groww.in/v1/historical/candles?")
    assert opener.call_args.kwargs["timeout"] == 30


@pytest.mark.parametrize(
    "content",
    [
        "wrong,header\n1,2",
        "symbol,timestamp,open,high,low,close,volume\nRELIANCE,1,2",
        'symbol,timestamp,open,high,low,close,volume\n"unterminated',
    ],
)
def test_malformed_csv_fails(tmp_path, content):
    path = tmp_path / "bad.csv"
    path.write_text(content)
    with pytest.raises(ProviderError):
        list(LocalCSVProvider(path).fetch_bars(request()))


def test_csv_preserves_decimal_strings_and_invalid_values(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text(
        "symbol,timestamp,open,high,low,close,volume\nRELIANCE,2026-01-05T09:15:00+05:30,1500.10,1502,1499,1501,100\n"
    )
    req = request()
    row = list(LocalCSVProvider(path).fetch_bars(req))[0]
    assert normalize(row, req, "local").open == Decimal("1500.10")


def test_groww_requires_semantic_assertions():
    with pytest.raises(ProviderError):
        GrowwProvider(
            Mock(), adjustment_type=AdjustmentType.RAW, timestamp_convention="close"
        )


def test_groww_malformed_rows_are_exposed_for_rejection():
    client = Mock(spec=["get_historical_candles"])
    client.get_historical_candles.return_value = {"candles": [["bad"]]}
    assert list(provider(client).fetch_bars(request()))[0].values == {}


def test_groww_inclusive_final_boundary_is_excluded():
    client = Mock(spec=["get_historical_candles"])
    client.get_historical_candles.return_value = {
        "candles": [["2026-01-05T10:00:00", 1500, 1502, 1499, 1501, 100, None]]
    }
    assert list(provider(client).fetch_bars(request())) == []
