"""Corrected frozen $500 replay; original reports and trading logic are untouched."""

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean, median

from trading_bot.config.settings import load_settings
from trading_bot.data.gap_policy import load_gap_policy
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.data.research_input import approved_research_inputs
from trading_bot.database.session import build_engine
from trading_bot.execution.research_backtest import (
    ResearchBacktestConfig,
    ResearchDay,
    run_historical,
)
from trading_bot.features.research_repository import (
    ResearchFeatureRepository,
    content_hash,
)
from trading_bot.features.xauusd import VERSION as FEATURE_VERSION
from trading_bot.strategies.xauusd import evaluate_xauusd
from trading_bot.strategies.xauusd_confirmation import VERSION, evaluate_confirmation


def write_markdown(result, metadata, original):
    m = result.metrics
    v1 = original["result"]["metrics"]
    old_trades = [r for r in original["result"]["records"] if r["net_pnl"] is not None]
    old_r = [Decimal(r["net_pnl"]) / Decimal(r["risk_budget"]) for r in old_trades]
    lines = [
        "# G2C4D1 — DEVELOPMENT / IN-SAMPLE experiment",
        "",
        "Pre-run hypothesis: V1 has negative expectancy and a high stop-out rate.",
        "Requiring agreement between 3-bar and 12-bar momentum may reduce short-lived",
        (
            "directional entries. Improvement was not assumed; no "
            "threshold search occurred."
        ),
        "",
        f"Candidate: `{VERSION}`. Every V1 condition is retained. BUY additionally",
        "requires momentum_12 > 0; SELL requires momentum_12 < 0. Zero/unavailable",
        "values do not confirm. 'long-confirmation' refers to the longer lookback,",
        "not a LONG-only strategy. Both directions remain enabled.",
        "",
        "All other inputs remain frozen: $3,000 balance, 1% risk, 49 approved days,",
        "13,524 bars, baseline-features-v1, 12-bar structural stop, 2R target,",
        "10 ounces/unit, volumes 0.25–2 step 0.25, tick 0.01, $1.25 round-trip fee.",
        "Observed market prices, generated grid levels, one position at a time,",
        "boundary closures and protective execution are unchanged. No raw data writes.",
        "",
        "## Signal study (completed before execution)",
        "",
    ]
    lines += [f"- {k}: {v}" for k, v in metadata["signal_study"].items()]
    lines += ["", "## V2 results", "", "| Metric | Value |", "| --- | ---: |"]
    lines += [f"| {k} | {v} |" for k, v in m if not isinstance(v, dict)]
    lines += [
        f"| mean net R | {metadata['mean_net_R']} |",
        f"| median net R | {metadata['median_net_R']} |",
        "",
        "Rejections:",
        "",
    ]
    lines += [f"- {k}: {v}" for k, v in m.rejection_reasons.items()]
    lines += ["", "Exits:", ""]
    lines += [f"- {k}: {v}" for k, v in m.exit_reasons.items()]
    lines += [
        "",
        "## V1 versus V2",
        "",
        "| Metric | V1 | V2 |",
        "| --- | ---: | ---: |",
    ]
    for k in [
        "signals_generated",
        "trades_closed",
        "win_rate_percent",
        "expectancy",
        "profit_factor",
        "net_pnl",
        "max_drawdown_usd",
        "max_drawdown_percent",
    ]:
        lines.append(f"| {k} | {v1[k]} | {getattr(m, k)} |")
    lines.append(f"| mean net R | {mean(old_r)} | {metadata['mean_net_R']} |")
    for name, keys in [
        ("stop rate including ambiguous %", ["CLOSED_STOP", "CLOSED_STOP_AMBIGUOUS"]),
        ("target rate %", ["CLOSED_TARGET"]),
    ]:
        old = (
            Decimal(sum(v1["exit_reasons"][k] for k in keys))
            * 100
            / v1["trades_closed"]
        )
        new = (
            Decimal(sum(m.exit_reasons[k] for k in keys)) * 100 / m.trades_closed
            if m.trades_closed
            else None
        )
        lines.append(f"| {name} | {old} | {new} |")
    lines += [
        "",
        "R uses saved risk budget, not actual deployed stop loss. Gross profit/loss",
        "sum positive/absolute negative net trade P&L; pre-commission P&L is separate.",
        (
            "All balances carry forward. Monthly metrics and complete "
            "signal records are in JSON."
        ),
        "",
        (
            "V1 replay reproduced its frozen content identity exactly "
            "after strategy routing"
        ),
        "was added. V2 ran twice with equal complete results and content identity:",
        f"`{result.report_identity}`.",
        (
            "Generation time is excluded from mathematical identity. "
            "Original persisted feature"
        ),
        (
            "hashes and signal completion times were checked. Offline "
            "future-mutation tests"
        ),
        (
            "cover the V2 pipeline, including future momentum_12 "
            "changes. No V1 report changed."
        ),
        "",
        "This is development data already used for attribution; it is not independent",
        (
            "validation. Reduced trade count alone is not improvement. "
            "The contract is synthetic,"
        ),
        (
            "day selection retrospective and OHLC fills simulated. No "
            "slippage/liquidity model"
        ),
        (
            "or broker verification is added. No parameter was changed "
            "after seeing results."
        ),
        "",
        "Reproduce with DATABASE_URL provided securely:",
        "",
        "```sh",
        "PYTHONPATH=src .venv/bin/python scripts/backtest_xauusd_confirmation.py",
        "```",
    ]
    Path("docs/xauusd-v2-momentum-confirmation-development.md").write_text(
        "\n".join(lines) + "\n"
    )


def main():
    original = json.loads(
        Path("docs/xauusd-3000-sensitivity-corrected.json").read_text()
    )
    config = ResearchBacktestConfig.model_validate_json(
        json.dumps(original["result"]["config"])
    )
    if config.starting_balance != Decimal("3000") or config.risk_fraction != Decimal(
        "0.01"
    ):
        raise ValueError("frozen account mismatch")
    routing_files = {
        "src/trading_bot/strategies/xauusd_levels.py",
        "src/trading_bot/execution/research_backtest.py",
    }
    for name, digest in original["provenance"]["component_source_hashes"].items():
        if (
            name not in routing_files
            and hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest
        ):
            raise ValueError(f"frozen component changed: {name}")
    manifest_report = json.loads(
        Path("docs/xauusd-baseline-feature-persistence.json").read_text()
    )
    policy = load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml"))
    engine = build_engine(load_settings()).execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    )
    days, source_evidence, seen = [], [], set()
    print(
        "Loading and validating approved persisted source days (read-only).", flush=True
    )
    try:
        bars_repo, features_repo = QuoteBarRepository(
            engine
        ), ResearchFeatureRepository(engine)
        records = sorted(
            manifest_report["first_pass"],
            key=lambda r: r["manifest"]["source"]["start"],
        )
        for record in records:
            manifest = record["manifest"]
            ds = QuoteDataset.model_validate(manifest["source"])
            if (
                ds.dataset_key != manifest["source_dataset_key"]
                or ds.dataset_key in seen
                or ds.source_month not in ("2024-02", "2024-03", "2024-04")
            ):
                raise ValueError("unexpected bounded source identity")
            seen.add(ds.dataset_key)
            bars = bars_repo.get_bars(
                dataset_key=ds.dataset_key,
                symbol="XAUUSD",
                interval="5minute",
                start=ds.start,
                end=ds.end,
            )
            approved_research_inputs(ds, bars, policy, as_of=ds.end)
            features = features_repo.get_rows(
                source_dataset_key=ds.dataset_key,
                symbol="XAUUSD",
                feature_version=FEATURE_VERSION,
                start=ds.start,
                end=ds.end,
                as_of=ds.end,
            )
            digest = content_hash([r.model_dump(mode="json") for r in features])
            if (
                digest != manifest["content_hash"]
                or len(features) != manifest["feature_row_count"]
            ):
                raise ValueError("persisted features differ from approved manifest")
            segment = next(
                s
                for s in policy.segments
                if s.effective_start_date
                <= date.fromisoformat(ds.selected_source_date)
                <= s.effective_end_date
            )
            boundaries = tuple(
                sorted(
                    {
                        ds.end,
                        *(
                            ds.start + timedelta(minutes=5 * r.indices[0])
                            for r in segment.allowed_missing_ranges
                        ),
                    }
                )
            )
            days.append(
                ResearchDay(
                    dataset=ds, bars=bars, features=features, boundary_times=boundaries
                )
            )
            source_evidence.append(
                {
                    "dataset": ds.model_dump(mode="json"),
                    "feature_content_hash": digest,
                    "bar_content_hash": content_hash(
                        [b.model_dump(mode="json") for b in bars]
                    ),
                    "boundary_times": [t.isoformat() for t in boundaries],
                }
            )
    finally:
        engine.dispose()
    counts = Counter(d.dataset.source_month for d in days)
    if (
        dict(counts) != {"2024-02": 16, "2024-03": 15, "2024-04": 18}
        or sum(len(d.bars) for d in days) != 13524
    ):
        raise ValueError("bounded scope mismatch")
    print(
        "Verified 49 days / 13,524 bars and features. Running frozen baseline twice.",
        flush=True,
    )
    if (
        source_evidence != original["provenance"]["source_evidence"]
        or policy.policy_key != original["provenance"]["gap_policy_key"]
    ):
        raise ValueError("frozen source or policy changed")
    signal_counts = Counter(
        evaluate_xauusd(row, as_of=row.available_at).action
        for day in days
        for row in day.features
    )
    if signal_counts["BUY"] != 2140 or signal_counts["SELL"] != 1944:
        raise ValueError(f"signal discrepancy: {signal_counts}")
    study = Counter()
    for day in days:
        for row in day.features:
            v1 = evaluate_xauusd(row, as_of=row.available_at)
            v2 = evaluate_confirmation(row, as_of=row.available_at)
            study[f"v1_{v1.action}"] += 1
            study[f"v2_{v2.action}"] += 1
            if v1.side is not None and v2.side is None:
                study[v2.reasons[-1]] += 1
                value = next(
                    (v.value for v in row.values if v.name == "momentum_12"), None
                )
                study[
                    (
                        "unavailable"
                        if value is None
                        else "zero" if value == 0 else "opposite_sign"
                    )
                ] += 1
            if v2.side is not None and v2.side != v1.side:
                raise ValueError("V2 promoted or reversed a V1 signal")
    print(
        "PRE-EXECUTION SIGNAL STUDY:",
        json.dumps(dict(study), sort_keys=True),
        flush=True,
    )
    baseline = run_historical(days, config)
    if baseline.report_identity != original["report_identity"]:
        raise ValueError("V1 regression: frozen result identity changed")
    first = run_historical(days, config, strategy_version=VERSION)
    if any(r.reason == "ENTRY_NOT_TICK_ALIGNED" for r in first.records):
        raise ValueError("observed-market grid regression")
    if Counter(d.action for d in first.decisions) != Counter(
        {action: study[f"v2_{action}"] for action in ("BUY", "SELL", "NO_TRADE")}
    ):
        raise ValueError("execution changed signal accounting")
    for record in first.records:
        if record.entry_timestamp is not None:
            config.contract.specification.validate_price(record.effective_stop)
            config.contract.specification.validate_price(record.target)
            if record.entry_timestamp < record.signal_timestamp:
                raise ValueError("entry precedes completed signal")
    print("First run finished; checking exact repeat.", flush=True)
    second = run_historical(days, config, strategy_version=VERSION)
    if first != second or first.report_identity != second.report_identity:
        raise ValueError("deterministic replay mismatch")
    metadata = {
        "first_source_date": days[0].dataset.selected_source_date,
        "last_source_date": days[-1].dataset.selected_source_date,
        "rows": sum(len(d.bars) for d in days),
        "approved_days": len(days),
        "source_feature_dataset_key": manifest_report["feature_dataset_key"],
        "gap_policy_key": policy.policy_key,
        "source_evidence": source_evidence,
        "decision_counts": dict(Counter(d.action for d in first.decisions)),
        "checkpoint": "G2C4D1",
        "development_in_sample": True,
        "hypothesis": (
            "3-bar and 12-bar momentum sign agreement may reduce "
            "short-lived directional entries; improvement is not assumed"
        ),
        "single_rule_change": (
            "V1 BUY additionally momentum_12 > 0; V1 SELL additionally "
            "momentum_12 < 0"
        ),
        "signal_study": dict(study),
        "v1_replay_identity_equal": True,
        "original_report_identity": original["report_identity"],
        "frozen_configuration_equal": True,
        "frozen_source_evidence_equal": True,
        "observed_market_grid_rejections": 0,
        "generated_level_grid_rejections": sum(
            r.status == "NO_TRADE_CONTRACT_ALIGNMENT" for r in first.records
        ),
        "database_writes": 0,
        "deterministic_rerun_equal": True,
        "component_source_hashes": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                Path("src/trading_bot/strategies/xauusd.py"),
                Path("src/trading_bot/strategies/xauusd_confirmation.py"),
                Path("src/trading_bot/strategies/xauusd_levels.py"),
                Path("src/trading_bot/execution/simulator.py"),
                Path("src/trading_bot/execution/sizing.py"),
                Path("src/trading_bot/execution/protection.py"),
                Path("src/trading_bot/execution/protective_exits.py"),
                Path("src/trading_bot/execution/accounting.py"),
                Path("src/trading_bot/execution/research_backtest.py"),
                Path("config/xauusd_first_backtest.json"),
            )
        },
    }
    closed = [r for r in first.records if r.net_pnl is not None]
    multiples = [r.net_pnl / r.risk_budget for r in closed]
    metadata["mean_net_R"] = str(mean(multiples)) if multiples else None
    metadata["median_net_R"] = str(median(multiples)) if multiples else None
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "report_identity": first.report_identity,
        "provenance": metadata,
        "result": first.model_dump(mode="json"),
    }
    Path("docs/xauusd-v2-momentum-confirmation-development.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    write_markdown(first, metadata, original)
    print(first.metrics.model_dump_json(indent=2))
    print("Report identity:", first.report_identity)


if __name__ == "__main__":
    main()
