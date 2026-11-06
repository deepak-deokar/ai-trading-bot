"""Read-only approved Feb-Apr 2024 baseline; parameters frozen in explicit config."""

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
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


def display(value):
    if value is None:
        return "—"
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.01")))
    return str(value)


def write_markdown(result, metadata):
    m = result.metrics
    config = result.config
    spec = config.contract.specification
    lines = [
        "# XAUUSD G2C4C2 — first historical baseline backtest",
        "",
        (
            "This is an in-sample, unoptimized research run over the 49 "
            "previously approved"
        ),
        "HistData source days in February–April 2024. Three months is insufficient",
        "evidence for production use. These results are not proof of profitability.",
        "",
        (
            f"Backtest: `{result.backtest_version}`; strategy: "
            f"`{result.strategy_version}`;"
        ),
        (
            f"features: `{result.feature_version}`. Source dates: "
            f"{metadata['first_source_date']}"
        ),
        (
            f"through {metadata['last_source_date']}; {metadata['rows']} "
            "persisted bars/features."
        ),
        "",
        "**No trades executed under the frozen configuration.** The flat balance",
        "provides no executed-trade profitability evidence. Tick-grid incompatibility",
        "and unaffordable minimum risk account for all non-boundary signals.",
        "",
        "## Frozen research assumptions",
        "",
        (
            f"Starting balance: ${config.starting_balance}; risk fraction: "
            f"{config.risk_fraction}"
        ),
        (
            "(1%, research-only, no live default). Realized balance carries "
            "between months."
        ),
        f"TEST_FIXTURE contract: {spec.contract_size} ounces/volume unit; minimum",
        (
            f"{spec.minimum_volume}, maximum {spec.maximum_volume}, step "
            f"{spec.volume_step},"
        ),
        (
            f"tick {spec.tick_size}. Fixed round-trip commission: "
            f"${config.commission.fixed_round_trip_usd}."
        ),
        "These are synthetic values, not verified broker or MT5 specifications.",
        "The existing 0.01 entry grid is retained even where feed prices have finer",
        (
            "precision; off-grid entries are rejected, not rounded or tuned "
            "to increase trades."
        ),
        "",
        (
            "Strategy thresholds are unchanged: BUY EMA12>EMA26, "
            "difference>0, momentum3>0,"
        ),
        (
            "RSI55–70; SELL mirrored trend/momentum and RSI30–45. Both "
            "require spread<=0.75"
        ),
        (
            "and relative spread<=0.0003. Structure is exactly 12 continuous "
            "bars; target 2R."
        ),
        (
            "Config was written before observing performance. No parameter "
            "alternatives tested."
        ),
        "",
        "## Execution and selection policy",
        "",
        "At each bar opening, a pending prior-bar signal is finalized using ASK for",
        (
            "LONG or BID for SHORT. G2C4C1 validates the original structure "
            "and aligns levels;"
        ),
        (
            "G2C4B5 performs entry sizing, central lifecycle entry and "
            "entry-bar monitoring."
        ),
        "G2C4B4 monitors subsequent completed bars unchanged. Stop/target evaluation",
        "precedes any forced boundary close. Strategy decisions are evaluated only at",
        "completion, after those exits; a new signal may be attempted after an exit",
        "at that same completion, but may not enter until the next bar opens.",
        "",
        "An open position blocks another signal. At a predeclared approved day/gap",
        "boundary, remaining positions close at that bar's BID close (LONG) or ASK",
        "close (SHORT), timestamped at completion, as CLOSED_END_OF_RESEARCH_DAY.",
        "This label includes pre-gap research-segment closures. It is a modeled",
        (
            "last-observed close, not an exact tick timestamp or a broker "
            "market-close claim."
        ),
        "Signals at that boundary are rejected; no pending plan or position crosses",
        "it. Boundary times come from the frozen dated gap policy, not a peek at the",
        "next bar's prices. Unexpected missing bars abort the run. No bars are filled.",
        "",
        "Approved-day selection itself is retrospective coverage filtering. These",
        "results are conditional on the previously approved subset, not all calendar",
        "days or a live availability guarantee. Indicators use persisted per-day/gap",
        "resets. HistData is a research feed, not the future MT5 broker schedule/feed.",
        (
            "No slippage, liquidity limits, swap, financing, margin or "
            "leverage is modeled."
        ),
        "",
        "## Overall results",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for name, value in m:
        if not isinstance(value, dict):
            lines.append(f"| {name} | {display(value)} |")
    lines += ["", "Rejections (all generated BUY/SELL signals are reconciled):", ""]
    lines += [f"- `{k}`: {v}" for k, v in sorted(m.rejection_reasons.items())]
    lines += [
        f"- `SIGNAL_IGNORED_POSITION_OPEN`: {m.ignored_signals}",
        "",
        "Exit reasons:",
        "",
    ]
    lines += [f"- `{k}`: {v}" for k, v in sorted(m.exit_reasons.items())]
    lines += [
        "",
        "## Monthly results (no balance reset)",
        "",
        (
            "| Month | Start | End | Trades | Wins | Losses | Net USD | Win % "
            "| DD USD | DD % | LONG | SHORT |"
        ),
        (
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
            "---: | ---: | ---: |"
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
        lines.append(f"| {month} | " + " | ".join(display(v) for v in fields) + " |")
    lines += [
        "",
        "## Definitions, causality and reproducibility",
        "",
        (
            "Wins/losses and gross profit/gross loss are sums of "
            "positive/absolute negative"
        ),
        "**net trade P&L after commission**. Gross trading P&L separately reports the",
        "before-commission sum. Average loss is a positive magnitude; largest loss is",
        "signed. Profit factor and payoff ratio are null when their denominators are",
        "zero; no infinity is fabricated. Expectancy is net P&L per closed trade.",
        (
            "Drawdown is realized balance below its running peak, including "
            "initial balance."
        ),
        "Monthly drawdown starts at that month's opening balance; overall drawdown",
        "retains the full-period peak. Percentages/ratios use fixed 50-digit Decimal",
        "reporting precision; balances and monetary sums use exact adaptive precision.",
        "No Sharpe or annualized performance is reported.",
        "",
        "Every BUY/SELL has a record: closed trade, rejection, or ignored-open signal.",
        "NO_TRADE decisions also have timestamp/action/content-hash audit entries.",
        "Trade records retain signal reasons, structural source identities, fills,",
        (
            "risk budget, projected stop risk, costs, realized balance and "
            "breach/ambiguity."
        ),
        (
            "No gap-through loss is clipped to budget; nonpositive equity "
            "blocks new sizing."
        ),
        "",
        "Two exact runs matched full records, decisions, metrics and content identity:",
        f"`{result.report_identity}`.",
        "The generation timestamp is outside that mathematical identity. Approved",
        "feature manifests were checked, persisted bar/feature pairs matched, policy",
        "eligibility was rechecked, and database transactions were read-only.",
        "Machine-readable inputs/provenance, per-signal records, decision audit and",
        "monthly/overall metrics are in `xauusd-first-backtest.json`.",
        "",
        "Reproduce with the development database URL provided securely:",
        "",
        "```sh",
        "PYTHONPATH=src .venv/bin/python scripts/backtest_xauusd_first.py",
        "```",
        "",
        "This baseline is sensitive to the synthetic contract, commission, tick",
        "compatibility, approved-date selection and OHLC fill assumptions. The small",
        "sample and rejections limit generalization. No thresholds were changed after",
        "seeing results. No G2C4C3, trailing stops or ML work was performed.",
    ]
    Path("docs/xauusd-first-backtest.md").write_text("\n".join(lines) + "\n")


def main():
    config = ResearchBacktestConfig.model_validate_json(
        Path("config/xauusd_first_backtest.json").read_text()
    )
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
    first = run_historical(days, config)
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
    Path("docs/xauusd-first-backtest.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    write_markdown(first, metadata)
    print(first.metrics.model_dump_json(indent=2))
    print("Report identity:", first.report_identity)


if __name__ == "__main__":
    main()
