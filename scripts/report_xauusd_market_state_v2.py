"""Development-only correction report; no strategy or outcome inputs."""

import hashlib
import json
from collections import Counter
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from itertools import groupby
from pathlib import Path

import yaml
from characterize_xauusd_market_state import analyze, load_rows

from trading_bot.config.settings import load_settings
from trading_bot.data.research_input import ApprovedResearchInputs
from trading_bot.database.session import build_engine
from trading_bot.domain.sessions import ResearchSessionClassifier, SessionConfig
from trading_bot.features.market_state_v2 import (
    MarketTaxonomyV2,
    calculate_market_state_v2,
)
from trading_bot.features.market_taxonomy import MarketTaxonomy
from trading_bot.features.research_repository import content_hash

CONFIG = Path("config/xauusd_market_state_taxonomy_v2.yaml")
OLD = Path("docs/xauusd-market-state-characterization.json")


def run(engine):
    evidence, loaded = load_rows(engine)
    old = json.loads(OLD.read_text())
    if (
        content_hash({k: v for k, v in old.items() if k != "content_hash"})
        != old["content_hash"]
    ):
        raise ValueError("G2 report identity differs")
    recalibrated = analyze(evidence, loaded)
    if (
        recalibrated["policy"] != old["policy"]
        or recalibrated["overall"] != old["overall"]
    ):
        raise ValueError("STOP: frozen thresholds or core counts changed")
    p = dict(old["policy"])
    p.update(
        taxonomy_version="xauusd-market-state-taxonomy-v2",
        feature_set_version="xauusd-market-state-features-v2",
        range_feature="volatility_ratio_12_36",
    )
    policy = MarketTaxonomyV2.model_validate_json(json.dumps(p))
    classifier = ResearchSessionClassifier(
        SessionConfig.load(Path("config/xauusd_sessions.yaml"))
    )
    records, datasets, reasons = [], [], Counter()
    for _, group in groupby(loaded, key=lambda item: item[0].dataset_key):
        pairs = list(group)
        ds = pairs[0][0]
        batch = ApprovedResearchInputs(
            dataset_key=ds.dataset_key,
            policy_key=ds.gap_policy_key,
            policy_version=ds.gap_policy_version,
            as_of=ds.end,
            inputs=tuple(r.input for _, r in pairs),
        )
        rows = calculate_market_state_v2(batch)
        old_policy = MarketTaxonomy.model_validate_json(json.dumps(old["policy"]))
        for (_, baseline), row in zip(pairs, rows, strict=True):
            if row.baseline != baseline:
                raise ValueError("STOP: v1 measurements changed")
            core, attribute = policy.classify(row)
            if core != old_policy.classify(baseline)[0]:
                raise ValueError("STOP: core classification changed")
            reasons[row.ratio_unavailable or "AVAILABLE"] += 1
            records.append(
                {
                    "month": ds.source_month,
                    "session": classifier.classify(row.available_at).value,
                    "core": core,
                    "attribute": attribute,
                }
            )
        for cut in (1, 13, 37, 205, 250):
            prefix = batch.model_copy(
                update={
                    "inputs": batch.inputs[:cut],
                    "as_of": batch.inputs[cut - 1].available_at,
                }
            )
            if calculate_market_state_v2(prefix) != rows[:cut]:
                raise ValueError("causality failed")
        datasets.append(
            {
                "dataset_key": ds.dataset_key,
                "rows": len(rows),
                "v1_hash": content_hash(
                    [r.baseline.model_dump(mode="json") for r in rows]
                ),
                "v2_hash": content_hash([r.model_dump(mode="json") for r in rows]),
            }
        )

    def counts(subset):
        c = Counter(r["attribute"] or "UNAVAILABLE" for r in subset)
        valid = len(subset) - c["UNAVAILABLE"]
        return {
            "rows": len(subset),
            "valid": valid,
            "unavailable": c["UNAVAILABLE"],
            "states": {
                s: {
                    "count": c[s],
                    "pct_valid": str(Decimal(100) * c[s] / valid) if valid else "0",
                    "pct_all": (
                        str(Decimal(100) * c[s] / len(subset)) if subset else "0"
                    ),
                }
                for s in ("COMPRESSED", "NEUTRAL", "EXPANDED")
            },
        }

    features = {
        "feature_set_version": policy.feature_set_version,
        "days": 49,
        "rows": len(records),
        "availability": dict(reasons),
        "datasets": datasets,
        "prefix_causality": True,
        "v1_measurements_identical": True,
    }
    taxonomy = {
        "policy": policy.model_dump(mode="json"),
        "core_counts_identical": True,
        "thresholds_identical": True,
        "core_counts": dict(Counter(r["core"] for r in records)),
        "overall": counts(records),
        "months": {
            m: counts([r for r in records if r["month"] == m])
            for m in ("2024-02", "2024-03", "2024-04")
        },
        "sessions": {
            s: counts([r for r in records if r["session"] == s])
            for s in (
                "ASIA",
                "LONDON",
                "LONDON_NEW_YORK_OVERLAP",
                "NEW_YORK",
                "OFF_SESSION",
            )
        },
        "classification_hash": content_hash(records),
    }
    return features, taxonomy


def main():
    engine = build_engine(load_settings())
    try:
        with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
            first, second = run(engine), run(engine)
    finally:
        engine.dispose()
    if first != second:
        raise ValueError("deterministic rerun differs")
    config = first[1]["policy"]
    if CONFIG.exists() and yaml.safe_load(CONFIG.read_text()) != config:
        raise ValueError("refusing to overwrite different frozen v2 config")
    if not CONFIG.exists():
        CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
    provenance = {
        "g1_report_sha256": hashlib.sha256(
            Path("docs/xauusd-market-state-features.json").read_bytes()
        ).hexdigest(),
        "g2_report_sha256": hashlib.sha256(OLD.read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(
            Path("src/trading_bot/features/market_state_v2.py").read_bytes()
        ).hexdigest(),
        "session_config_sha256": hashlib.sha256(
            Path("config/xauusd_sessions.yaml").read_bytes()
        ).hexdigest(),
        "rerun_equal": True,
        "may_july_used": False,
        "august_october": "LOCKED_UNPROCESSED",
    }
    for name, result in zip(("features", "taxonomy"), first, strict=True):
        report = provenance | result
        report["content_hash"] = content_hash(report)
        Path(f"docs/xauusd-market-state-{name}-v2.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
    print(json.dumps(first[1], indent=2))


if __name__ == "__main__":
    main()
