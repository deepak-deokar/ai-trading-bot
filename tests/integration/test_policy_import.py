"""Offline PostgreSQL tests with synthetic bars; no vendor/network dependency."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from trading_bot.data.gap_policy import load_gap_policy
from trading_bot.data.policy_import import evaluate_policy_day, import_policy_day
from trading_bot.data.quote_bar_storage import (
    QuoteBarConflict,
    QuoteBarRepository,
    QuoteDataset,
)
from trading_bot.domain.quote_bars import QuoteBar

pytestmark = pytest.mark.integration
POLICY = load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml"))


def synthetic(day="2024-02-20", wrong=False):
    start = datetime.fromisoformat(day).replace(hour=5, tzinfo=UTC)
    segment = next(s for s in POLICY.segments if s.evidence.source_month == day[:7])
    dataset = QuoteDataset(
        provider="HISTDATA",
        provider_symbol="XAU/USD",
        source_archive="synthetic.zip",
        source_sha256="a" * 64 if wrong else segment.evidence.archive_sha256,
        source_month=day[:7],
        selected_source_date=day,
        start=start,
        end=start + timedelta(days=1),
        source_timezone=POLICY.source_timezone,
        normalization_version="histdata-ticks-v1",
        aggregation_version="bid-ask-utc-5minute-v1",
    )
    bars = tuple(
        QuoteBar(
            opening_timestamp=start + timedelta(minutes=5 * i),
            tick_count=1,
            **{
                f"{s}_{k}": Decimal("2000")
                for s in ("bid", "ask")
                for k in ("open", "high", "low", "close")
            },
        )
        for i in range(288)
        if i not in range(204, 216)
    )
    return dataset, bars


def ingest(repo, ds, bars, policy=POLICY):
    return import_policy_day(
        repo,
        ds,
        bars,
        policy,
        raw_ticks=sum(b.tick_count for b in bars),
        invalid_ticks=0,
    )


@pytest.mark.parametrize(
    "day,wrong",
    [
        ("2024-02-23", False),
        ("2024-02-19", False),
        ("2024-03-28", False),
        ("2024-03-29", False),
        ("2024-02-24", False),
        ("2024-02-20", True),
    ],
)
def test_rejected_dates_never_written(history_engine, day, wrong):
    ds, bars = synthetic(day, wrong)
    result = ingest(QuoteBarRepository(history_engine), ds, bars)
    assert not result.eligibility.eligible and result.imported is None
    with history_engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM bid_ask_bars")) == 0
        assert c.scalar(text("SELECT count(*) FROM system_events")) == 0


def test_gated_idempotency_conflict_isolation_and_january(history_engine):
    repo = QuoteBarRepository(history_engine)
    jan, jbars = synthetic("2024-01-16")
    legacy_payload = jan.model_dump(
        mode="json", exclude={"gap_policy_version", "gap_policy_key"}
    )
    assert (
        jan.dataset_key
        == hashlib.sha256(
            json.dumps(legacy_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    janrun = repo.import_bars(jan, jbars, raw_ticks=276, invalid_ticks=0)
    ds, bars = synthetic()
    first = ingest(repo, ds, tuple(reversed(bars)))
    second = ingest(repo, ds, bars)
    assert (
        first.imported.inserted,
        second.imported.inserted,
        second.imported.existing,
    ) == (276, 0, 276)
    assert first.imported.dataset_key != ds.dataset_key
    assert len(first.coverage.missing_openings) == 12
    manifest = repo.get_run(first.imported.run_id)["manifest"]
    assert manifest["gap_policy_key"] == POLICY.policy_key
    assert manifest["gap_policy_version"] == POLICY.policy_version

    def query(dataset, key):
        return repo.get_bars(
            dataset_key=key,
            symbol="XAUUSD",
            interval="5minute",
            start=dataset.start,
            end=dataset.end,
        )

    assert query(ds, first.imported.dataset_key) == bars
    changed = bars[-1].model_copy(
        update={
            f"{s}_{k}": Decimal("2001")
            for s in ("bid", "ask")
            for k in ("open", "high", "low", "close")
        }
    )
    with pytest.raises(QuoteBarConflict):
        ingest(repo, ds, bars[:-1] + (changed,))
    assert query(ds, first.imported.dataset_key) == bars
    assert query(jan, janrun.dataset_key) == jbars
    different = POLICY.model_copy(update={"policy_version": "synthetic-v2"})
    other = ingest(repo, ds, bars, different)
    assert other.imported.dataset_key != first.imported.dataset_key
    assert query(ds, ds.dataset_key) == ()
    with history_engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM system_events")) == 4


def test_audit_failure_rolls_back_inserted_bars(history_engine):
    with history_engine.begin() as c:
        c.execute(
            text(
                "ALTER TABLE system_events ADD CONSTRAINT reject_test_audit "
                "CHECK (event_type <> 'quote_bar_dataset_import')"
            )
        )
    ds, bars = synthetic()
    with pytest.raises(IntegrityError):
        ingest(QuoteBarRepository(history_engine), ds, bars)
    with history_engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM bid_ask_bars")) == 0
        assert c.scalar(text("SELECT count(*) FROM system_events")) == 0


def test_preflight_invalid_ticks_and_policy_rebinding():
    ds, bars = synthetic()
    with pytest.raises(ValueError):
        evaluate_policy_day(ds, bars, POLICY, raw_ticks=277, invalid_ticks=1)
    approved = evaluate_policy_day(ds, bars, POLICY, raw_ticks=276, invalid_ticks=0)
    with pytest.raises(ValueError):
        evaluate_policy_day(
            approved.coverage.provenance,
            bars,
            POLICY.model_copy(update={"policy_version": "other"}),
            raw_ticks=276,
            invalid_ticks=0,
        )
