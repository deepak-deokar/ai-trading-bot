"""Matched random controls, using only the frozen D2 development inputs."""

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
from trading_bot.strategies.xauusd_pullback import VERSION as CANDIDATE
from trading_bot.strategies.xauusd_pullback import evaluate_pullback


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
    candidate_records = []
    decisions = []
    monthly = Counter()
    sessions = Counter()
    candidate_actual = {h: [] for h in (5, 10, 20)}
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
            previous = None
            for bar, row in zip(bars, rows, strict=True):
                decision = evaluate_pullback(row, previous, as_of=row.available_at)
                assert decision == evaluate_pullback(
                    row, previous, as_of=row.available_at
                )
                previous = row
                decisions.append(decision.model_dump(mode="json"))
                if decision.side is not None:
                    monthly[(ds.source_month, decision.action)] += 1
                    sessions[
                        (classifier.classify(row.available_at).value, decision.action)
                    ] += 1
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
                            if decision.side == side:
                                candidate_actual[h].append(observation)
                            if v1.side == side:
                                actual["V1"][h].append(observation)
                            if v2.side == side:
                                actual["V2"][h].append(observation)
                        if decision.side == side:
                            candidate_records.append(
                                asdict(measured)
                                | {
                                    "dataset_key": ds.dataset_key,
                                    "signal_opening": row.opening_timestamp,
                                    "side": side.name,
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
    assert len(decisions) == 13524 and len(frozen["source_evidence"]) == 49
    results, trial_records, matching = {}, {}, {}
    for h in (5, 10, 20):
        strata = Counter(o.stratum for o in candidate_actual[h])
        availability = Counter(o.stratum for o in pools[h])
        matching[str(h)] = [
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
            f"{h} bars: {len(candidate_actual[h])} eligible; 1000 trials twice",
            flush=True,
        )
        trials = matched_trials(
            tuple(pools[h]), dict(strata), strategy=CANDIDATE, horizon=h
        )
        assert trials == matched_trials(
            tuple(pools[h]), dict(strata), strategy=CANDIDATE, horizon=h
        )
        trial_records[str(h)] = trials
        results[str(h)] = {}
        for side in ("ALL", "BUY", "SELL"):
            stats = summary(
                [
                    r
                    for r in candidate_records
                    if r["horizon"] == h and (side == "ALL" or r["side"] == side)
                ]
            )
            comparisons = {
                field: distribution(
                    [t[side][field] for t in trials], stats[actual_field]
                )
                for field, actual_field in (
                    ("mean_markout", "mean_markout"),
                    ("positive_pct", "pct_positive"),
                    ("mean_favorable", "mean_favorable"),
                    ("mean_adverse", "mean_adverse"),
                )
            }
            results[str(h)][side] = {"actual": stats, "random": comparisons}
    report = {
        "checkpoint": "G2C4E1",
        "strategy": CANDIDATE,
        "development_in_sample": True,
        "days": 49,
        "bars": len(decisions),
        "signal_counts": dict(
            Counter(
                "NO_TRADE" if d["side"] is None else str(d["side"]).upper()
                for d in decisions
            )
        ),
        "monthly_counts": [
            {"month": k[0], "side": k[1], "count": n}
            for k, n in sorted(monthly.items())
        ],
        "session_counts": [
            {"session": k[0], "side": k[1], "count": n}
            for k, n in sorted(sessions.items())
        ],
        "seed_namespace": SEED_NAMESPACE,
        "seed_strategy": CANDIDATE,
        "python_version": platform.python_version(),
        "trials": TRIALS,
        "rerun_equal": True,
        "D2_content_hash": frozen["content_hash"],
        "D2_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "session_config_sha256": hashlib.sha256(
            Path("config/xauusd_sessions.yaml").read_bytes()
        ).hexdigest(),
        "baseline_signal_counts_reproduced": dict(counts),
        "baseline_observations_reproduced": len(reproduced),
        "baseline_context": frozen["results"],
        "source_evidence": frozen["source_evidence"],
        "matching": matching,
        "results": results,
        "decisions_content_hash": content_hash(decisions),
        "signal_decisions": [d for d in decisions if d["side"] is not None],
        "observations": candidate_records,
        "trial_results": trial_records,
        "method": (
            "D2 markouts unchanged; D3 exact month/session/direction matching "
            "without replacement; all eligible candidates including warmup/signals; "
            "1000 trials independently repeated; no execution/account simulation"
        ),
    }
    report = json.loads(json.dumps(report, default=str))
    report["content_hash"] = content_hash(report)
    Path("docs/xauusd-pullback-resumption-signal-study.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "monthly": report["monthly_counts"],
                "sessions": report["session_counts"],
                "results": results,
            },
            default=str,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
