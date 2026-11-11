"""Corrected frozen $500 replay; original reports and trading logic are untouched."""

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

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


def write_markdown(result, metadata):
    m = result.metrics
    lines = [
        "# XAUUSD G2C4C3C — corrected frozen $500 historical backtest",
        "",
        (
            f"Backtest version: `{result.backtest_version}`. Strategy: "
            f"`{result.strategy_version}`."
        ),
        f"Features: `{result.feature_version}`. Identity: `{result.report_identity}`.",
        "",
        "The original $500, 1% risk, 12 continuous completed bars and 2R configuration",
        "is unchanged. Synthetic contract: 10 ounces/unit, volume min 0.25/max 2/step",
        "0.25, tick 0.01; fixed round-trip commission $1.25. All 49 approved February–",
        "April 2024 days and 13,524 bars/features match frozen provenance hashes.",
        "",
        "Only G2C4C3B changes execution semantics: observed entry/exit BID/ASK remains",
        "exact, including off-grid boundary/gap prices. Generated stops/targets obey",
        "the original contract grid. No strategy or parameter optimization occurred.",
        "",
        "One position at a time; signals while open are ignored, never queued. Signals",
        "use completed bars and enter no earlier than the next eligible opening.",
        "LONG enters ASK/exits BID; SHORT enters BID/exits ASK. Ambiguous bars use",
        "STOP_FIRST_CONSERVATIVE. Gap losses are not clipped to the risk budget.",
        "Open positions close at the last observed executable close at approved",
        "day/pre-gap segment boundaries; no position crosses a boundary. Realized",
        "balance carries between months and supplies subsequent sizing equity.",
        "",
        "## Overall results",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    lines += [
        f"| {name} | {value if value is not None else 'N/A'} |"
        for name, value in m
        if not isinstance(value, dict)
    ]
    lines += [
        f"| BUY signals | {metadata['decision_counts']['BUY']} |",
        f"| SELL signals | {metadata['decision_counts']['SELL']} |",
        "| observed-market grid rejections | 0 |",
        (
            f"| generated-level alignment rejections | "
            f"{metadata['generated_level_grid_rejections']} |"
        ),
    ]
    lines += ["", "Rejections by reason:", ""]
    lines += [f"- `{k}`: {v}" for k, v in sorted(m.rejection_reasons.items())]
    lines += ["", "Exit reasons:", ""]
    lines += [f"- `{k}`: {v}" for k, v in sorted(m.exit_reasons.items())]
    lines += [
        "",
        "## Monthly results",
        "",
        (
            "| Month | Start | End | Trades | Wins | Losses | Net USD | "
            "Win % | Max DD USD | Max DD % | LONG | SHORT |"
        ),
        (
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
            "---: | ---: | ---: | ---: |"
        ),
    ]
    for month, item in result.months.items():
        fields = (
            item.starting_balance,
            item.ending_balance,
            item.trades_closed,
            item.wins,
            item.losses,
            item.net_pnl,
            item.win_rate_percent,
            item.max_drawdown_usd,
            item.max_drawdown_percent,
            item.long_trades,
            item.short_trades,
        )
        lines.append(
            f"| {month} | "
            + " | ".join(str(v) if v is not None else "N/A" for v in fields)
            + " |"
        )
    lines += [
        "",
        "## Comparison and verification",
        "",
        "| Run | Plans attempted | Observed-grid rejections | Opened | Closed |",
        "| --- | ---: | ---: | ---: | ---: |",
        "| Frozen pre-fix | 4084 | 4047 | 0 | 0 |",
        (
            f"| Corrected | {m.trade_plans_attempted} | 0 | "
            f"{m.trades_opened} | {m.trades_closed} |"
        ),
        "",
        "This difference is a validation-semantics correction, not optimization. Every",
        (
            "directional signal is reconciled as rejected, "
            "opened/closed, or ignored while open."
        ),
        "Two full runs matched all records, decisions, metrics and content identity.",
        "Generation timestamp is outside mathematical identity. The retained offline",
        "end-to-end future-mutation regression verifies signal, entry, exit, P&L and",
        "balance through a closed trade are unchanged by later data mutations.",
        "",
        "Gross profit/loss are sums of positive/absolute negative net trade P&L after",
        (
            "commission; gross_trading_pnl separately reports "
            "before-commission P&L. Average"
        ),
        "loss is a magnitude, largest loss is signed. Drawdown uses realized balance,",
        (
            "including initial balance; monthly peaks start at the "
            "month's opening balance."
        ),
        (
            "Ratios are deterministic Decimal calculations, not "
            "annualized. No Sharpe is used."
        ),
        "",
        (
            "Three months is insufficient production evidence. Contract "
            "specifications remain"
        ),
        (
            "synthetic, approved-day selection is retrospective, and "
            "OHLC fills are simulation."
        ),
        (
            "No slippage, liquidity, swap, margin or leverage is "
            "modeled. No tuning follows"
        ),
        (
            "these results. Original $500 reports and $3,000 sensitivity "
            "files remain unchanged."
        ),
        "",
        "Reproduce with DATABASE_URL provided securely:",
        "",
        "```sh",
        "PYTHONPATH=src .venv/bin/python scripts/backtest_xauusd_corrected.py",
        "```",
    ]
    Path("docs/xauusd-first-backtest-corrected.md").write_text("\n".join(lines) + "\n")


def main():
    config = ResearchBacktestConfig.model_validate_json(
        Path("config/xauusd_first_backtest.json").read_text()
    )
    original = json.loads(Path("docs/xauusd-first-backtest.json").read_text())
    if config != ResearchBacktestConfig.model_validate_json(
        json.dumps(original["result"]["config"])
    ):
        raise ValueError("original configuration changed")
    allowed_changes = {
        "src/trading_bot/strategies/xauusd_levels.py",
        "src/trading_bot/execution/simulator.py",
        "src/trading_bot/execution/accounting.py",
    }
    for name, digest in original["provenance"]["component_source_hashes"].items():
        if (
            name not in allowed_changes
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
    first = run_historical(days, config)
    if any(r.reason == "ENTRY_NOT_TICK_ALIGNED" for r in first.records):
        raise ValueError("observed-market grid regression")
    if Counter(d.action for d in first.decisions) != signal_counts:
        raise ValueError("execution changed signal accounting")
    for record in first.records:
        if record.entry_timestamp is not None:
            config.contract.specification.validate_price(record.effective_stop)
            config.contract.specification.validate_price(record.target)
            if record.entry_timestamp < record.signal_timestamp:
                raise ValueError("entry precedes completed signal")
    print("First run finished; checking exact repeat.", flush=True)
    second = run_historical(days, config)
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
        "checkpoint": "G2C4C3C",
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
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "report_identity": first.report_identity,
        "provenance": metadata,
        "result": first.model_dump(mode="json"),
    }
    Path("docs/xauusd-first-backtest-corrected.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    write_markdown(first, metadata)
    print(first.metrics.model_dump_json(indent=2))
    print("Report identity:", first.report_identity)


if __name__ == "__main__":
    main()
