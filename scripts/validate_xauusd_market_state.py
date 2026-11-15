"""Frozen G3 taxonomy applied read-only to the existing May–July dataset."""

import hashlib
import json
from collections import Counter
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from pathlib import Path

import yaml

from trading_bot.config.settings import load_settings
from trading_bot.data.gap_policy import load_gap_policy
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.data.research_input import approved_research_inputs
from trading_bot.database.session import build_engine
from trading_bot.domain.sessions import ResearchSessionClassifier, SessionConfig
from trading_bot.features.market_state_v2 import (
    MarketTaxonomyV2,
    calculate_market_state_v2,
)
from trading_bot.features.market_taxonomy import (
    STATES,
    WARMUP,
    StateObservation,
    temporal_summary,
)
from trading_bot.features.research_repository import (
    ResearchFeatureRepository,
    content_hash,
)
from trading_bot.features.xauusd import VERSION as BASELINE
from trading_bot.features.xauusd import calculate_xauusd

SOURCE = Path("docs/xauusd-may-july-validation-dataset.json")
CONFIG = Path("config/xauusd_market_state_taxonomy_v2.yaml")
G3 = Path("docs/xauusd-market-state-taxonomy-v2.json")
G2 = Path("docs/xauusd-market-state-characterization.json")
IDENTITY = "811d9f5db6bf55d128147b2247197d2364e31b185d005c69b33b2349ffa589c5"
OUTPUT = Path("docs/xauusd-market-state-validation-may-july.json")


def verified_report(path):
    report = json.loads(path.read_text())
    if (
        content_hash({k: v for k, v in report.items() if k != "content_hash"})
        != report["content_hash"]
    ):
        raise ValueError("frozen report hash mismatch")
    return report


def load_frozen_taxonomy():
    raw = yaml.safe_load(CONFIG.read_text())
    if raw != verified_report(G3)["policy"]:
        raise ValueError("frozen G3 taxonomy differs")
    return MarketTaxonomyV2.model_validate_json(json.dumps(raw))


def verified_manifest():
    source = json.loads(SOURCE.read_text())
    manifest = source["manifest"]
    if source["dataset_key"] != IDENTITY or content_hash(manifest) != IDENTITY:
        raise ValueError("validation dataset identity mismatch")
    days = manifest["days"]
    if (
        len(days) != 50
        or manifest["bar_count"] != 13800
        or manifest["feature_count"] != 13800
    ):
        raise ValueError("validation size mismatch")
    if Counter(d["dataset"]["source_month"] for d in days) != {
        "2024-05": 17,
        "2024-06": 15,
        "2024-07": 18,
    }:
        raise ValueError("validation partition mismatch")
    return manifest


def percent(count, total):
    return str(Decimal(100) * count / total) if total else "0"


def frequencies(records):
    counts = Counter(r["core"] for r in records)
    valid = len(records) - counts[WARMUP]
    attrs = Counter(r["attribute"] or "UNAVAILABLE" for r in records)
    available = len(records) - attrs["UNAVAILABLE"]
    return {
        "rows": len(records),
        "classified": valid,
        "unclassified": counts[WARMUP],
        "core": {
            s: {"count": counts[s], "pct_classified": percent(counts[s], valid)}
            for s in STATES
        },
        "attribute_valid": available,
        "attribute_unavailable": attrs["UNAVAILABLE"],
        "attribute": {
            s: {"count": attrs[s], "pct_valid": percent(attrs[s], available)}
            for s in ("COMPRESSED", "NEUTRAL", "EXPANDED")
        },
    }


def persistence(sequence):
    runs, matrix = temporal_summary(tuple(sequence))
    stats = {}
    for state, values in runs.items():
        v = sorted(values)
        if not v:
            stats[state] = None
            continue
        n = len(v)
        numbers = {
            "min": Decimal(v[0]),
            "median": Decimal(v[(n - 1) // 2] + v[n // 2]) / 2,
            "mean": Decimal(sum(v)) / n,
            "p95": Decimal(v[(95 * n + 99) // 100 - 1]),
            "max": Decimal(v[-1]),
        }
        stats[state] = {
            "runs": n,
            "bars": {k: str(x) for k, x in numbers.items()},
            "minutes": {k: str(x * 5) for k, x in numbers.items()},
        }
    total = sum(sum(row.values()) for row in matrix.values())
    same = sum(matrix[s][s] for s in STATES)
    return {
        "run_lengths": stats,
        "run_bar_count": sum(sum(v) for v in runs.values()),
        "transition_counts": matrix,
        "transition_probabilities": {
            a: {
                b: str(Decimal(n) / sum(row.values())) if sum(row.values()) else "0"
                for b, n in row.items()
            }
            for a, row in matrix.items()
        },
        "transitions": total,
        "same_state_transitions": same,
        "same_state_pct": percent(same, total),
    }


def summarize(records, sequence):
    result = {
        "overall": frequencies(records),
        "months": {
            m: frequencies([r for r in records if r["month"] == m])
            for m in ("2024-05", "2024-06", "2024-07")
        },
        "sessions": {
            s: frequencies([r for r in records if r["session"] == s])
            for s in (
                "ASIA",
                "LONDON",
                "LONDON_NEW_YORK_OVERLAP",
                "NEW_YORK",
                "OFF_SESSION",
            )
        },
        **persistence(sequence),
    }
    if (
        sum(s["classified"] for s in result["sessions"].values())
        != result["overall"]["classified"]
    ):
        raise ValueError("session counts do not reconcile")
    if result["run_bar_count"] != result["overall"]["classified"]:
        raise ValueError("run counts do not reconcile")
    return result


def generate(engine):
    manifest = verified_manifest()
    taxonomy = load_frozen_taxonomy()
    gap_policy = load_gap_policy(Path("config/histdata_xauusd_validation_gap_v1.yaml"))
    if gap_policy.policy_key != manifest["policy_key"]:
        raise ValueError("validation gap policy differs")
    br, fr = QuoteBarRepository(engine), ResearchFeatureRepository(engine)
    classifier = ResearchSessionClassifier(
        SessionConfig.load(Path("config/xauusd_sessions.yaml"))
    )
    records, sequence, evidence = [], [], []
    resets, unavailable = Counter(), Counter()
    for day in manifest["days"]:
        ds = QuoteDataset.model_validate(day["dataset"])
        if ds.dataset_key != day["dataset_key"]:
            raise ValueError("source dataset identity differs")
        bars = br.get_bars(
            dataset_key=ds.dataset_key,
            symbol="XAUUSD",
            interval="5minute",
            start=ds.start,
            end=ds.end,
        )
        baseline = fr.get_rows(
            source_dataset_key=ds.dataset_key,
            symbol="XAUUSD",
            feature_version=BASELINE,
            start=ds.start,
            end=ds.end,
            as_of=ds.end,
        )
        if (
            len(bars) != 276
            or len(baseline) != 276
            or content_hash([b.model_dump(mode="json") for b in bars])
            != day["bar_content_hash"]
            or content_hash([r.model_dump(mode="json") for r in baseline])
            != day["feature_content_hash"]
        ):
            raise ValueError("frozen validation bars/baseline differ")
        batch = approved_research_inputs(ds, bars, gap_policy, as_of=ds.end)
        if calculate_xauusd(batch) != baseline:
            raise ValueError("baseline formulas differ")
        rows = calculate_market_state_v2(batch)
        for cut in (1, 13, 37, 205, 250):
            prefix = batch.model_copy(
                update={
                    "inputs": batch.inputs[:cut],
                    "as_of": batch.inputs[cut - 1].available_at,
                }
            )
            if calculate_market_state_v2(prefix) != rows[:cut]:
                raise ValueError("prefix causality failed")
        for row in rows:
            core, attribute = taxonomy.classify(row)
            reset = row.baseline.sequence_reset
            if reset:
                resets[reset] += 1
            unavailable[row.ratio_unavailable or "AVAILABLE"] += 1
            records.append(
                {
                    "month": ds.source_month,
                    "session": classifier.classify(row.available_at).value,
                    "core": core,
                    "attribute": attribute,
                }
            )
            sequence.append(
                StateObservation(
                    ds.dataset_key,
                    row.baseline.input.opening_timestamp,
                    core,
                    reset is not None,
                )
            )
        evidence.append(
            {
                "dataset_key": ds.dataset_key,
                "bar_hash": day["bar_content_hash"],
                "baseline_hash": day["feature_content_hash"],
                "v2_hash": content_hash([r.model_dump(mode="json") for r in rows]),
            }
        )
    if resets != {"DATASET_BOUNDARY": 50, "DISCONTINUITY": 50}:
        raise ValueError("unexpected validation reset structure")
    return {
        "dataset_key": IDENTITY,
        "days": 50,
        "bars": len(records),
        "baseline_rows_verified": 13800,
        "policy": taxonomy.model_dump(mode="json"),
        "resets": dict(resets),
        "ratio_availability": dict(unavailable),
        "datasets": evidence,
        "classification_hash": content_hash(records),
        **summarize(records, sequence),
    }


def comparison(result):
    development = verified_report(G2)
    corrected = verified_report(G3)
    old = development["overall"]["states"]
    new = result["overall"]["core"]
    shifts = {}
    for name, match in (
        ("volatility", lambda s, k: s.startswith(k)),
        ("efficiency", lambda s, k: s.endswith(k)),
    ):
        keys = (
            ("LOW_VOL", "NORMAL_VOL", "HIGH_VOL")
            if name == "volatility"
            else ("CHOPPY", "MIXED", "DIRECTIONAL")
        )
        shifts[name] = {}
        for key in keys:
            a = Decimal(
                percent(
                    sum(v["count"] for s, v in old.items() if match(s, key)),
                    development["overall"]["classified"],
                )
            )
            b = Decimal(
                percent(
                    sum(v["count"] for s, v in new.items() if match(s, key)),
                    result["overall"]["classified"],
                )
            )
            shifts[name][key] = {
                "development_pct": str(a),
                "validation_pct": str(b),
                "shift_pp": str(b - a),
            }
    shifts["attribute"] = {}
    for key, v in corrected["overall"]["states"].items():
        a, b = Decimal(v["pct_valid"]), Decimal(
            result["overall"]["attribute"][key]["pct_valid"]
        )
        shifts["attribute"][key] = {
            "development_pct": str(a),
            "validation_pct": str(b),
            "shift_pp": str(b - a),
        }
    matrix = development["transition_counts"]
    old_same = percent(
        sum(matrix[s][s] for s in STATES), sum(sum(r.values()) for r in matrix.values())
    )
    shifts["same_state_pct"] = {
        "development": old_same,
        "validation": result["same_state_pct"],
        "shift_pp": str(Decimal(result["same_state_pct"]) - Decimal(old_same)),
    }
    shifts["development_run_lengths"] = development["run_lengths"]
    return shifts


def main():
    engine = build_engine(load_settings())
    try:
        with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
            first, second = generate(engine), generate(engine)
            if first != second:
                raise ValueError("deterministic rerun differs")
            first["development_comparison"] = comparison(first)
    finally:
        engine.dispose()
    report = {
        "report_version": "xauusd-market-state-validation-may-july-v1",
        "stability_conclusion": "SHIFTED BUT STILL INFORMATIVE",
        "assessment_method": (
            "Qualitative description, not a numeric saturation rule: "
            "all nine states remain populated; volatility mix shifts, "
            "efficiency remains separated, and both compression/expansion "
            "remain represented."
        ),
        "rerun_equal": True,
        "thresholds_recalibrated": False,
        "strategy_outcomes_inspected": False,
        "august_october": "LOCKED_UNPROCESSED",
        "prefix_causality": True,
        "file_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                SOURCE,
                CONFIG,
                G3,
                G2,
                Path("src/trading_bot/features/market_state_v2.py"),
                Path("src/trading_bot/features/market_state.py"),
                Path("config/xauusd_sessions.yaml"),
            )
        },
        **first,
    }
    report["content_hash"] = content_hash(report)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("overall", "development_comparison", "same_state_pct")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
