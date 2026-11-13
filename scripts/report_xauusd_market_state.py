"""Read-only development feature generation; no strategies or outcome inputs."""

import hashlib
import json
from collections import Counter, defaultdict
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from pathlib import Path

from trading_bot.config.settings import load_settings
from trading_bot.data.gap_policy import load_gap_policy
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.data.research_input import approved_research_inputs
from trading_bot.database.session import build_engine
from trading_bot.features.market_state import VERSION, calculate_market_state
from trading_bot.features.research_repository import (
    ResearchFeatureRepository,
    content_hash,
)
from trading_bot.features.xauusd import VERSION as BASELINE
from trading_bot.features.xauusd import calculate_xauusd

SOURCE = Path("docs/xauusd-baseline-feature-persistence.json")


def describe(values):
    values = sorted(values)
    n = len(values)
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
        return {
            "count": n,
            "min": str(values[0]),
            "median": str((values[(n - 1) // 2] + values[n // 2]) / 2),
            "mean": str(sum(values, Decimal(0)) / n),
            "max": str(values[-1]),
            "p05": str(values[(5 * n + 99) // 100 - 1]),
            "p95": str(values[(95 * n + 99) // 100 - 1]),
        }


def generate(engine):
    policy = load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml"))
    evidence = json.loads(SOURCE.read_text())["first_pass"]
    months = Counter(x["manifest"]["source"]["source_month"] for x in evidence)
    if months != {"2024-02": 16, "2024-03": 15, "2024-04": 18}:
        raise ValueError("development scope differs")
    br, fr = QuoteBarRepository(engine), ResearchFeatureRepository(engine)
    values, missing, resets, manifests = defaultdict(list), Counter(), Counter(), []
    for e in evidence:
        m = e["manifest"]
        ds = QuoteDataset.model_validate(m["source"])
        bars = br.get_bars(
            dataset_key=ds.dataset_key,
            symbol="XAUUSD",
            interval="5minute",
            start=ds.start,
            end=ds.end,
        )
        batch = approved_research_inputs(ds, bars, policy, as_of=ds.end)
        old = fr.get_rows(
            source_dataset_key=ds.dataset_key,
            symbol="XAUUSD",
            feature_version=BASELINE,
            start=ds.start,
            end=ds.end,
            as_of=ds.end,
        )
        baseline = calculate_xauusd(batch)
        if (
            len(bars) != 276
            or old != baseline
            or content_hash([r.model_dump(mode="json") for r in old])
            != m["content_hash"]
        ):
            raise ValueError("baseline or input preservation check failed")
        rows = calculate_market_state(batch)
        payload = [r.model_dump(mode="json") for r in rows]
        # Recompute each complete prefix: all outputs must be causally identical.
        for cut in (1, 13, 37, 205, 250):
            prefix = batch.model_copy(
                update={
                    "inputs": batch.inputs[:cut],
                    "as_of": batch.inputs[cut - 1].available_at,
                }
            )
            if calculate_market_state(prefix) != rows[:cut]:
                raise ValueError("prefix causality failed")
        for row in rows:
            if row.sequence_reset:
                resets[row.sequence_reset] += 1
            for v in row.values:
                if v.value is None:
                    missing[v.name] += 1
                else:
                    values[v.name].append(v.value)
        manifests.append(
            {
                "dataset_key": ds.dataset_key,
                "source": ds.model_dump(mode="json"),
                "rows": len(rows),
                "bar_hash": content_hash([b.model_dump(mode="json") for b in bars]),
                "baseline_hash": m["content_hash"],
                "extension_hash": content_hash(payload),
            }
        )
    return {
        "days": len(manifests),
        "rows": sum(m["rows"] for m in manifests),
        "months": dict(months),
        "resets": dict(resets),
        "unavailable": dict(missing),
        "distributions": {k: describe(v) for k, v in values.items()},
        "datasets": manifests,
    }


def main():
    engine = build_engine(load_settings())
    try:
        first, second = generate(engine), generate(engine)
    finally:
        engine.dispose()
    if first != second:
        raise ValueError("deterministic rerun failed")
    report = {
        "feature_set_version": VERSION,
        "rerun_equal": True,
        "prefix_causality": True,
        "baseline_preserved": True,
        "may_july_used": False,
        "august_october": "LOCKED_UNPROCESSED",
        "source_manifest_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(
            Path("src/trading_bot/features/market_state.py").read_bytes()
        ).hexdigest(),
        "quantiles": "nearest-rank p05/p95; midpoint median",
        **first,
    }
    report["content_hash"] = content_hash(report)
    Path("docs/xauusd-market-state-features.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ("datasets", "distributions")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
