"""Inverted interpretation at frozen timestamps; source BID/ASK, no strategy."""

import hashlib
import json
import platform
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from analyze_xauusd_markouts import summary

from trading_bot.config.settings import load_settings
from trading_bot.data.forward_markout import measure_forward
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.data.random_markout import (
    SEED_NAMESPACE,
    TRIALS,
    Observation,
    distribution,
    matched_trials,
)
from trading_bot.database.session import build_engine
from trading_bot.domain.models import Side
from trading_bot.domain.sessions import ResearchSessionClassifier, SessionConfig
from trading_bot.features.research_repository import (
    ResearchFeatureRepository,
    content_hash,
)
from trading_bot.features.xauusd import VERSION
from trading_bot.strategies.xauusd import evaluate_xauusd
from trading_bot.strategies.xauusd_confirmation import evaluate_confirmation


def main():
    path = Path("docs/xauusd-forward-signal-quality.json")
    frozen = json.loads(path.read_text())
    assert (
        content_hash({k: v for k, v in frozen.items() if k != "content_hash"})
        == frozen["content_hash"]
    )
    classifier = ResearchSessionClassifier(
        SessionConfig.load(Path("config/xauusd_sessions.yaml"))
    )
    saved = {
        (r["dataset_key"], datetime.fromisoformat(r["signal_opening"]), r["horizon"]): r
        for r in frozen["observations"]
    }
    pools = {h: [] for h in (5, 10, 20)}
    actual = {v: {h: [] for h in (5, 10, 20)} for v in ("V1", "V2")}
    counts = Counter()
    reproduced = []
    inverted = []
    engine = build_engine(load_settings()).execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    )
    try:
        repo, features = QuoteBarRepository(engine), ResearchFeatureRepository(engine)
        for evidence in frozen["source_evidence"]:
            ds = QuoteDataset.model_validate(evidence["dataset"])
            assert ds.source_month in ("2024-02", "2024-03", "2024-04")
            bars = repo.get_bars(
                dataset_key=ds.dataset_key,
                symbol="XAUUSD",
                interval="5minute",
                start=ds.start,
                end=ds.end,
            )
            rows = features.get_rows(
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
                content_hash([r.model_dump(mode="json") for r in rows])
                == evidence["feature_content_hash"]
            )
            boundaries = tuple(
                datetime.fromisoformat(t) for t in evidence["boundary_times"]
            )
            for bar, row in zip(bars, rows, strict=True):
                assert bar.opening_timestamp == row.opening_timestamp
                v1 = evaluate_xauusd(row, as_of=row.available_at)
                v2 = evaluate_confirmation(row, as_of=row.available_at)
                counts[f"V1_{v1.action}"] += 1
                counts[f"V2_{v2.action}"] += 1
                for h in (5, 10, 20):
                    for side in (Side.BUY, Side.SELL):
                        measured = measure_forward(
                            ds,
                            bars,
                            signal_opening=bar.opening_timestamp,
                            side=side,
                            horizon=h,
                            boundary_times=boundaries,
                        )
                        if measured.unavailable is None:
                            identity = (
                                f"{ds.dataset_key}:"
                                f"{bar.opening_timestamp.isoformat()}:{side.name}"
                            )
                            observation = Observation(
                                identity,
                                (
                                    ds.source_month,
                                    classifier.classify(row.available_at).value,
                                    side.name,
                                ),
                                measured.markout,
                                measured.favorable,
                                measured.adverse,
                            )
                            pools[h].append(observation)
                            if v1.side is not None and v1.side != side:
                                actual["V1"][h].append(observation)
                            if v2.side is not None and v2.side != side:
                                actual["V2"][h].append(observation)
                        if v1.side is not None and v1.side != side:
                            inverted.append(
                                asdict(measured)
                                | {
                                    "dataset_key": ds.dataset_key,
                                    "source_date": ds.selected_source_date,
                                    "signal_timestamp": v1.available_at,
                                    "signal_opening": v1.opening_timestamp,
                                    "side": side.name,
                                    "original_side": v1.side.name,
                                    "retained_v2": v2.side is not None,
                                    "v1_decision_key": content_hash(
                                        v1.model_dump(mode="json")
                                    ),
                                }
                            )
                        if v1.side == side:
                            record = asdict(measured) | {
                                "dataset_key": ds.dataset_key,
                                "source_date": ds.selected_source_date,
                                "signal_timestamp": v1.available_at,
                                "signal_opening": v1.opening_timestamp,
                                "side": side.name,
                                "retained_v2": v2.side is not None,
                                "v1_decision_key": content_hash(
                                    v1.model_dump(mode="json")
                                ),
                            }
                            normalized = json.loads(json.dumps(record, default=str))
                            assert (
                                normalized
                                == saved[(ds.dataset_key, bar.opening_timestamp, h)]
                            )
                            reproduced.append(record)
    finally:
        engine.dispose()
    assert dict(counts) == frozen["signal_counts"]
    assert len(reproduced) == len(frozen["observations"]) == 12252
    assert len(inverted) == len(reproduced)
    original_by_key = {
        (r["dataset_key"], r["signal_opening"], r["horizon"]): r for r in reproduced
    }
    for r in inverted:
        old = original_by_key[(r["dataset_key"], r["signal_opening"], r["horizon"])]
        assert r["unavailable"] == old["unavailable"]
        assert r["signal_timestamp"] == old["signal_timestamp"]
        assert r["side"] != old["side"]
    results = {}
    trial_records = {}
    matching = {}
    for version in ("V1", "V2"):
        results[version] = {}
        trial_records[version] = {}
        matching[version] = {}
        for h in (5, 10, 20):
            population = actual[version][h]
            strata = Counter(o.stratum for o in population)
            availability = Counter(o.stratum for o in pools[h])
            matching[version][str(h)] = [
                {
                    "month": k[0],
                    "session": k[1],
                    "direction": k[2],
                    "requested": n,
                    "candidates": availability[k],
                }
                for k, n in sorted(strata.items())
            ]
            print(
                f"{version} {h}: {len(population)} observations; "
                "exact strata, 1000 trials twice",
                flush=True,
            )
            trials = matched_trials(
                tuple(pools[h]), dict(strata), strategy=version + "-inverted", horizon=h
            )
            rerun = matched_trials(
                tuple(pools[h]), dict(strata), strategy=version + "-inverted", horizon=h
            )
            assert trials == rerun
            trial_records[version][str(h)] = trials
            results[version][str(h)] = {}
            for side in ("ALL", "BUY", "SELL"):
                source = [
                    r
                    for r in inverted
                    if r["horizon"] == h
                    and (version == "V1" or r["retained_v2"])
                    and (side == "ALL" or r["side"] == side)
                ]
                stats = summary(source)
                original_side = (
                    "ALL" if side == "ALL" else "SELL" if side == "BUY" else "BUY"
                )
                for name in ("signals", "eligible", "unavailable"):
                    assert (
                        stats[name]
                        == frozen["results"][version][str(h)][original_side][name]
                    )
                comparisons = {}
                for field, actual_field in (
                    ("mean_markout", "mean_markout"),
                    ("positive_pct", "pct_positive"),
                    ("mean_favorable", "mean_favorable"),
                    ("mean_adverse", "mean_adverse"),
                ):
                    comparisons[field] = distribution(
                        [t[side][field] for t in trials], stats[actual_field]
                    )
                results[version][str(h)][side] = {
                    "actual": stats,
                    "random": comparisons,
                }
    serial_trials = json.loads(json.dumps(trial_records, default=str))
    report = {
        "checkpoint": "G2C4D4",
        "development_in_sample": True,
        "hypothesis": (
            "Failed continuation signals may identify short-term directional "
            "exhaustion rather than continuation; no parameter change"
        ),
        "holdout": (
            "After April 30, 2024 remains reserved from strategy-performance "
            "analysis until a future candidate is frozen; source-day dates "
            "define the existing approved data"
        ),
        "seed_namespace": SEED_NAMESPACE,
        "seed_scheme": (
            "SHA256(namespace|V1-inverted-or-V2-inverted|horizon|zero-based-trial), "
            "big-endian "
            "integer -> Python random.Random.sample"
        ),
        "python_version": platform.python_version(),
        "trials": TRIALS,
        "rerun_equal": True,
        "trial_content_hash": content_hash(serial_trials),
        "D2_content_hash": frozen["content_hash"],
        "D2_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "session_config_sha256": hashlib.sha256(
            Path("config/xauusd_sessions.yaml").read_bytes()
        ).hexdigest(),
        "signal_counts": dict(counts),
        "D2_observations_reproduced": len(reproduced),
        "matching": matching,
        "results": results,
        "inverted_observations": inverted,
        "side_labels": "BUY = original SELL inverted; SELL = original BUY inverted",
        "trial_results": serial_trials,
        "method": (
            "Exact month x existing signal-time research session x direction; "
            "without replacement within each stratum, independent trials; no "
            "fallback. All horizon-eligible candidates, including actual "
            "signal bars and feature warmup rows, are eligible. Opposite "
            "directions may sample the same timestamp. No outcome filtering."
        ),
        "percentiles": (
            "p05/p95 nearest rank; actual "
            "percentile=100*(less+0.5*equal)/1000; descriptive, not a p-value"
        ),
    }
    report = json.loads(json.dumps(report, default=str))
    report["content_hash"] = content_hash(report)
    Path("docs/xauusd-contrarian-signal-diagnostic.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                v: {
                    h: {s: g["random"]["mean_markout"] for s, g in groups.items()}
                    for h, groups in horizons.items()
                }
                for v, horizons in results.items()
            },
            default=str,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
