"""Synthetic prices only; production archives are never read by these tests."""

import ast
import json
import runpy
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.data.gap_policy import load_gap_policy
from trading_bot.data.policy_import import evaluate_policy_day
from trading_bot.data.quote_bar_storage import QuoteBarRepository
from trading_bot.data.research_input import approved_research_inputs
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.features.research_repository import content_hash
from trading_bot.features.xauusd import calculate_xauusd

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/materialize_xauusd_validation.py"
API = runpy.run_path(str(SCRIPT))
POLICY = load_gap_policy(API["POLICY_PATH"])
EVIDENCE = json.loads(API["EVIDENCE_PATH"].read_text())


def synthetic(ds, missing=()):
    omitted = set(range(204, 216)) | set(missing)
    return tuple(
        QuoteBar(
            opening_timestamp=ds.start + timedelta(minutes=5 * i),
            tick_count=1,
            **{
                f"{side}_{k}": Decimal("2000.123")
                + Decimal(i) / 1000
                + (Decimal("0.201") if side == "ask" else 0)
                for side in ("bid", "ask")
                for k in ("open", "high", "low", "close")
            },
        )
        for i in range(288)
        if i not in omitted
    )


def test_scope_allowlist_provenance_and_exclusions():
    allowed = API["verify_scope"](POLICY, EVIDENCE)
    assert len(allowed) == 50
    assert not {"2024-05-27", "2024-06-19", "2024-07-04"} & allowed
    for month in EVIDENCE["months"]:
        for day in month["days"]:
            ds = API["dataset"](month, day["date"])
            bars = synthetic(ds)
            result = evaluate_policy_day(
                ds, bars, POLICY, raw_ticks=len(bars), invalid_ticks=0
            )
            assert result.eligibility.eligible == (day["date"] in allowed)
    ds = API["dataset"](EVIDENCE["months"][0], "2024-05-01")
    for bad in ("0" * 64,):
        invalid = ds.model_copy(update={"source_sha256": bad})
        bars = synthetic(invalid)
        assert not evaluate_policy_day(
            invalid, bars, POLICY, raw_ticks=276, invalid_ticks=0
        ).eligibility.eligible
    with pytest.raises(ValueError):
        type(ds).model_validate(ds.model_dump(exclude={"source_sha256"}))
    for bars in (
        synthetic(ds, missing=(1,)),
        synthetic(ds)
        + (
            synthetic(ds)[0].model_copy(
                update={"opening_timestamp": ds.start + timedelta(minutes=5 * 204)}
            ),
        ),
    ):
        bars = tuple(sorted(bars, key=lambda b: b.opening_timestamp))
        assert not evaluate_policy_day(
            ds, bars, POLICY, raw_ticks=len(bars), invalid_ticks=0
        ).eligibility.eligible


@pytest.mark.integration
def test_13800_exact_idempotent_rows_and_resets(history_engine):
    prepared = []
    for month in EVIDENCE["months"]:
        for day in month["days"]:
            if not day["proposed_eligible"]:
                continue
            ds = API["dataset"](month, day["date"])
            bars = synthetic(ds)
            ds = evaluate_policy_day(
                ds, bars, POLICY, raw_ticks=276, invalid_ticks=0
            ).coverage.provenance
            rows = calculate_xauusd(
                approved_research_inputs(ds, bars, POLICY, as_of=ds.end)
            )
            API["check_resets"](rows)
            prepared.append((ds, bars, rows))
    records = API["materialize"](history_engine, prepared, POLICY)
    assert sum(r["bar_first_inserted"] for r in records) == 13800
    assert sum(r["bar_second_inserted"] for r in records) == 0
    assert sum(r["bar_second_existing"] for r in records) == 13800
    assert sum(r["feature_first_inserted"] for r in records) == 13800
    assert sum(r["feature_second_inserted"] for r in records) == 0
    assert sum(r["feature_second_existing"] for r in records) == 13800
    assert sum(r["dataset_resets"] for r in records) == 50
    assert sum(r["discontinuity_resets"] for r in records) == 50
    repo = QuoteBarRepository(history_engine)
    for record, (ds, _, _) in zip(records, prepared, strict=True):
        assert record["bar_content_hash"] == content_hash(
            [b.model_dump(mode="json") for b in API["query_bars"](repo, ds)]
        )
    original = content_hash(API["identity"](records, POLICY))
    changed = [
        r | {"generated_at": "different", "bar_first_inserted": 0}
        for r in reversed(records)
    ]
    assert content_hash(API["identity"](changed, POLICY)) == original
    changed[0] = changed[0] | {"bar_content_hash": "0" * 64}
    assert content_hash(API["identity"](changed, POLICY)) != original


def test_runner_has_no_strategy_or_markout_import():
    tree = ast.parse(SCRIPT.read_text())
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(
        any(word in (module or "") for word in ("strategies", "markout", "backtest"))
        for module in imports
    )
