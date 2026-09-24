"""Hardening regression tests; no features or strategy calculations."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
import yaml
from pydantic import ValidationError

from trading_bot.data.calendar import CalendarError, NSECalendar
from trading_bot.data.contracts import HistoryRequest
from trading_bot.data.identity import dataset_identity
from trading_bot.data.normalize import normalize
from trading_bot.data.providers.base import RawCandle
from trading_bot.data.providers.groww import GrowwProvider
from trading_bot.data.providers.groww_semantics import (
    GrowwSemantics,
    ProviderSemanticsError,
)
from trading_bot.domain.market import Timeframe
from trading_bot.domain.models import Bar


def dt(value):
    return datetime.fromisoformat(value + "+05:30")


def semantics(**updates):
    return GrowwSemantics.model_validate(
        dict(
            timestamp_meaning="open",
            timezone="Asia/Kolkata",
            adjustment_type="RAW",
            interval_mapping={"5minute": "5minute"},
            instrument_mapping={"NSE:CASH:RELIANCE": "NSE-RELIANCE"},
            acknowledgement="UNVERIFIED_PROVIDER_SEMANTICS_ACCEPTED",
        )
        | updates
    )


def request(**updates):
    return HistoryRequest(
        **(
            dict(
                symbols=("RELIANCE",),
                start=dt("2026-01-05T09:15"),
                end=dt("2026-01-05T09:20"),
            )
            | updates
        )
    )


@pytest.mark.parametrize(
    "year,day",
    [
        (2020, "01-06"),
        (2021, "01-04"),
        (2022, "01-03"),
        (2023, "01-02"),
        (2024, "01-02"),
        (2025, "01-02"),
        (2026, "01-05"),
    ],
)
def test_multiyear_regular_session_with_explicit_research_acceptance(year, day):
    calendar = NSECalendar(allow_unverified_history=True)
    start, end = dt(f"{year}-{day}T09:15"), dt(f"{year}-{day}T15:30")
    bars = calendar.expected_bars(start, end, Timeframe.MIN_5)
    assert len(bars) == 75
    assert min(bars) == start and max(bars.values()) == end
    expected_authority = "REVIEWED_POLICY" if year == 2026 else "UNKNOWN"
    assert calendar.provenance(start, end)["authority"] == expected_authority


@pytest.mark.parametrize(
    "date",
    [
        "2020-01-04",
        "2021-01-26",
        "2022-01-26",
        "2023-01-26",
        "2024-01-26",
        "2025-01-26",
    ],
)
def test_dependency_weekends_and_known_holidays(date):
    calendar = NSECalendar(allow_unverified_history=True)
    assert not calendar.expected_bars(
        dt(date + "T09:15"), dt(date + "T15:30"), Timeframe.MIN_5
    )


def test_unreviewed_history_requires_opt_in():
    with pytest.raises(CalendarError, match="UNKNOWN"):
        NSECalendar().expected_bars(
            dt("2020-01-06T09:15"), dt("2020-01-06T09:20"), Timeframe.MIN_5
        )


def test_year_boundary_has_no_overnight_phantom_bars():
    calendar = NSECalendar(allow_unverified_history=True)
    expected = calendar.expected_bars(
        dt("2020-12-31T15:25"), dt("2021-01-01T09:20"), Timeframe.MIN_5
    )
    assert list(expected) == [dt("2020-12-31T15:25"), dt("2021-01-01T09:15")]


@pytest.mark.parametrize("day", ["2019-12-31", "2027-01-04"])
def test_outside_dependency_coverage_always_fails(day):
    calendar = NSECalendar(allow_unverified_history=True)
    with pytest.raises(CalendarError, match="coverage"):
        calendar.expected_bars(dt(day + "T09:15"), dt(day + "T09:20"), Timeframe.MIN_5)


def test_fixture_closure_special_session_and_unknown_date(tmp_path):
    policy = yaml.safe_load(Path("config/calendar_nse.yaml").read_text())
    policy["closed"].append({"date": "2021-01-05", "source": "fixture:known-closure"})
    policy["sessions"].append(
        {
            "date": "2021-01-09",
            "open": "10:00",
            "close": "10:10",
            "source": "fixture:special-session",
        }
    )
    policy["unknown"] = [
        {"start": "2021-01-06", "end": "2021-01-06", "reason": "fixture:unknown"}
    ]
    path = tmp_path / "calendar.yaml"
    path.write_text(yaml.safe_dump(policy))
    calendar = NSECalendar(path, allow_unverified_history=True)
    assert not calendar.expected_bars(
        dt("2021-01-05T09:15"), dt("2021-01-05T15:30"), Timeframe.MIN_5
    )
    assert (
        len(
            calendar.expected_bars(
                dt("2021-01-09T09:15"), dt("2021-01-09T15:30"), Timeframe.MIN_5
            )
        )
        == 2
    )
    with pytest.raises(CalendarError):
        calendar.expected_bars(
            dt("2021-01-06T09:15"), dt("2021-01-06T15:30"), Timeframe.MIN_5
        )


def test_dependency_upgrade_requires_coverage_review(tmp_path):
    policy = yaml.safe_load(Path("config/calendar_nse.yaml").read_text())
    policy["provider_version"] = "unknown-version"
    path = tmp_path / "calendar.yaml"
    path.write_text(yaml.safe_dump(policy))
    with pytest.raises(CalendarError, match="version"):
        NSECalendar(path)


def test_bar_open_interval_is_half_open():
    req = request()
    expected = NSECalendar().expected_bars(req.start, req.end, req.timeframe)
    opening, closing = next(iter(expected.items()))
    assert opening == dt("2026-01-05T09:15")
    assert closing == dt("2026-01-05T09:20")
    assert opening <= dt("2026-01-05T09:19:59") < closing
    assert not opening <= dt("2026-01-05T09:20") < closing
    values = dict(
        symbol="RELIANCE",
        timestamp=opening,
        open=100,
        high=102,
        low=99,
        close=101,
        volume=1,
    )
    assert Bar(**values).model_dump()["timestamp_convention"] == "open"
    with pytest.raises(ValidationError):
        Bar(**values, timestamp_convention="close")
    with pytest.raises(ValueError, match="openings"):
        normalize(RawCandle(values, 1, timestamp_convention="close"), req, "local")


@pytest.mark.parametrize(
    "field",
    [
        "timestamp_meaning",
        "timezone",
        "adjustment_type",
        "interval_mapping",
        "instrument_mapping",
        "acknowledgement",
    ],
)
def test_all_groww_semantics_are_required(field):
    values = semantics().model_dump()
    values.pop(field)
    with pytest.raises(ValidationError):
        GrowwSemantics.model_validate(values)


@pytest.mark.parametrize(
    "updates",
    [
        {"timestamp_meaning": "close"},
        {"timezone": "UTC"},
        {"adjustment_type": "unknown"},
        {"interval_mapping": {"5minute": "1minute"}},
        {"instrument_mapping": {"NSE:CASH:RELIANCE": "NSE-TCS"}},
    ],
)
def test_unsupported_groww_mapping_fails(updates):
    with pytest.raises(ValidationError):
        semantics(**updates)


def test_groww_unconfigured_cannot_fetch():
    client = Mock(spec=["get_historical_candles"])
    with pytest.raises(ProviderSemanticsError):
        GrowwProvider(client, adjustment_type="RAW", timestamp_convention="open")
    client.get_historical_candles.assert_not_called()


@pytest.mark.parametrize(
    "updates",
    [
        {"symbols": ("TCS",)},
        {"timeframe": "15minute"},
        {"adjustment_type": "SPLIT_ADJUSTED"},
    ],
)
def test_groww_missing_or_conflicting_mapping_fails_before_network(updates):
    client = Mock(spec=["get_historical_candles"])
    with pytest.raises(ProviderSemanticsError):
        list(
            GrowwProvider(client, semantics=semantics()).fetch_bars(request(**updates))
        )
    client.get_historical_candles.assert_not_called()


def test_groww_unknown_timestamp_format_is_rejected_not_guessed():
    client = Mock(spec=["get_historical_candles"])
    client.get_historical_candles.return_value = {
        "candles": [[1767584700, 100, 102, 99, 101, 1, None]]
    }
    rows = list(GrowwProvider(client, semantics=semantics()).fetch_bars(request()))
    with pytest.raises(ValueError):
        normalize(rows[0], request(), "groww")


def test_groww_response_interval_mismatch_is_semantics_error():
    client = Mock(spec=["get_historical_candles"])
    client.get_historical_candles.return_value = {
        "candles": [],
        "interval_in_minutes": 1,
    }
    with pytest.raises(ProviderSemanticsError, match="interval"):
        list(GrowwProvider(client, semantics=semantics()).fetch_bars(request()))


def test_dataset_identity_canonical_selection_and_unique_run():
    cal = NSECalendar()
    req = request(symbols=("RELIANCE", "TCS"))
    provenance = cal.provenance(req.start, req.end)
    a = dataset_identity(req, "local", uuid4(), provenance, {})
    b = dataset_identity(
        request(symbols=("TCS", "RELIANCE")), "local", uuid4(), provenance, {}
    )
    assert a.dataset_key == b.dataset_key and a.run_key != b.run_key
    for req2, provider, calendar, mapping in [
        (request(adjustment_type="SPLIT_ADJUSTED"), "local", provenance, {}),
        (req, "groww", provenance, {}),
        (req, "local", provenance | {"version": "changed"}, {}),
        (req, "local", provenance, {"timezone": "changed"}),
        (request(end=dt("2026-01-05T09:25")), "local", provenance, {}),
    ]:
        assert (
            dataset_identity(req2, provider, a.run_id, calendar, mapping).dataset_key
            != a.dataset_key
        )
