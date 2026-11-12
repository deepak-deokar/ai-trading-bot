"""Offline May–July 2024 data-quality audit; no database or strategy imports."""

import argparse
import calendar
import csv
import hashlib
import io
import json
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from itertools import groupby
from pathlib import Path
from zipfile import ZipFile

from trading_bot.data.providers.histdata import (
    SOURCE_TIMEZONE,
    five_minute_view,
    parse_tick,
)

VERSION = "G2C4E2A-v1"
HOLIDAYS = {
    "2024-05-27": "Memorial Day",
    "2024-06-19": "Juneteenth National Independence Day",
    "2024-07-04": "Independence Day",
}
HOLIDAY_SOURCE = (
    "https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/#url=2024"
)
STEP = timedelta(minutes=5)


def audit_day(day, lines):
    """Keep invalid/duplicate observations explicit; aggregate valid ticks unchanged."""
    start = datetime.combine(day, time(), SOURCE_TIMEZONE).astimezone(UTC)
    expected = tuple(start + n * STEP for n in range(288))
    ticks = []
    raw = invalid = crossed = regressions = 0
    rejected = []
    previous = None
    for line in lines:
        raw += 1
        try:
            tick = parse_tick(line)
            if tick.quote.timestamp.astimezone(SOURCE_TIMEZONE).date() != day:
                raise ValueError("record outside stated source day")
        except (ValueError, InvalidOperation, csv.Error):
            invalid += 1
            if len(rejected) < 20:
                rejected.append(raw)
            try:
                fields = next(csv.reader([line], strict=True))
                bid, ask = Decimal(fields[1]), Decimal(fields[2])
                crossed += int(bid.is_finite() and ask.is_finite() and bid > ask)
            except (ValueError, InvalidOperation, IndexError, csv.Error):
                pass
            continue
        if previous is not None and tick.quote.timestamp < previous:
            regressions += 1
        previous = tick.quote.timestamp
        ticks.append(tick)
    timestamps = Counter(t.quote.timestamp for t in ticks)
    exact = Counter(
        (t.quote.timestamp, t.quote.bid, t.quote.ask, t.source_volume) for t in ticks
    )
    precision, effective = Counter(), Counter()
    aligned = Counter()
    volumes = Counter()
    for tick in ticks:
        volumes[tick.source_volume] += 1
        for price in (tick.quote.bid, tick.quote.ask):
            precision[max(0, -int(price.as_tuple().exponent))] += 1
            effective[max(0, -int(price.normalize().as_tuple().exponent))] += 1
            aligned["aligned_0.001" if price % Decimal("0.001") == 0 else "finer"] += 1
            if price % Decimal("0.01") == 0:
                aligned["aligned_0.01"] += 1
    bars = five_minute_view(ticks)
    observed = {datetime.fromisoformat(b["timestamp"]) for b in bars}
    missing = [i for i, opening in enumerate(expected) if opening not in observed]
    outside = sorted(observed - set(expected))
    assert len(observed & set(expected)) + len(missing) == 288
    assert sum(b["ticks"] for b in bars) == len(ticks)
    return {
        "date": day.isoformat(),
        "weekday": day.strftime("%A"),
        "tick_presence": bool(ticks),
        "raw_ticks": raw,
        "valid_ticks": len(ticks),
        "invalid_ticks": invalid,
        "crossed_quotes": crossed,
        "duplicate_timestamps": sum(n - 1 for n in timestamps.values()),
        "duplicate_observations": sum(n - 1 for n in exact.values()),
        "timestamp_regressions": regressions,
        "rejected_day_rows_first_20": rejected,
        "expected_bins": 288,
        "observed_bins": len(bars),
        "missing_bins": len(missing),
        "missing_indices": missing,
        "missing_openings": [expected[i].isoformat() for i in missing],
        "out_of_range_openings": [t.isoformat() for t in outside],
        "first_observation": min(timestamps).isoformat() if ticks else None,
        "last_observation": max(timestamps).isoformat() if ticks else None,
        "first_bar": bars[0]["timestamp"] if bars else None,
        "last_bar": bars[-1]["timestamp"] if bars else None,
        "source_price_decimal_places": dict(precision),
        "effective_price_decimal_places": dict(effective),
        "price_alignment": dict(aligned),
        "volume_values": dict(volumes),
        "observed_bar_sha256": hashlib.sha256(
            json.dumps(bars, default=str, sort_keys=True).encode()
        ).hexdigest(),
    }


def classify_month(days):
    """Discover exact recurring one-hour signatures; never activate a policy."""
    frequencies = Counter(
        tuple(d["missing_indices"])
        for d in days
        if date.fromisoformat(d["date"]).weekday() < 4
        and d["date"] not in HOLIDAYS
        and not d["invalid_ticks"]
        and not d["timestamp_regressions"]
        and not d["out_of_range_openings"]
        and d["valid_ticks"]
    )
    patterns = sorted(
        sig
        for sig, count in frequencies.items()
        if count >= 3 and len(sig) == 12 and sig == tuple(range(sig[0], sig[0] + 12))
    )
    for d in days:
        missing = set(d["missing_indices"])
        # Reference only: nearest observed signature, never an automatic acceptance.
        reference = min(patterns, key=lambda p: (len(missing ^ set(p)), p), default=())
        d["reference_missing_indices"] = list(reference)
        extra = sorted(missing - set(reference))
        day = date.fromisoformat(d["date"])
        start = datetime.combine(day, time(), SOURCE_TIMEZONE).astimezone(UTC)
        d["unexpected_missing_openings"] = [
            (start + i * STEP).isoformat() for i in extra
        ]
        d["unexpected_bins"] = len(extra)
        d["expected_pattern_bins_present"] = sorted(set(reference) - missing)
        d["holiday_context"] = HOLIDAYS.get(d["date"])
        d["no_data"] = not d["valid_ticks"]
        d["proposed_eligible"] = False
        if day.weekday() == 5:
            label = "SATURDAY"
        elif day.weekday() == 6:
            label = "SUNDAY"
        elif d["holiday_context"]:
            label = "HOLIDAY_ASSOCIATED"
        elif not d["valid_ticks"]:
            label = "NO_DATA"
        elif day.weekday() == 4:
            label = "FRIDAY"
        elif (
            tuple(d["missing_indices"]) in patterns
            and not d["invalid_ticks"]
            and not d["timestamp_regressions"]
            and not d["out_of_range_openings"]
        ):
            label = "NORMAL_WEEKDAY_CANDIDATE"
            d["proposed_eligible"] = True
        else:
            label = "UNEXPLAINED_ANOMALY"
        d["classification"] = label
    return [
        {
            "category": "OBSERVED_DAILY_PROVIDER_CLOSURE_PATTERN",
            "missing_indices": list(p),
            "utc_opening_clocks": [
                (datetime(2024, 1, 1, 5, tzinfo=UTC) + i * STEP).strftime("%H:%M")
                for i in p
            ],
            "exact_match_dates": [
                d["date"] for d in days if tuple(d["missing_indices"]) == p
            ],
            "proposed_source_dates": [
                d["date"]
                for d in days
                if d["proposed_eligible"] and tuple(d["missing_indices"]) == p
            ],
        }
        for p in patterns
    ]


def audit_archive(root, month):
    if month not in (5, 6, 7):
        raise ValueError("only May–July 2024 authorized")
    provenance = json.loads((root / f"2024{month:02d}-provenance.json").read_text())
    archive = root / f"HISTDATA_COM_ASCII_XAUUSD_T_2024{month:02d}.zip"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == provenance["sha256"]
    member = f"DAT_ASCII_XAUUSD_T_2024{month:02d}.csv"
    by_day = {}
    with ZipFile(archive) as zipped:
        assert zipped.namelist().count(member) == 1
        assert zipped.getinfo(member).file_size < 2_000_000_000
        with zipped.open(member) as stream:
            for prefix, lines in groupby(
                io.TextIOWrapper(stream, encoding="ascii"), lambda s: s[:8]
            ):
                day = datetime.strptime(prefix, "%Y%m%d").date()
                if day.year != 2024 or day.month != month or day in by_day:
                    raise ValueError("unexpected/out-of-order source date; stop audit")
                by_day[day] = audit_day(day, lines)
                print(day, by_day[day]["raw_ticks"], flush=True)
    days = [
        by_day[d] if d in by_day else audit_day(d, ())
        for n in range(1, calendar.monthrange(2024, month)[1] + 1)
        for d in (date(2024, month, n),)
    ]
    patterns = classify_month(days)
    proposals = []
    for p in patterns:
        allowed = p["proposed_source_dates"]
        if allowed:
            proposals.append(
                {
                    "status": "PROPOSED_ONLY_NOT_ACTIVATED",
                    "effective_start_date": min(allowed),
                    "effective_end_date": max(allowed),
                    "allowed_source_dates": allowed,
                    "allowed_missing_indices": p["missing_indices"],
                    "archive_sha256": provenance["sha256"],
                    "report_version": VERSION,
                    "normalization_version": "histdata-ticks-v1",
                    "aggregation_version": "bid-ask-utc-5minute-v1",
                    "requirement": (
                        "exact missing-set equality; no invalid/unexplained data; "
                        "exclude Fridays/weekends/holidays"
                    ),
                }
            )
    sums = {
        k: sum(d[k] for d in days)
        for k in (
            "raw_ticks",
            "valid_ticks",
            "invalid_ticks",
            "crossed_quotes",
            "duplicate_timestamps",
            "duplicate_observations",
            "timestamp_regressions",
            "observed_bins",
        )
    }
    return {
        "month": f"2024-{month:02d}",
        "archive": provenance,
        "member": member,
        "totals": sums,
        "classifications": dict(Counter(d["classification"] for d in days)),
        "proposed_eligible_days": sum(d["proposed_eligible"] for d in days),
        "patterns": patterns,
        "proposed_segments": proposals,
        "days": days,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_directory", type=Path)
    args = parser.parse_args()
    report = {
        "version": VERSION,
        "provider": "HISTDATA",
        "canonical_symbol": "XAUUSD",
        "provider_symbol": "XAU/USD",
        "source_timezone": "UTC-05:00 fixed; no DST",
        "interval": "5minute",
        "timestamp_convention": "open",
        "validation_partition": "May–July 2024; data quality only",
        "locked_partition": "August–October 2024; not processed",
        "strategy_outcomes_inspected": False,
        "database_writes": False,
        "holiday_context_source": HOLIDAY_SOURCE,
        "pattern_rule": (
            "At least three non-holiday Mon–Thu exact matches of one "
            "contiguous 12-bin missing set per month; no presumed UTC clock"
        ),
        "months": [audit_archive(args.archive_directory, m) for m in (5, 6, 7)],
    }
    report["content_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True).encode()
    ).hexdigest()
    Path("docs/histdata-validation-may-july-2024.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
