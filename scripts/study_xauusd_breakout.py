"""Frozen development-only structural breakout screen; no trading simulator."""

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
from trading_bot.strategies.xauusd_breakout import VERSION as CANDIDATE
from trading_bot.strategies.xauusd_breakout import evaluate_breakout

SOURCE = Path("docs/xauusd-forward-signal-quality.json")
OUTPUT = Path("docs/xauusd-structural-breakout-signal-study.json")


def load_verified(engine):
    frozen = json.loads(SOURCE.read_text())
    if (
        content_hash({k: v for k, v in frozen.items() if k != "content_hash"})
        != frozen["content_hash"]
    ):
        raise ValueError("frozen development report hash differs")
    loaded = []
    br, fr = QuoteBarRepository(engine), ResearchFeatureRepository(engine)
    for e in frozen["source_evidence"]:
        ds = QuoteDataset.model_validate(e["dataset"])
        if ds.source_month not in ("2024-02", "2024-03", "2024-04"):
            raise ValueError("only development source dates are allowed")
        bars = br.get_bars(
            dataset_key=ds.dataset_key,
            symbol="XAUUSD",
            interval="5minute",
            start=ds.start,
            end=ds.end,
        )
        rows = fr.get_rows(
            source_dataset_key=ds.dataset_key,
            symbol="XAUUSD",
            feature_version=VERSION,
            start=ds.start,
            end=ds.end,
            as_of=ds.end,
        )
        if (
            len(bars) != 276
            or len(rows) != 276
            or content_hash([b.model_dump(mode="json") for b in bars])
            != e["bar_content_hash"]
            or content_hash([r.model_dump(mode="json") for r in rows])
            != e["feature_content_hash"]
        ):
            raise ValueError("frozen development inputs differ")
        boundaries = tuple(datetime.fromisoformat(t) for t in e["boundary_times"])
        loaded.append((ds, bars, rows, boundaries))
    if dict(Counter(ds.source_month for ds, _, _, _ in loaded)) != {
        "2024-02": 16,
        "2024-03": 15,
        "2024-04": 18,
    }:
        raise ValueError("development cardinalities differ")
    return loaded


def study(loaded):
    classifier = ResearchSessionClassifier(
        SessionConfig.load(Path("config/xauusd_sessions.yaml"))
    )
    monthly, sessions, counts = Counter(), Counter(), Counter()
    pools, actual = {h: [] for h in (5, 10, 20)}, {h: [] for h in (5, 10, 20)}
    decisions, records = [], []
    for ds, bars, rows, boundaries in loaded:
        for i, (bar, row) in enumerate(zip(bars, rows, strict=True)):
            if bar.opening_timestamp != row.opening_timestamp:
                raise ValueError("bar/feature chronology differs")
            d = evaluate_breakout(row, rows[max(0, i - 13) : i], as_of=row.available_at)
            decisions.append(d.model_dump(mode="json"))
            counts[d.action] += 1
            session = classifier.classify(row.available_at).value
            if d.side is not None:
                monthly[(ds.source_month, d.action)] += 1
                sessions[(session, d.action)] += 1
            for h in (5, 10, 20):
                for side in (Side.BUY, Side.SELL):
                    measured = measure_forward(
                        ds,
                        bars,
                        signal_opening=row.opening_timestamp,
                        side=side,
                        horizon=h,
                        boundary_times=boundaries,
                    )
                    if measured.unavailable is None:
                        obs = Observation(
                            f"{ds.dataset_key}:{row.opening_timestamp.isoformat()}:{side.name}",
                            (ds.source_month, session, side.name),
                            measured.markout,
                            measured.favorable,
                            measured.adverse,
                        )
                        pools[h].append(obs)
                        if d.side == side:
                            actual[h].append(obs)
                    if d.side == side:
                        records.append(
                            asdict(measured)
                            | {
                                "dataset_key": ds.dataset_key,
                                "opening": row.opening_timestamp.isoformat(),
                                "side": side.name,
                            }
                        )
    results, matching, trial_hashes = {}, {}, {}
    for h in (5, 10, 20):
        strata = Counter(o.stratum for o in actual[h])
        available = Counter(o.stratum for o in pools[h])
        matching[str(h)] = [
            {
                "month": k[0],
                "session": k[1],
                "direction": k[2],
                "requested": n,
                "candidates": available[k],
            }
            for k, n in sorted(strata.items())
        ]
        trials = matched_trials(
            tuple(pools[h]), dict(strata), strategy=CANDIDATE, horizon=h
        )
        trial_hashes[str(h)] = content_hash(json.loads(json.dumps(trials, default=str)))
        results[str(h)] = {}
        for side in ("ALL", "BUY", "SELL"):
            stats = summary(
                [
                    r
                    for r in records
                    if r["horizon"] == h and (side == "ALL" or r["side"] == side)
                ]
            )
            comparisons = {
                field: distribution([t[side][field] for t in trials], stats[name])
                for field, name in (
                    ("mean_markout", "mean_markout"),
                    ("positive_pct", "pct_positive"),
                    ("mean_favorable", "mean_favorable"),
                    ("mean_adverse", "mean_adverse"),
                )
            }
            results[str(h)][side] = {"actual": stats, "random": comparisons}
    return json.loads(
        json.dumps(
            {
                "counts": dict(counts),
                "monthly": [
                    {"month": k[0], "side": k[1], "count": n}
                    for k, n in sorted(monthly.items())
                ],
                "sessions": [
                    {"session": k[0], "side": k[1], "count": n}
                    for k, n in sorted(sessions.items())
                ],
                "results": results,
                "matching": matching,
                "trial_hashes": trial_hashes,
                "decision_hash": content_hash(decisions),
                "observation_hash": content_hash(
                    json.loads(json.dumps(records, default=str))
                ),
            },
            default=str,
        )
    )


def main():
    engine = build_engine(load_settings()).execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    )
    try:
        loaded = load_verified(engine)
        print("49 development days / 13524 rows verified", flush=True)
        first = study(loaded)
        print(
            "First frozen structural-breakout study complete; repeating unchanged",
            flush=True,
        )
        if first != study(load_verified(engine)):
            raise ValueError("deterministic rerun mismatch")
    finally:
        engine.dispose()
    baseline = json.loads(SOURCE.read_text())["results"]
    e1path = Path("docs/xauusd-pullback-resumption-signal-study.json")
    e1 = json.loads(e1path.read_text())
    if (
        content_hash({k: v for k, v in e1.items() if k != "content_hash"})
        != e1["content_hash"]
    ):
        raise ValueError("frozen E1 development report hash differs")
    context = {}
    for name in ("V1", "V2", "E1"):
        context[name] = {}
        for h in ("5", "10", "20"):
            context[name][h] = {}
            for side in ("ALL", "BUY", "SELL"):
                a = (
                    e1["results"][h][side]["actual"]
                    if name == "E1"
                    else baseline[name][h][side]
                )
                context[name][h][side] = {
                    k: a[k] for k in ("mean_markout", "mean_favorable", "mean_adverse")
                }
    report = {
        "checkpoint": "G2C4F1",
        "strategy": CANDIDATE,
        "lookback": 12,
        "freshness_prior_bars_required": 13,
        "scope": "February–April 2024 DEVELOPMENT ONLY",
        "days": 49,
        "bars": 13524,
        "may_july_used": False,
        "august_october": "LOCKED_UNPROCESSED",
        "D2_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "E1_sha256": hashlib.sha256(e1path.read_bytes()).hexdigest(),
        "candidate_source_sha256": hashlib.sha256(
            Path("src/trading_bot/strategies/xauusd_breakout.py").read_bytes()
        ).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "session_config_sha256": hashlib.sha256(
            Path("config/xauusd_sessions.yaml").read_bytes()
        ).hexdigest(),
        "seed_namespace": SEED_NAMESPACE,
        "seed_strategy": CANDIDATE,
        "python_version": platform.python_version(),
        "trials": TRIALS,
        "rerun_equal": True,
        "study_hash": content_hash(first),
        "development_context": context,
        **first,
    }
    report["content_hash"] = content_hash(report)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
