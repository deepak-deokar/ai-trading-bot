from datetime import datetime, timedelta

import pandas as pd
import pytest

from trading_bot.data.calendar import NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.normalize import normalize
from trading_bot.data.providers.base import ProviderError
from trading_bot.data.providers.yahoo import (
    OPTIONS,
    SYMBOLS,
    YahooHistoricalDataProvider,
)
from trading_bot.domain.market import AdjustmentType


@pytest.fixture
def yahoo_sample():
    start = datetime.fromisoformat("2026-10-19T09:15:00+05:30")
    request = HistoryRequest(
        symbols=("RELIANCE",),
        start=start,
        end=start.replace(hour=15, minute=30),
        adjustment_type=AdjustmentType.YAHOO_NATIVE,
    )
    index = pd.date_range(start, periods=75, freq="5min").tz_convert("Asia/Kolkata")
    frame = pd.DataFrame(
        {
            "Open": [1500.0] * 75,
            "High": [1502.0] * 75,
            "Low": [1498.0] * 75,
            "Close": [1501.0] * 75,
            "Volume": [1000] * 75,
        },
        index=index,
    )
    metadata = dict(
        symbol="RELIANCE.NS",
        exchangeName="NSI",
        instrumentType="EQUITY",
        currency="INR",
        dataGranularity="5m",
        exchangeTimezoneName="Asia/Kolkata",
    )
    return request, frame, metadata


def provider(request, frame, metadata):
    return YahooHistoricalDataProvider(
        NSECalendar(),
        loader=lambda *args: (frame, metadata),
        now=lambda: request.end + timedelta(days=1),
    )


def test_mappings_and_explicit_options(yahoo_sample):
    req, frame, meta = yahoo_sample
    calls = []

    def load(*args):
        calls.append(args)
        return frame, meta

    p = YahooHistoricalDataProvider(
        NSECalendar(), loader=load, now=lambda: req.end + timedelta(days=1)
    )
    p.prepare(req)
    assert len(list(p.fetch_bars(req))) == 75 and len(calls) == 1
    assert calls[0] == ("RELIANCE.NS", req.start, req.end)
    assert SYMBOLS == {
        "RELIANCE": "RELIANCE.NS",
        "TCS": "TCS.NS",
        "INFY": "INFY.NS",
        "HDFCBANK": "HDFCBANK.NS",
        "ICICIBANK": "ICICIBANK.NS",
    }
    assert OPTIONS["interval"] == "5m" and OPTIONS["auto_adjust"] is False
    assert OPTIONS["back_adjust"] is OPTIONS["repair"] is False
    assert OPTIONS["actions"] is OPTIONS["keepna"] is True


def test_normalization_timezone_native_policy(yahoo_sample):
    req, frame, meta = yahoo_sample
    p = provider(req, frame, meta)
    rows = list(p.fetch_bars(req))
    bar = normalize(rows[0], req, p.name)
    assert bar.timestamp.hour == 3 and bar.timestamp.minute == 45
    assert (
        bar.source == "yahoo_finance"
        and bar.adjustment_type == AdjustmentType.YAHOO_NATIVE
    )
    assert bar.volume == 1000 and bar.close == 1501
    assert p.semantics_manifest()["adjustment_status"] == "UNVERIFIED"
    assert p.evidence["missing_expected_slots"] == 0


@pytest.mark.parametrize(
    "case", ["empty", "column", "naive", "shifted", "symbol", "interval", "timezone"]
)
def test_fail_closed_semantics(yahoo_sample, case):
    req, frame, meta = yahoo_sample
    if case == "empty":
        frame = frame.iloc[:0]
    if case == "column":
        frame = frame.drop(columns=["Volume"])
    if case == "naive":
        frame.index = frame.index.tz_localize(None)
    if case == "shifted":
        frame.index += timedelta(minutes=5)
    if case == "symbol":
        meta["symbol"] = "TCS.NS"
    if case == "interval":
        meta["dataGranularity"] = "1m"
    if case == "timezone":
        meta["exchangeTimezoneName"] = "UTC"
    with pytest.raises(ProviderError):
        list(provider(req, frame, meta).fetch_bars(req))


@pytest.mark.parametrize("policy", ["RAW", "SPLIT_ADJUSTED", "FULLY_ADJUSTED"])
def test_adjustment_policy_cannot_be_relabelled(yahoo_sample, policy):
    req, frame, meta = yahoo_sample
    req = req.model_copy(update={"adjustment_type": AdjustmentType(policy)})
    with pytest.raises(ProviderError):
        list(provider(req, frame, meta).fetch_bars(req))


def test_unknown_symbol_and_incomplete_session(yahoo_sample):
    req, frame, meta = yahoo_sample
    for changed in [
        req.model_copy(update={"symbols": ("UNKNOWN",)}),
        req.model_copy(update={"end": req.end - timedelta(hours=1)}),
    ]:
        with pytest.raises(ProviderError):
            list(provider(req, frame, meta).fetch_bars(changed))


def test_duplicate_ordering_and_missing_rows_preserved(yahoo_sample):
    req, frame, meta = yahoo_sample
    frame = pd.concat([frame.iloc[[1]], frame.drop(frame.index[2])])
    p = provider(req, frame, meta)
    rows = list(p.fetch_bars(req))
    assert len(rows) == 75 and rows[0].values["timestamp"] > rows[1].values["timestamp"]
    assert rows[0].values == rows[2].values
    assert p.evidence["missing_expected_slots"] == 1


def test_invalid_volume_and_ohlc_reach_normal_validation(yahoo_sample):
    req, frame, meta = yahoo_sample
    frame["Volume"] = frame["Volume"].astype(float)
    frame.iloc[0, frame.columns.get_loc("Volume")] = 1.5
    frame.iloc[1, frame.columns.get_loc("Low")] = 1600
    rows = list(provider(req, frame, meta).fetch_bars(req))
    for row in rows[:2]:
        with pytest.raises(ValueError):
            normalize(row, req, "yahoo_finance")


def test_nan_placeholder_is_rejected_not_filled_or_dropped(yahoo_sample):
    req, frame, meta = yahoo_sample
    frame.loc[frame.index[30], ["Open", "High", "Low", "Close"]] = float("nan")
    frame.loc[frame.index[30], "Volume"] = 0
    rows = list(provider(req, frame, meta).fetch_bars(req))
    assert len(rows) == 75
    assert rows[30].values["open"] == "NaN"
    with pytest.raises(ValueError):
        normalize(rows[30], req, "yahoo_finance")
