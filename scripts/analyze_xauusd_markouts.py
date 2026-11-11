"""Read-only fixed forward-price study; no backtest, sizing or portfolio blocking."""

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal, localcontext
from pathlib import Path
from statistics import median

from trading_bot.config.settings import load_settings
from trading_bot.data.forward_markout import measure_forward
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.database.session import build_engine
from trading_bot.domain.models import Side
from trading_bot.features.research_repository import (
    ResearchFeatureRepository,
    content_hash,
)
from trading_bot.features.xauusd import VERSION
from trading_bot.strategies.xauusd import evaluate_xauusd
from trading_bot.strategies.xauusd_confirmation import evaluate_confirmation


def summary(records):
    available = [r for r in records if r["unavailable"] is None]
    output = {
        "signals": len(records),
        "eligible": len(available),
        "unavailable": len(records) - len(available),
        "unavailable_reasons": dict(
            Counter(r["unavailable"] for r in records if r["unavailable"])
        ),
    }
    with localcontext() as ctx:
        ctx.prec = 60
        for name in ("markout", "favorable", "adverse"):
            values = [r[name] for r in available]
            output[f"mean_{name}"] = (
                sum(values, Decimal(0)) / len(values) if values else None
            )
            output[f"median_{name}"] = median(values) if values else None
        for name, sign in (("positive", 1), ("negative", -1), ("zero", 0)):
            count = sum(
                (
                    (r["markout"] > 0)
                    if sign == 1
                    else (r["markout"] < 0) if sign == -1 else r["markout"] == 0
                )
                for r in available
            )
            output[name] = count
            output[f"pct_{name}"] = (
                Decimal(count) * 100 / len(available) if available else None
            )
    return output


def main():
    paths = [
        Path("docs/xauusd-3000-sensitivity-corrected.json"),
        Path("docs/xauusd-v2-momentum-confirmation-development.json"),
    ]
    baseline, candidate = [json.loads(p.read_text()) for p in paths]
    assert (
        baseline["provenance"]["source_evidence"]
        == candidate["provenance"]["source_evidence"]
    )
    frozen_decisions = [
        {d["decision_key"] for d in r["result"]["decisions"]}
        for r in (baseline, candidate)
    ]
    seen_decisions = [set(), set()]
    engine = build_engine(load_settings()).execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    )
    records, counts = [], Counter()
    try:
        bars_repo, features_repo = QuoteBarRepository(
            engine
        ), ResearchFeatureRepository(engine)
        for evidence in baseline["provenance"]["source_evidence"]:
            ds = QuoteDataset.model_validate(evidence["dataset"])
            bars = bars_repo.get_bars(
                dataset_key=ds.dataset_key,
                symbol="XAUUSD",
                interval="5minute",
                start=ds.start,
                end=ds.end,
            )
            features = features_repo.get_rows(
                source_dataset_key=ds.dataset_key,
                symbol="XAUUSD",
                feature_version=VERSION,
                start=ds.start,
                end=ds.end,
                as_of=ds.end,
            )
            assert (
                content_hash([b.model_dump(mode="json") for b in bars])
                == evidence["bar_content_hash"]
            )
            assert (
                content_hash([r.model_dump(mode="json") for r in features])
                == evidence["feature_content_hash"]
            )
            boundaries = tuple(
                datetime.fromisoformat(t) for t in evidence["boundary_times"]
            )
            for row in features:
                v1 = evaluate_xauusd(row, as_of=row.available_at)
                v2 = evaluate_confirmation(row, as_of=row.available_at)
                for index, d in enumerate((v1, v2)):
                    seen_decisions[index].add(content_hash(d.model_dump(mode="json")))
                counts[f"V1_{v1.action}"] += 1
                counts[f"V2_{v2.action}"] += 1
                assert v2.side is None or v2.side == v1.side
                if v1.side is None:
                    continue
                for horizon in (5, 10, 20):
                    measured = measure_forward(
                        ds,
                        bars,
                        signal_opening=v1.opening_timestamp,
                        side=v1.side,
                        horizon=horizon,
                        boundary_times=boundaries,
                    )
                    records.append(
                        asdict(measured)
                        | {
                            "dataset_key": ds.dataset_key,
                            "source_date": ds.selected_source_date,
                            "signal_timestamp": v1.available_at,
                            "signal_opening": v1.opening_timestamp,
                            "side": v1.side.name,
                            "retained_v2": v2.side is not None,
                            "v1_decision_key": content_hash(v1.model_dump(mode="json")),
                        }
                    )
    finally:
        engine.dispose()
    assert seen_decisions == frozen_decisions
    assert (
        counts["V1_BUY"],
        counts["V1_SELL"],
        counts["V2_BUY"],
        counts["V2_SELL"],
    ) == (2140, 1944, 2008, 1789)
    results = {}
    for cohort in ("V1", "V2", "REMOVED"):
        selected = [
            r for r in records if cohort == "V1" or r["retained_v2"] == (cohort == "V2")
        ]
        results[cohort] = {}
        for horizon in (5, 10, 20):
            results[cohort][str(horizon)] = {}
            for side in ("ALL", Side.BUY.name, Side.SELL.name):
                subset = [
                    r
                    for r in selected
                    if r["horizon"] == horizon and (side == "ALL" or r["side"] == side)
                ]
                results[cohort][str(horizon)][side] = summary(subset)
    for horizon in ("5", "10", "20"):
        for side in ("ALL", "BUY", "SELL"):
            for key in (
                "signals",
                "eligible",
                "unavailable",
                "positive",
                "negative",
                "zero",
            ):
                assert (
                    results["V1"][horizon][side][key]
                    == results["V2"][horizon][side][key]
                    + results["REMOVED"][horizon][side][key]
                )
    assert results["REMOVED"]["5"]["ALL"]["signals"] == 287
    report = {
        "checkpoint": "G2C4D2",
        "development_in_sample": True,
        "horizons": [5, 10, 20],
        "signal_counts": dict(counts),
        "source_report_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
        "source_report_identities": [
            baseline["report_identity"],
            candidate["report_identity"],
        ],
        "source_evidence": baseline["provenance"]["source_evidence"],
        "definitions": {
            "entry": (
                "signal bar completion = next continuous bar opening; "
                "entry bar counts as horizon bar 1"
            ),
            "BUY": "endpoint BID close minus entry ASK open",
            "SELL": "entry BID open minus endpoint ASK close",
            "favorable": (
                "max(0, max BID high-entry ASK) BUY; max(0, entry "
                "BID-min ASK low) SELL"
            ),
            "adverse": (
                "max(0, entry ASK-min BID low) BUY; max(0, max ASK "
                "high-entry BID) SELL"
            ),
            "window": (
                "entry bar through horizon bar inclusive; ending at a "
                "boundary allowed, crossing forbidden"
            ),
            "independence": (
                "overlapping signals retained; not independent or a "
                "portfolio backtest"
            ),
        },
        "results": results,
        "observations": records,
    }
    serialized = json.loads(json.dumps(report, default=str))
    serialized["content_hash"] = content_hash(serialized)
    Path("docs/xauusd-forward-signal-quality.json").write_text(
        json.dumps(serialized, indent=2) + "\n"
    )
    print(
        json.dumps(
            {c: {h: g["ALL"] for h, g in hs.items()} for c, hs in results.items()},
            default=str,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
