"""Synthetic offline persistence and rollback checks in disposable schemas."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from trading_bot.data.gap_policy import load_gap_policy
from trading_bot.data.policy_import import import_policy_day
from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.data.research_input import approved_research_inputs
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.features.definitions import FeatureError
from trading_bot.features.research_repository import ResearchFeatureRepository
from trading_bot.features.xauusd import VERSION, calculate_xauusd

pytestmark = pytest.mark.integration
POLICY = load_gap_policy(Path("config/histdata_xauusd_gap_policy_v1.yaml"))


def prepare(engine):
    start = datetime(2024, 2, 20, 5, tzinfo=UTC)
    ds = QuoteDataset(
        provider="HISTDATA",
        provider_symbol="XAU/USD",
        source_archive="synthetic.zip",
        source_sha256=POLICY.segments[1].evidence.archive_sha256,
        source_month="2024-02",
        selected_source_date="2024-02-20",
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
                f"{s}_{k}": Decimal("2000.1234567890")
                + Decimal(i)
                + (Decimal("0.0000000001") if s == "ask" else 0)
                for s in ("bid", "ask")
                for k in ("open", "high", "low", "close")
            },
        )
        for i in range(288)
        if i not in range(204, 216)
    )
    audit = import_policy_day(
        QuoteBarRepository(engine), ds, bars, POLICY, raw_ticks=276, invalid_ticks=0
    )
    return audit.coverage.provenance, bars


def query(repo, ds, version=VERSION):
    return repo.get_rows(
        source_dataset_key=ds.dataset_key,
        symbol="XAUUSD",
        feature_version=version,
        start=ds.start,
        end=ds.end,
        as_of=ds.end,
    )


def test_exact_roundtrip_idempotency_conflict_and_nulls(history_engine):
    ds, bars = prepare(history_engine)
    repo = ResearchFeatureRepository(history_engine)
    first = repo.generate(ds, POLICY)
    second = repo.generate(ds, POLICY)
    assert (first["inserted"], second["inserted"], second["existing"]) == (276, 0, 276)
    assert first["feature_dataset_key"] == second["feature_dataset_key"]
    expected = calculate_xauusd(
        approved_research_inputs(ds, bars, POLICY, as_of=ds.end)
    )
    assert query(repo, ds) == expected
    assert query(repo, ds, "wrong-version") == ()
    assert expected[0].value("return_1") is None
    assert expected[204].sequence_reset == "DISCONTINUITY"
    assert expected[204].value("ema_26") is None
    assert expected[0].value("mid_close") == Decimal("2000.12345678905")
    assert first["manifest"]["source"]["gap_policy_version"] == POLICY.policy_version
    with history_engine.connect() as c:
        payload = c.execute(
            text(
                "SELECT payload FROM research_feature_bars "
                "ORDER BY opening_timestamp LIMIT 1"
            )
        ).scalar_one()
        assert (
            next(v for v in payload["values"] if v["name"] == "return_1")["value"]
            is None
        )
        assert isinstance(
            next(v for v in payload["values"] if v["name"] == "relative_spread")[
                "value"
            ],
            str,
        )
    with history_engine.begin() as c:
        c.execute(
            text(
                "UPDATE research_feature_bars SET feature_dataset_key=:k "
                "WHERE opening_timestamp=:t"
            ),
            {"k": "a" * 64, "t": expected[-1].opening_timestamp},
        )
    with pytest.raises(FeatureError, match="conflicting"):
        repo.generate(ds, POLICY)
    with history_engine.connect() as c:
        assert (
            c.scalar(
                text(
                    "SELECT count(*) FROM system_events "
                    "WHERE event_type='research_feature_import'"
                )
            )
            == 2
        )
        assert c.scalar(text("SELECT count(*) FROM research_feature_bars")) == 276


def test_audit_failure_rollback_and_excluded_input(history_engine):
    ds, bars = prepare(history_engine)
    repo = ResearchFeatureRepository(history_engine)
    with pytest.raises(ValueError):
        repo.generate(
            ds.model_copy(update={"gap_policy_key": None, "gap_policy_version": None}),
            POLICY,
        )
    with history_engine.begin() as c:
        c.execute(
            text(
                "ALTER TABLE system_events ADD CONSTRAINT test_no_features "
                "CHECK (event_type <> 'research_feature_import')"
            )
        )
    with pytest.raises(IntegrityError):
        repo.generate(ds, POLICY)
    with history_engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM research_feature_bars")) == 0
        assert c.scalar(text("SELECT count(*) FROM bid_ask_bars")) == len(bars)


def test_migration_roundtrip(history_engine):
    with history_engine.begin() as c:
        config = Config("alembic.ini")
        config.attributes["connection"] = c
        command.downgrade(config, "0007")
        assert c.scalar(text("SELECT to_regclass('research_feature_bars')")) is None
        command.upgrade(config, "head")
        command.check(config)
    ds, _ = prepare(history_engine)
    ResearchFeatureRepository(history_engine).generate(ds, POLICY)
    with (
        pytest.raises(RuntimeError, match="features still exist"),
        history_engine.begin() as c,
    ):
        config.attributes["connection"] = c
        command.downgrade(config, "0007")
