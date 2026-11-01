"""G2C4A read-only study of the approved persisted baseline feature dataset."""

import json
from collections import Counter
from decimal import Decimal, localcontext
from pathlib import Path

from trading_bot.config.settings import load_settings
from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.database.session import build_engine
from trading_bot.features.research_repository import (
    ResearchFeatureRepository,
    content_hash,
)
from trading_bot.features.xauusd import VERSION as FEATURE_VERSION
from trading_bot.strategies.xauusd import VERSION, evaluate_xauusd


def main():
    source = json.loads(
        Path("docs/xauusd-baseline-feature-persistence.json").read_text()
    )
    engine = build_engine(load_settings())
    try:
        repo = ResearchFeatureRepository(engine)
        rows = []
        seen = set()
        for record in source["first_pass"]:
            manifest = record["manifest"]
            ds = QuoteDataset.model_validate(manifest["source"])
            if (
                ds.source_month not in ("2024-02", "2024-03", "2024-04")
                or ds.dataset_key in seen
                or ds.dataset_key != manifest["source_dataset_key"]
            ):
                raise ValueError("invalid study source selection")
            seen.add(ds.dataset_key)
            part = repo.get_rows(
                source_dataset_key=ds.dataset_key,
                symbol="XAUUSD",
                feature_version=FEATURE_VERSION,
                start=ds.start,
                end=ds.end,
                as_of=ds.end,
            )
            if (
                len(part) != manifest["feature_row_count"]
                or content_hash([r.model_dump(mode="json") for r in part])
                != manifest["content_hash"]
            ):
                raise ValueError(
                    "persisted feature content differs from approved evidence"
                )
            rows.extend((ds.source_month, r) for r in part)
        if len(seen) != 49 or len(rows) != 13524:
            raise ValueError("bounded study scope discrepancy")
        counts = {m: Counter() for m in ("2024-02", "2024-03", "2024-04")}
        rejection = {m: Counter() for m in counts}
        digests = []
        for month, row in rows:
            decision = evaluate_xauusd(row, as_of=row.available_at)
            counts[month][decision.action] += 1
            if decision.action == "NO_TRADE":
                rejection[month][decision.reasons[-1]] += 1
            digests.append(content_hash(decision.model_dump(mode="json")))
        months = {}
        for month, c in counts.items():
            total = sum(c.values())
            with localcontext() as context:
                context.prec = 28
                percentages = {
                    k: str((Decimal(c[k]) * 100 / total).quantize(Decimal("0.01")))
                    for k in ("BUY", "SELL", "NO_TRADE")
                }
            months[month] = {
                "rows": total,
                "counts": {k: c[k] for k in ("BUY", "SELL", "NO_TRADE")},
                "percentages": percentages,
                "major_no_trade_reasons": dict(rejection[month]),
            }
        overall = sum(counts.values(), Counter())
        overall_reasons = sum(rejection.values(), Counter())
        report = {
            "strategy_version": VERSION,
            "feature_set_version": FEATURE_VERSION,
            "source_feature_dataset_key": source["feature_dataset_key"],
            "rows_evaluated": len(rows),
            "months": months,
            "counts": dict(overall),
            "percentages": {
                k: str(
                    (Decimal(overall[k]) * 100 / len(rows)).quantize(Decimal("0.01"))
                )
                for k in ("BUY", "SELL", "NO_TRADE")
            },
            "major_no_trade_reasons": dict(overall_reasons),
            "decision_content_hash": content_hash(digests),
            "near_universal_signal_warning": (overall["BUY"] + overall["SELL"]) * 100
            >= 90 * len(rows),
            "thresholds_tuned": False,
            "database_writes": 0,
        }
        Path("docs/xauusd-baseline-signal-study.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
