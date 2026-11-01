"""Bounded G2C2B: verify existing Feb–Apr archives, preflight, import twice."""

import argparse
import calendar
import hashlib
import io
import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from itertools import groupby
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from trading_bot.config.settings import load_settings
from trading_bot.data.gap_policy import load_gap_policy
from trading_bot.data.policy_import import evaluate_policy_day, import_policy_day
from trading_bot.data.providers.histdata import five_minute_view, parse_tick
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.database.models import BidAskBar
from trading_bot.database.session import build_engine
from trading_bot.domain.quote_bars import QuoteBar


def snapshot(engine):
    with Session(engine) as session:
        rows = session.scalars(select(BidAskBar)).all()
        return {
            (r.dataset_key, r.opening_timestamp.isoformat()): hashlib.sha256(
                json.dumps(
                    {
                        c.name: str(getattr(r, c.name))
                        for c in BidAskBar.__table__.columns
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            for r in rows
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_directory", type=Path)
    args = parser.parse_args()
    policy = load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml"))
    evidence_path = Path("docs/histdata-2024-feb-apr-validation.json")
    evidence = json.loads(evidence_path.read_text())
    report_hash = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    months = evidence["months"]
    if [m["source_month"] for m in months] != ["2024-02", "2024-03", "2024-04"]:
        raise ValueError("only the three validated months are allowed")
    # Verify every archive and its policy evidence before parsing or DB access.
    for month in months:
        path = args.archive_directory / month["archive"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != month["sha256"]:
            raise ValueError("archive checksum mismatch")
        segments = [
            s
            for s in policy.segments
            if s.evidence.source_month == month["source_month"]
        ]
        if not segments or any(
            s.evidence.archive_sha256 != month["sha256"]
            or s.evidence.report_sha256 != report_hash
            for s in segments
        ):
            raise ValueError("policy/evidence binding mismatch")
    prepared = []
    for month in months:
        observed = {}
        with ZipFile(args.archive_directory / month["archive"]) as archive:
            with archive.open(month["source_member"]) as stream:
                lines = io.TextIOWrapper(stream, encoding="ascii")
                for prefix, group in groupby(lines, key=lambda line: line[:8]):
                    day = datetime.strptime(prefix, "%Y%m%d").date()
                    if (
                        day.strftime("%Y-%m") != month["source_month"]
                        or day in observed
                    ):
                        raise ValueError("out-of-month or noncontiguous source date")
                    # Fail closed on malformed/crossed ticks; never repair or skip.
                    ticks = tuple(parse_tick(line) for line in group)
                    bars = tuple(
                        QuoteBar(
                            opening_timestamp=item["timestamp"],
                            tick_count=item["ticks"],
                            **{
                                f"{side}_{key}": value
                                for side in ("bid", "ask")
                                for key, value in item[side].items()
                            },
                        )
                        for item in five_minute_view(ticks)
                    )
                    observed[day] = (bars, len(ticks))
        m = int(month["source_month"][-2:])
        for n in range(1, calendar.monthrange(2024, m)[1] + 1):
            day = date(2024, m, n)
            start = datetime(2024, m, n, 5, tzinfo=UTC)
            bars, ticks = observed.get(day, ((), 0))
            dataset = QuoteDataset(
                provider="HISTDATA",
                provider_symbol="XAU/USD",
                source_archive=month["archive"],
                source_sha256=month["sha256"],
                source_month=month["source_month"],
                selected_source_date=day.isoformat(),
                start=start,
                end=start + timedelta(days=1),
                source_timezone="UTC-05:00 fixed; no DST",
                normalization_version="histdata-ticks-v1",
                aggregation_version="bid-ask-utc-5minute-v1",
            )
            audit = evaluate_policy_day(
                dataset, bars, policy, raw_ticks=ticks, invalid_ticks=0
            )
            prepared.append((dataset, bars, ticks, audit))
        print(month["source_month"], "preflight complete", flush=True)
    eligible = [p for p in prepared if p[3].eligibility.eligible]
    counts = Counter(p[0].source_month for p in eligible)
    if dict(counts) != {"2024-02": 16, "2024-03": 15, "2024-04": 18}:
        raise ValueError(f"eligible counts differ from G2C1: {counts}")
    if sum(len(p[1]) for p in eligible) != 13524 or any(
        len(p[1]) != 276 or len(p[3].coverage.missing_openings) != 12 for p in eligible
    ):
        raise ValueError("bar totals differ from expected evidence")
    engine = build_engine(load_settings())
    try:
        repository = QuoteBarRepository(engine)
        before = snapshot(engine)
        excluded_keys = {
            p[3].coverage.dataset_key for p in prepared if not p[3].eligibility.eligible
        }
        if any(key[0] in excluded_keys for key in before):
            raise ValueError("excluded policy dataset already exists")
        records = []
        for dataset, bars, ticks, audit in prepared:
            record = {
                "manifest": audit.coverage.provenance.model_dump(mode="json"),
                "eligibility": audit.eligibility.model_dump(mode="json"),
                "observed_bars": len(bars),
                "missing_openings": [
                    t.isoformat() for t in audit.coverage.missing_openings
                ],
                "raw_ticks": ticks,
                "invalid_ticks": 0,
            }
            for pass_number in (1, 2):
                result = import_policy_day(
                    repository, dataset, bars, policy, raw_ticks=ticks, invalid_ticks=0
                )
                record[f"pass_{pass_number}"] = (
                    result.imported.model_dump(mode="json") if result.imported else None
                )
                if pass_number == 2 and result.imported and result.imported.inserted:
                    raise ValueError("second import inserted duplicates")
            if audit.eligibility.eligible:
                stored = repository.get_bars(
                    dataset_key=audit.coverage.dataset_key,
                    symbol="XAUUSD",
                    interval="5minute",
                    start=dataset.start,
                    end=dataset.end,
                )
                if stored != tuple(sorted(bars, key=lambda b: b.opening_timestamp)):
                    raise ValueError("stored bars differ from validated observations")
            records.append(record)
        after = snapshot(engine)
        if any(after.get(k) != v for k, v in before.items()):
            raise ValueError("pre-existing rows changed")
        if any(key[0] in excluded_keys for key in after):
            raise ValueError("excluded date was persisted")
        keys = {p[3].coverage.dataset_key for p in eligible}
        if sum(k[0] in keys for k in after) != 13524:
            raise ValueError("persisted policy dataset total differs")
        output = {
            "checkpoint": "G2C2B",
            "completed_at": datetime.now(UTC).isoformat(),
            "policy_version": policy.policy_version,
            "policy_key": policy.policy_key,
            "eligible_days": dict(counts),
            "stored_bars": 13524,
            "preexisting_rows_verified_unchanged": len(before),
            "excluded_policy_rows": 0,
            "first_pass_inserted": sum(
                r["pass_1"]["inserted"] for r in records if r["pass_1"]
            ),
            "second_pass_inserted": sum(
                r["pass_2"]["inserted"] for r in records if r["pass_2"]
            ),
            "days": records,
        }
        Path("docs/histdata-feb-apr-persistence.json").write_text(
            json.dumps(output, indent=2) + "\n"
        )
        print({k: v for k, v in output.items() if k != "days"}, flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
