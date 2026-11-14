"""Development-only descriptive taxonomy; no strategy or outcome imports."""

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
from trading_bot.features.market_state import calculate_market_state
from trading_bot.features.market_taxonomy import (
    STATES,
    WARMUP,
    MarketTaxonomy,
    StateObservation,
    quantile,
    temporal_summary,
)
from trading_bot.features.research_repository import content_hash

SOURCE = Path("docs/xauusd-market-state-features.json")
CONFIG = Path("config/xauusd_market_state_taxonomy_v1.yaml")
OUTPUT = Path("docs/xauusd-market-state-characterization.json")


def percent(n, total):
    return str(Decimal(100) * n / total) if total else "0"


def load_rows(engine):
    evidence = json.loads(SOURCE.read_text())
    if (
        content_hash({k: v for k, v in evidence.items() if k != "content_hash"})
        != evidence["content_hash"]
    ):
        raise ValueError("G1 report hash differs")
    repo = QuoteBarRepository(engine)
    policy = load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml"))
    result = []
    months = Counter()
    for m in evidence["datasets"]:
        ds = QuoteDataset.model_validate(m["source"])
        if ds.source_month not in ("2024-02", "2024-03", "2024-04"):
            raise ValueError("non-development date rejected")
        bars = repo.get_bars(
            dataset_key=ds.dataset_key,
            symbol="XAUUSD",
            interval="5minute",
            start=ds.start,
            end=ds.end,
        )
        if content_hash([b.model_dump(mode="json") for b in bars]) != m["bar_hash"]:
            raise ValueError("frozen bars differ")
        rows = calculate_market_state(
            approved_research_inputs(ds, bars, policy, as_of=ds.end)
        )
        if (
            len(rows) != 276
            or content_hash([r.model_dump(mode="json") for r in rows])
            != m["extension_hash"]
        ):
            raise ValueError("G1 feature outputs differ")
        result.extend((ds, row) for row in rows)
        months[ds.source_month] += 1
    if months != {"2024-02": 16, "2024-03": 15, "2024-04": 18} or len(result) != 13524:
        raise ValueError("development cardinality differs")
    return evidence, result


def analyze(evidence, rows):
    samples = {
        name: tuple(r.value(name) for _, r in rows if r.value(name) is not None)
        for name in ("mid_change_std_36", "mid_efficiency_12")
    }
    thresholds = {
        name: tuple(
            quantile(values, p) for p in (Decimal("0.333333"), Decimal("0.666667"))
        )
        for name, values in samples.items()
    }
    policy = MarketTaxonomy(
        volatility_low=thresholds["mid_change_std_36"][0],
        volatility_high=thresholds["mid_change_std_36"][1],
        efficiency_low=thresholds["mid_efficiency_12"][0],
        efficiency_high=thresholds["mid_efficiency_12"][1],
        development_hash=content_hash(evidence["datasets"]),
    )
    classifier = ResearchSessionClassifier(
        SessionConfig.load(Path("config/xauusd_sessions.yaml"))
    )
    records, sequence = [], []
    for ds, row in rows:
        core, range_label = policy.classify(row)
        session = classifier.classify(row.available_at).value
        records.append(
            (ds.source_month, session, str(ds.selected_source_date), core, range_label)
        )
        sequence.append(
            StateObservation(
                ds.dataset_key,
                row.input.opening_timestamp,
                core,
                row.sequence_reset is not None,
            )
        )

    def frequency(subset):
        counts = Counter(x[3] for x in subset)
        valid = len(subset) - counts[WARMUP]
        return {
            "total": len(subset),
            "classified": valid,
            "unclassified": counts[WARMUP],
            "states": {
                s: {
                    "count": counts[s],
                    "pct_classified": percent(counts[s], valid),
                    "pct_all": percent(counts[s], len(subset)),
                    "days": len({x[2] for x in subset if x[3] == s}),
                }
                for s in STATES
            },
        }

    runs, transitions = temporal_summary(tuple(sequence))
    durations = {}
    for s, lengths in runs.items():
        sample = tuple(Decimal(n) for n in sorted(lengths))
        if not sample:
            durations[s] = None
            continue
        n = len(sample)
        stats = {
            "min": sample[0],
            "median": (sample[(n - 1) // 2] + sample[n // 2]) / 2,
            "mean": sum(sample) / n,
            "p95": quantile(sample, Decimal("0.95")),
            "max": sample[-1],
        }
        durations[s] = {
            "runs": n,
            "bars": {k: str(v) for k, v in stats.items()},
            "minutes": {k: str(v * 5) for k, v in stats.items()},
        }
    ranges = {}
    for s in STATES:
        sub = [x for x in records if x[3] == s]
        c = Counter(x[4] for x in sub)
        ranges[s] = {
            k: {"count": c[k], "pct": percent(c[k], len(sub))}
            for k in ("COMPRESSED", "NEUTRAL", "EXPANDED")
        }
    overall = frequency(records)
    if sum(sum(x) for x in runs.values()) != overall["classified"]:
        raise ValueError("run totals do not reconcile")
    if sum(sum(x.values()) for x in transitions.values()) != overall[
        "classified"
    ] - sum(len(x) for x in runs.values()) + sum(
        v for a, row in transitions.items() for b, v in row.items() if a != b
    ):
        raise ValueError("transition/run reconciliation failed")
    result = {
        "policy": policy.model_dump(mode="json"),
        "policy_hash": content_hash(policy.model_dump(mode="json")),
        "quantile_samples": {k: len(v) for k, v in samples.items()},
        "overall": overall,
        "months": {
            m: frequency([x for x in records if x[0] == m])
            for m in ("2024-02", "2024-03", "2024-04")
        },
        "sessions": {
            s: frequency([x for x in records if x[1] == s])
            for s in (
                "ASIA",
                "LONDON",
                "LONDON_NEW_YORK_OVERLAP",
                "NEW_YORK",
                "OFF_SESSION",
            )
        },
        "range_states": ranges,
        "run_lengths": durations,
        "transition_counts": transitions,
        "transition_probabilities": {
            s: {
                t: str(Decimal(n) / sum(row.values())) if sum(row.values()) else "0"
                for t, n in row.items()
            }
            for s, row in transitions.items()
        },
        "classification_hash": content_hash(records),
    }
    return result


def main():
    engine = build_engine(load_settings())
    try:
        with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
            first = analyze(*load_rows(engine))
            second = analyze(*load_rows(engine))
    finally:
        engine.dispose()
    if first != second:
        raise ValueError("deterministic rerun differs")
    config = first["policy"]
    if CONFIG.exists() and yaml.safe_load(CONFIG.read_text()) != config:
        raise ValueError("refusing to overwrite different frozen taxonomy")
    if not CONFIG.exists():
        CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
    report = {
        "scope": "February–April DEVELOPMENT ONLY",
        "days": 49,
        "bars": 13524,
        "g1_report_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "session_config_sha256": hashlib.sha256(
            Path("config/xauusd_sessions.yaml").read_bytes()
        ).hexdigest(),
        "g1_hashes_unchanged": True,
        "rerun_equal": True,
        "may_july_used": False,
        "august_october": "LOCKED_UNPROCESSED",
        **first,
    }
    report["content_hash"] = content_hash(report)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: report[k] for k in ("policy", "overall", "content_hash")}, indent=2
        )
    )


if __name__ == "__main__":
    main()
