"""E2B: frozen validation bars/features only; no strategy imports or evaluation."""

import argparse
import hashlib
import io
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from itertools import groupby
from pathlib import Path
from zipfile import ZipFile

from trading_bot.config.settings import load_settings
from trading_bot.data.gap_policy import load_gap_policy
from trading_bot.data.policy_import import evaluate_policy_day, import_policy_day
from trading_bot.data.providers.histdata import five_minute_view, parse_tick
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.data.research_input import approved_research_inputs
from trading_bot.database.session import build_engine
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.features.research_repository import (
    ResearchFeatureRepository,
    content_hash,
)
from trading_bot.features.xauusd import VERSION, calculate_xauusd

POLICY_PATH = Path("config/histdata_xauusd_validation_gap_v1.yaml")
EVIDENCE_PATH = Path("docs/histdata-validation-may-july-2024.json")
EXPECTED = {"2024-05": 17, "2024-06": 15, "2024-07": 18}
CHECKSUMS = {
    "2024-05": "ec9128f89afb2091912310ef55a1cd6006475f27817707a0d2c08983fd74b5aa",
    "2024-06": "a94e12301134b02899f8402d6f990fb65d2e2a837daf243cb2a642625cb8a980",
    "2024-07": "cec29b35b592b3ca9810b84e0af81ea6e84af78d1d16f22e2ee2eb4bddb7c810",
}


def dataset(month, day):
    start = datetime.fromisoformat(day + "T05:00:00+00:00")
    return QuoteDataset(
        provider="HISTDATA",
        provider_symbol="XAU/USD",
        source_archive=month["archive"]["filename"],
        source_sha256=month["archive"]["sha256"],
        source_month=month["month"],
        selected_source_date=day,
        start=start,
        end=start + timedelta(days=1),
        source_timezone="UTC-05:00 fixed; no DST",
        normalization_version="histdata-ticks-v1",
        aggregation_version="bid-ask-utc-5minute-v1",
    )


def verify_scope(policy, evidence):
    if [m["month"] for m in evidence["months"]] != list(EXPECTED):
        raise ValueError("unexpected validation months")
    dates = [
        d["date"]
        for m in evidence["months"]
        for d in m["days"]
        if d["proposed_eligible"]
    ]
    counts = Counter(d[:7] for d in dates)
    if dict(counts) != EXPECTED or len(set(dates)) != 50:
        raise ValueError("E2A eligible counts differ; stop")
    if sorted(s.effective_start_date.isoformat() for s in policy.segments) != sorted(
        dates
    ) or any(s.effective_end_date != s.effective_start_date for s in policy.segments):
        raise ValueError("policy must exactly encode the 50-date allowlist")
    for m in evidence["months"]:
        if m["archive"]["sha256"] != CHECKSUMS[m["month"]]:
            raise ValueError("wrong archive provenance")
    report_hash = hashlib.sha256(EVIDENCE_PATH.read_bytes()).hexdigest()
    for s in policy.segments:
        if (
            s.evidence.archive_sha256 != CHECKSUMS[s.evidence.source_month]
            or s.evidence.report_sha256 != report_hash
            or s.evidence.report_version != evidence["version"]
            or s.evidence.report_reference != str(EVIDENCE_PATH)
            or tuple(i for r in s.allowed_missing_ranges for i in r.indices)
            != tuple(range(204, 216))
        ):
            raise ValueError("policy evidence or gap mismatch")
    return set(dates)


def prepare(root, policy):
    evidence = json.loads(EVIDENCE_PATH.read_text())
    digest = evidence.pop("content_sha256")
    if (
        hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
        != digest
    ):
        raise ValueError("E2A content hash mismatch")
    allowed = verify_scope(policy, evidence)
    for m in evidence["months"]:
        if (
            hashlib.sha256((root / m["archive"]["filename"]).read_bytes()).hexdigest()
            != CHECKSUMS[m["month"]]
        ):
            raise ValueError("local archive checksum mismatch")
    prepared = []
    for m in evidence["months"]:
        days = {d["date"]: d for d in m["days"]}
        seen = set()
        with ZipFile(root / m["archive"]["filename"]) as archive:
            with archive.open(m["member"]) as stream:
                for prefix, lines in groupby(
                    io.TextIOWrapper(stream, encoding="ascii"), lambda s: s[:8]
                ):
                    day = datetime.strptime(prefix, "%Y%m%d").date().isoformat()
                    if day[:7] != m["month"] or day in seen:
                        raise ValueError("unexpected archive date")
                    seen.add(day)
                    if day not in allowed:
                        continue
                    ticks = tuple(parse_tick(line) for line in lines)
                    view = five_minute_view(ticks)
                    if (
                        hashlib.sha256(
                            json.dumps(view, default=str, sort_keys=True).encode()
                        ).hexdigest()
                        != days[day]["observed_bar_sha256"]
                    ):
                        raise ValueError("source bars differ from E2A")
                    if (
                        len(ticks) != days[day]["valid_ticks"]
                        or days[day]["invalid_ticks"]
                    ):
                        raise ValueError("source tick counts differ")
                    bars = tuple(
                        QuoteBar(
                            opening_timestamp=b["timestamp"],
                            tick_count=b["ticks"],
                            **{
                                f"{side}_{k}": v
                                for side in ("bid", "ask")
                                for k, v in b[side].items()
                            },
                        )
                        for b in view
                    )
                    ds = dataset(m, day)
                    audit = evaluate_policy_day(
                        ds, bars, policy, raw_ticks=len(ticks), invalid_ticks=0
                    )
                    if not audit.eligibility.eligible or len(bars) != 276:
                        raise ValueError("allowlisted date failed actual gap policy")
                    bound = audit.coverage.provenance
                    rows = calculate_xauusd(
                        approved_research_inputs(bound, bars, policy, as_of=ds.end)
                    )
                    check_resets(rows)
                    prepared.append((bound, bars, rows))
        print(m["month"], "preflight complete", flush=True)
    if (
        dict(Counter(ds.source_month for ds, _, _ in prepared)) != EXPECTED
        or sum(len(b) for _, b, _ in prepared) != 13800
    ):
        raise ValueError("preflight cardinality discrepancy; no writes")
    return sorted(prepared, key=lambda p: p[0].start)


def check_resets(rows):
    if (
        len(rows) != 276
        or rows[0].sequence_reset != "DATASET_BOUNDARY"
        or rows[204].sequence_reset != "DISCONTINUITY"
    ):
        raise ValueError("unexpected feature resets")
    if sum(r.sequence_reset is not None for r in rows) != 2:
        raise ValueError("expected one dataset and one gap reset per day")
    for row in (rows[0], rows[204]):
        for name in ("ema_12", "ema_26", "rsi_14", "momentum_3", "momentum_12"):
            if row.value(name) is not None:
                raise ValueError("feature state carried across boundary")


def query_bars(repo, ds):
    return repo.get_bars(
        dataset_key=ds.dataset_key,
        symbol="XAUUSD",
        interval="5minute",
        start=ds.start,
        end=ds.end,
    )


def query_features(repo, ds):
    return repo.get_rows(
        source_dataset_key=ds.dataset_key,
        symbol="XAUUSD",
        feature_version=VERSION,
        start=ds.start,
        end=ds.end,
        as_of=ds.end,
    )


def development_snapshot(engine):
    # Read only frozen input-evidence hashes; no strategy evaluator is imported.
    frozen = json.loads(Path("docs/xauusd-forward-signal-quality.json").read_text())
    records = []
    bars, features = QuoteBarRepository(engine), ResearchFeatureRepository(engine)
    for e in frozen["source_evidence"]:
        ds = QuoteDataset.model_validate(e["dataset"])
        if ds.source_month not in ("2024-02", "2024-03", "2024-04"):
            raise ValueError("unexpected development scope")
        b, f = query_bars(bars, ds), query_features(features, ds)
        bh = content_hash([x.model_dump(mode="json") for x in b])
        fh = content_hash([x.model_dump(mode="json") for x in f])
        if bh != e["bar_content_hash"] or fh != e["feature_content_hash"]:
            raise ValueError("frozen development content changed")
        records.append(
            dict(
                dataset_key=ds.dataset_key,
                bars=len(b),
                features=len(f),
                bar_hash=bh,
                feature_hash=fh,
            )
        )
    if (
        len(records) != 49
        or sum(r["bars"] for r in records) != 13524
        or sum(r["features"] for r in records) != 13524
    ):
        raise ValueError("development cardinality differs")
    return {
        "days": 49,
        "bars": 13524,
        "features": 13524,
        "content_hash": content_hash(records),
    }


def materialize(engine, prepared, policy):
    bar_repo, feature_repo = QuoteBarRepository(engine), ResearchFeatureRepository(
        engine
    )
    records = []
    for ds, bars, expected_rows in prepared:
        passes = []
        for _ in (1, 2):
            result = import_policy_day(
                bar_repo,
                ds,
                bars,
                policy,
                raw_ticks=sum(b.tick_count for b in bars),
                invalid_ticks=0,
            )
            if result.imported is None:
                raise ValueError("eligible import rejected")
            passes.append(result.imported)
        stored_bars = query_bars(bar_repo, ds)
        if passes[1].inserted != 0 or passes[1].existing != 276 or stored_bars != bars:
            raise ValueError("bar persistence/idempotency/price mismatch")
        first = feature_repo.generate(ds, policy)
        second = feature_repo.generate(ds, policy)
        rows = query_features(feature_repo, ds)
        if (
            rows != expected_rows
            or second["inserted"] != 0
            or second["existing"] != 276
            or first["feature_dataset_key"] != second["feature_dataset_key"]
        ):
            raise ValueError("feature persistence/idempotency mismatch")
        check_resets(rows)
        records.append(
            {
                "date": ds.selected_source_date,
                "dataset": ds.model_dump(mode="json"),
                "dataset_key": ds.dataset_key,
                "bar_count": len(bars),
                "bar_content_hash": content_hash(
                    [b.model_dump(mode="json") for b in stored_bars]
                ),
                "feature_count": len(rows),
                "feature_content_hash": first["manifest"]["content_hash"],
                "feature_dataset_key": first["feature_dataset_key"],
                "dataset_resets": 1,
                "discontinuity_resets": 1,
                "bar_first_inserted": passes[0].inserted,
                "bar_first_existing": passes[0].existing,
                "bar_second_inserted": passes[1].inserted,
                "bar_second_existing": passes[1].existing,
                "feature_first_inserted": first["inserted"],
                "feature_second_inserted": second["inserted"],
                "feature_second_existing": second["existing"],
            }
        )
    return records


def identity(records, policy):
    fields = (
        "date",
        "dataset",
        "dataset_key",
        "bar_count",
        "bar_content_hash",
        "feature_count",
        "feature_content_hash",
        "feature_dataset_key",
    )
    return {
        "partition": "FIRST_UNSEEN_VALIDATION_MAY_JULY_2024",
        "version": "G2C4E2B-v1",
        "provider": "HISTDATA",
        "canonical_symbol": "XAUUSD",
        "provider_symbol": "XAU/USD",
        "archives": CHECKSUMS,
        "policy_version": policy.policy_version,
        "policy_key": policy.policy_key,
        "feature_version": VERSION,
        "normalization_version": "histdata-ticks-v1",
        "aggregation_version": "bid-ask-utc-5minute-v1",
        "input_semantics_version": "g2c3a-research-input-v1",
        "bar_count": sum(r["bar_count"] for r in records),
        "feature_count": sum(r["feature_count"] for r in records),
        "days": [
            {k: r[k] for k in fields} for r in sorted(records, key=lambda r: r["date"])
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_directory", type=Path)
    args = parser.parse_args()
    policy = load_gap_policy(POLICY_PATH)
    prepared = prepare(args.archive_directory, policy)
    engine = build_engine(load_settings())
    try:
        before = development_snapshot(engine)
        records = materialize(engine, prepared, policy)
        after = development_snapshot(engine)
        if before != after:
            raise ValueError("development changed")
        manifest = identity(records, policy)
        if manifest["bar_count"] != 13800 or manifest["feature_count"] != 13800:
            raise ValueError("stored counts differ")
        if any(n.startswith("trading_bot.strategies") for n in sys.modules):
            raise ValueError("strategy module unexpectedly imported")
        output = {
            "dataset_key": content_hash(manifest),
            "manifest": manifest,
            "generated_at": datetime.now(UTC).isoformat(),
            "monthly_days": EXPECTED,
            "development_unchanged": after,
            "dataset_resets": 50,
            "gap_resets": 50,
            "strategy_outcomes_inspected": False,
            "august_october": "LOCKED_UNPROCESSED",
            "import_totals": {
                k: sum(r[k] for r in records)
                for k in records[0]
                if k.startswith(
                    ("bar_first_", "bar_second_", "feature_first_", "feature_second_")
                )
            },
        }
        Path("docs/xauusd-may-july-validation-dataset.json").write_text(
            json.dumps(output, indent=2) + "\n"
        )
        print(
            json.dumps({k: v for k, v in output.items() if k != "manifest"}, indent=2)
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
