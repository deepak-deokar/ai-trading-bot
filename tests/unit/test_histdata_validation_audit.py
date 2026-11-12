"""Synthetic offline coverage only; no validation-market observations or strategies."""

import runpy
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

AUDIT = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "scripts/audit_histdata_validation.py")
)
audit_day = AUDIT["audit_day"]
classify_month = AUDIT["classify_month"]


DEFAULT_GAP = range(204, 216)


def synthetic_day(day, missing=DEFAULT_GAP):
    start = datetime.combine(day, time())
    return audit_day(
        day,
        [
            f'{(start + timedelta(minutes=5*i)).strftime("%Y%m%d %H%M%S")}000,'
            "2000.001000,2000.201000,0\n"
            for i in range(288)
            if i not in missing
        ],
    )


def test_fixed_offset_and_separate_observed_bins():
    day = synthetic_day(date(2024, 5, 1))
    assert day["first_observation"] == "2024-05-01T05:00:00+00:00"
    assert day["last_observation"] == "2024-05-02T04:55:00+00:00"
    assert day["observed_bins"] == 276
    assert day["missing_bins"] == 12
    assert day["missing_openings"][0] == "2024-05-01T22:00:00+00:00"
    assert day["price_alignment"] == {"aligned_0.001": 552}
    assert day["effective_price_decimal_places"] == {3: 552}
    assert day["source_price_decimal_places"] == {6: 552}


def test_rejections_and_duplicates_remain_explicit():
    r = audit_day(
        date(2024, 5, 1),
        [
            "20240501 000000000,2000.001,2000.2,0",
            "20240501 000000000,2000.001,2000.2,0",
            "20240501 000001000,2001,2000,0",
            "20240501 000002000,0,2000,0",
            "20240501 000003000,nan,2000,0",
        ],
    )
    assert (r["raw_ticks"], r["valid_ticks"], r["invalid_ticks"]) == (5, 2, 3)
    assert r["crossed_quotes"] == 1
    assert r["duplicate_timestamps"] == r["duplicate_observations"] == 1
    assert r["observed_bins"] == 1 and r["missing_bins"] == 287


@pytest.mark.parametrize("gap", [range(204, 216), range(192, 204)])
def test_discovery_is_independent_of_april_clock(gap):
    days = [synthetic_day(date(2024, 5, d), gap) for d in (6, 7, 8)]
    patterns = classify_month(days)
    assert len(patterns) == 1 and patterns[0]["missing_indices"] == list(gap)
    assert all(d["proposed_eligible"] for d in days)
    assert all(d["unexpected_bins"] == 0 for d in days)


def test_exact_equality_and_exclusions():
    days = [synthetic_day(date(2024, 5, d)) for d in (6, 7, 8)]
    extra = synthetic_day(date(2024, 5, 9), [*range(204, 216), 100])
    fewer = synthetic_day(date(2024, 5, 13), range(204, 215))
    friday = synthetic_day(date(2024, 5, 10))
    holiday = synthetic_day(date(2024, 5, 27))
    empty = audit_day(date(2024, 5, 14), ())
    saturday = audit_day(date(2024, 5, 11), ())
    sunday = synthetic_day(date(2024, 5, 12), range(216))
    cases = [extra, fewer, friday, holiday, empty, saturday, sunday]
    classify_month(days + cases)
    assert all(not d["proposed_eligible"] for d in cases)
    assert extra["unexpected_bins"] == 1
    assert fewer["expected_pattern_bins_present"] == [215]
    assert fewer["classification"] == "UNEXPLAINED_ANOMALY"
    assert holiday["classification"] == "HOLIDAY_ASSOCIATED"
    assert empty["classification"] == "NO_DATA"
    assert saturday["no_data"] and saturday["classification"] == "SATURDAY"
    assert sunday["classification"] == "SUNDAY"


def test_less_than_three_matches_does_not_propose_policy():
    days = [synthetic_day(date(2024, 5, d)) for d in (6, 7)]
    assert classify_month(days) == []
    assert all(not d["proposed_eligible"] for d in days)


def test_locked_month_rejected_before_opening_files(tmp_path):
    with pytest.raises(ValueError, match="only May"):
        AUDIT["audit_archive"](tmp_path, 8)
