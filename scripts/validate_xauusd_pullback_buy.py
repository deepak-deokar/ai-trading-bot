"""First unseen BUY-only signal validation; frozen rules, no account simulation."""

import hashlib
import json
import platform
from collections import Counter
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal
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
from trading_bot.domain.market import utc
from trading_bot.domain.models import Side
from trading_bot.domain.sessions import ResearchSessionClassifier, SessionConfig
from trading_bot.features.research_repository import (
    ResearchFeatureRepository,
    content_hash,
)
from trading_bot.features.xauusd import VERSION, XAUUSDFeatureRow
from trading_bot.strategies.xauusd_pullback import REQUIRED, _values
from trading_bot.strategies.xauusd_pullback import VERSION as CANDIDATE

DATASET_KEY = "811d9f5db6bf55d128147b2247197d2364e31b185d005c69b33b2349ffa589c5"
DATASET_PATH = Path("docs/xauusd-may-july-validation-dataset.json")
OUTPUT = Path("docs/xauusd-pullback-buy-validation-may-july.json")


def buy_only(current, previous, *, as_of):
    """BUY projection of frozen E1 guards/predicate; never evaluate its other arm."""
    current = XAUUSDFeatureRow.model_validate(current.model_dump())
    if utc(as_of) < current.available_at:
        raise ValueError("current feature row is not yet available")
    if previous is None:
        return False
    previous = XAUUSDFeatureRow.model_validate(previous.model_dump())
    if (
        previous.dataset_key != current.dataset_key
        or previous.policy_key != current.policy_key
        or current.sequence_reset is not None
        or current.opening_timestamp - previous.opening_timestamp
        != timedelta(minutes=5)
        or previous.available_at != current.opening_timestamp
        or current.input.previous_observed_timestamp != previous.opening_timestamp
    ):
        return False
    values, prior = _values(current), _values(previous).get("momentum_3")
    if (
        prior is None
        or prior.value is None
        or prior.unavailable is not None
        or any(
            n not in values
            or values[n].value is None
            or values[n].unavailable is not None
            for n in REQUIRED
        )
    ):
        return False
    fast, slow, short, long, spread, relative = (values[n].value for n in REQUIRED)
    if spread < 0 or relative < 0:
        raise ValueError("negative spread feature")
    if spread > Decimal("0.75") or relative > Decimal("0.0003"):
        return False
    return fast > slow and long > 0 and prior.value <= 0 and short > 0


def classification(actual, comparison):
    if actual > 0 and comparison["actual_percentile"] >= 95:
        return "STRONG VALIDATION SUPPORT"
    if actual > comparison["random_mean"]:
        return "PARTIAL SUPPORT"
    return "NO VALIDATION SUPPORT"


def load_verified(engine):
    frozen = json.loads(DATASET_PATH.read_text())
    manifest = frozen["manifest"]
    if frozen["dataset_key"] != DATASET_KEY or content_hash(manifest) != DATASET_KEY:
        raise ValueError("frozen E2B dataset identity differs")
    if (
        manifest["bar_count"] != 13800
        or manifest["feature_count"] != 13800
        or manifest["feature_version"] != VERSION
        or len(manifest["days"]) != 50
    ):
        raise ValueError("frozen scope differs")
    loaded = []
    br, fr = QuoteBarRepository(engine), ResearchFeatureRepository(engine)
    for item in manifest["days"]:
        ds = QuoteDataset.model_validate(item["dataset"])
        if (
            ds.source_month not in ("2024-05", "2024-06", "2024-07")
            or ds.dataset_key != item["dataset_key"]
        ):
            raise ValueError("unexpected dataset scope")
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
        if len(bars) != 276 or len(rows) != 276:
            raise ValueError("stored row count differs")
        if (
            content_hash([b.model_dump(mode="json") for b in bars])
            != item["bar_content_hash"]
            or content_hash([r.model_dump(mode="json") for r in rows])
            != item["feature_content_hash"]
        ):
            raise ValueError("frozen bar/feature content differs")
        # D2 boundaries: the closing instant before each gap, plus day end.
        boundaries = tuple(
            a.closing_timestamp
            for a, b in zip(bars, bars[1:], strict=False)
            if a.closing_timestamp != b.opening_timestamp
        ) + (ds.end,)
        loaded.append((ds, bars, rows, boundaries))
    if dict(Counter(ds.source_month for ds, _, _, _ in loaded)) != {
        "2024-05": 17,
        "2024-06": 15,
        "2024-07": 18,
    }:
        raise ValueError("month cardinalities differ")
    return loaded


def study(loaded):
    classifier = ResearchSessionClassifier(
        SessionConfig.load(Path("config/xauusd_sessions.yaml"))
    )
    counts, monthly, sessions = Counter(), Counter(), Counter()
    pools, actual = {h: [] for h in (5, 10, 20)}, {h: [] for h in (5, 10, 20)}
    records, decisions = [], []
    for ds, bars, rows, boundaries in loaded:
        previous = None
        for bar, row in zip(bars, rows, strict=True):
            if bar.opening_timestamp != row.opening_timestamp:
                raise ValueError("feature/bar chronology differs")
            buy = buy_only(row, previous, as_of=row.available_at)
            decisions.append(
                {
                    "dataset_key": ds.dataset_key,
                    "opening": row.opening_timestamp.isoformat(),
                    "buy": buy,
                    "current_hash": content_hash(row.model_dump(mode="json")),
                    "previous_hash": (
                        content_hash(previous.model_dump(mode="json"))
                        if previous
                        else None
                    ),
                }
            )
            previous = row
            session = classifier.classify(row.available_at).value
            if buy:
                counts["BUY"] += 1
                monthly[ds.source_month] += 1
                sessions[session] += 1
            for h in (5, 10, 20):
                measured = measure_forward(
                    ds,
                    bars,
                    signal_opening=row.opening_timestamp,
                    side=Side.BUY,
                    horizon=h,
                    boundary_times=boundaries,
                )
                if measured.unavailable is None:
                    obs = Observation(
                        f"{ds.dataset_key}:{row.opening_timestamp.isoformat()}:BUY",
                        (ds.source_month, session, "BUY"),
                        measured.markout,
                        measured.favorable,
                        measured.adverse,
                    )
                    pools[h].append(obs)
                    if buy:
                        actual[h].append(obs)
                if buy:
                    records.append(
                        asdict(measured)
                        | {
                            "dataset_key": ds.dataset_key,
                            "signal_opening": row.opening_timestamp.isoformat(),
                        }
                    )
    results, matching, hashes = {}, {}, {}
    for h in (5, 10, 20):
        strata = Counter(o.stratum for o in actual[h])
        availability = Counter(o.stratum for o in pools[h])
        matching[str(h)] = [
            {
                "month": k[0],
                "session": k[1],
                "requested": n,
                "candidates": availability[k],
            }
            for k, n in sorted(strata.items())
        ]
        stats = summary([r for r in records if r["horizon"] == h])
        trials = matched_trials(
            tuple(pools[h]), dict(strata), strategy=CANDIDATE, horizon=h
        )
        # Only BUY is sampled and reported from the unchanged benchmark helper.
        compact = [
            {
                "trial": t["trial"],
                "selection_hash": t["selection_hash"],
                "BUY": t["BUY"],
            }
            for t in trials
        ]
        hashes[str(h)] = content_hash(json.loads(json.dumps(compact, default=str)))
        results[str(h)] = {
            "actual": stats,
            "random": {
                field: distribution([t["BUY"][field] for t in trials], stats[name])
                for field, name in (
                    ("mean_markout", "mean_markout"),
                    ("positive_pct", "pct_positive"),
                    ("mean_favorable", "mean_favorable"),
                    ("mean_adverse", "mean_adverse"),
                )
            },
        }
    return json.loads(
        json.dumps(
            {
                "buy_signals": counts["BUY"],
                "monthly_buy": dict(sorted(monthly.items())),
                "session_buy": dict(sorted(sessions.items())),
                "results": results,
                "matching": matching,
                "trial_hashes": hashes,
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
        loaded = load_verified(
            engine
        )  # Verify all 50 days before any signal evaluation.
        print("E2B identity and all 13800 bar/feature rows verified", flush=True)
        first = study(loaded)
        print("First BUY-only study complete; repeating unchanged", flush=True)
        second = study(load_verified(engine))
        if first != second:
            raise ValueError("full deterministic rerun differs")
    finally:
        engine.dispose()
    primary = first["results"]["10"]
    result = classification(
        Decimal(primary["actual"]["mean_markout"]),
        {k: Decimal(v) for k, v in primary["random"]["mean_markout"].items()},
    )
    report = {
        "checkpoint": "G2C4E2C",
        "strategy": CANDIDATE,
        "side": "BUY_ONLY",
        "primary_horizon": 10,
        "supporting_horizons": [5, 20],
        "dataset_key": DATASET_KEY,
        "dataset_report_sha256": hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest(),
        "session_config_sha256": hashlib.sha256(
            Path("config/xauusd_sessions.yaml").read_bytes()
        ).hexdigest(),
        "frozen_candidate_source_sha256": hashlib.sha256(
            Path("src/trading_bot/strategies/xauusd_pullback.py").read_bytes()
        ).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python_version": platform.python_version(),
        "seed_namespace": SEED_NAMESPACE,
        "seed_strategy": CANDIDATE,
        "trials": TRIALS,
        "classification": result,
        "rerun_equal": True,
        "study_hash": content_hash(first),
        "august_october": "LOCKED_UNPROCESSED",
        "development_context": {
            "5": {"mean": "-0.132739", "percentile": "87.1"},
            "10": {"mean": "0.217478", "percentile": "98.9"},
            "20": {"mean": "0.265121", "percentile": "85.2"},
        },
        **first,
    }
    report["content_hash"] = content_hash(report)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
