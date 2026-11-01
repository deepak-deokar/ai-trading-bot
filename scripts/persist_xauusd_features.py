"""G2C3C: persisted approved Feb–Apr datasets only; no raw files or labels."""

import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from trading_bot.config.settings import load_settings
from trading_bot.data.gap_policy import load_gap_policy
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.data.research_input import approved_research_inputs
from trading_bot.database.models import SystemEvent
from trading_bot.database.session import build_engine
from trading_bot.features.research_repository import (
    ResearchFeatureRepository,
    content_hash,
)
from trading_bot.features.xauusd import calculate_xauusd


def snapshots(engine):
    # Only known research/NSE tables; no account/credential configuration queried.
    result = {}
    with engine.connect() as connection:
        for table in ("bid_ask_bars", "feature_sets", "feature_values"):
            rows = (
                connection.execute(text(f"SELECT to_jsonb(t)::text FROM {table} t"))
                .scalars()
                .all()
            )
            result[table] = {"rows": len(rows), "hash": content_hash(sorted(rows))}
    return result


def main():
    policy = load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml"))
    engine = build_engine(load_settings())
    try:
        datasets = {}
        with Session(engine) as session:
            for details in session.scalars(
                select(SystemEvent.details).where(
                    SystemEvent.event_type == "quote_bar_dataset_import"
                )
            ):
                manifest = details["manifest"]
                if (
                    manifest.get("source_month")
                    not in ("2024-02", "2024-03", "2024-04")
                    or manifest.get("gap_policy_key") != policy.policy_key
                ):
                    continue
                ds = QuoteDataset.model_validate(
                    {
                        k: v
                        for k, v in manifest.items()
                        if k in QuoteDataset.model_fields
                    }
                )
                if ds.dataset_key != details["result"]["dataset_key"]:
                    raise ValueError("source manifest identity mismatch")
                datasets[ds.dataset_key] = ds
        dates = [ds.selected_source_date for ds in datasets.values()]
        if len(dates) != len(set(dates)):
            raise ValueError("multiple dataset identities for a source date")
        bar_repository = QuoteBarRepository(engine)
        counts = Counter()
        total = 0
        # Full scope checked before feature writes; every day passes policy again.
        for ds in datasets.values():
            bars = bar_repository.get_bars(
                dataset_key=ds.dataset_key,
                symbol="XAUUSD",
                interval="5minute",
                start=ds.start,
                end=ds.end,
            )
            batch = approved_research_inputs(ds, bars, policy, as_of=ds.end)
            rows = calculate_xauusd(batch)
            if len(rows) != len(bars):
                raise ValueError("feature row count mismatch")
            counts[ds.source_month] += 1
            total += len(rows)
        if (
            dict(counts) != {"2024-02": 16, "2024-03": 15, "2024-04": 18}
            or total != 13524
        ):
            raise ValueError(f"preflight scope discrepancy: {counts}, {total}")
        before = snapshots(engine)
        repo = ResearchFeatureRepository(engine)
        first = []
        second = []
        ordered = sorted(datasets.values(), key=lambda d: d.start)
        for ds in ordered:
            first.append(repo.generate(ds, policy))
        for ds, prior in zip(ordered, first, strict=True):
            repeat = repo.generate(ds, policy)
            if (
                repeat["inserted"] != 0
                or repeat["feature_dataset_key"] != prior["feature_dataset_key"]
            ):
                raise ValueError("idempotency failure")
            rows = repo.get_rows(
                source_dataset_key=ds.dataset_key,
                symbol="XAUUSD",
                feature_version=prior["manifest"]["feature_set_version"],
                start=ds.start,
                end=ds.end,
                as_of=ds.end,
            )
            if (
                len(rows) != prior["manifest"]["feature_row_count"]
                or content_hash([r.model_dump(mode="json") for r in rows])
                != prior["manifest"]["content_hash"]
            ):
                raise ValueError("stored content differs from generation")
            second.append(repeat)
        after = snapshots(engine)
        if before != after:
            raise ValueError("source bars or existing NSE features changed")
        with engine.connect() as connection:
            stored = connection.execute(
                text(
                    "SELECT source_dataset_key,count(*) FROM research_feature_bars "
                    "GROUP BY source_dataset_key"
                )
            ).all()
        if {key: count for key, count in stored} != {
            d.dataset_key: 276 for d in ordered
        }:
            raise ValueError("unexpected feature scope or excluded dataset rows")
        monthly = {}
        for month in sorted(counts):
            results = [
                r for r in first if r["manifest"]["source"]["source_month"] == month
            ]
            monthly[month] = {
                "approved_days": len(results),
                "input_bars": sum(r["manifest"]["source_bar_count"] for r in results),
                "feature_rows": sum(
                    r["manifest"]["feature_row_count"] for r in results
                ),
                "warmup_rows": sum(r["manifest"]["warmup_rows"] for r in results),
                "discontinuity_resets": sum(
                    r["manifest"]["discontinuity_resets"] for r in results
                ),
                "dataset_resets": sum(r["manifest"]["dataset_resets"] for r in results),
                "first_inserted": sum(r["inserted"] for r in results),
            }
        report = {
            "feature_dataset_key": content_hash(
                sorted(r["feature_dataset_key"] for r in first)
            ),
            "months": monthly,
            "source_snapshots_unchanged": before,
            "first_inserted": sum(r["inserted"] for r in first),
            "second_inserted": sum(r["inserted"] for r in second),
            "second_existing": sum(r["existing"] for r in second),
            "first_pass": first,
            "second_pass": second,
        }
        Path("docs/xauusd-baseline-feature-persistence.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(
            json.dumps(
                {
                    k: v
                    for k, v in report.items()
                    if k not in ("first_pass", "second_pass")
                },
                indent=2,
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
