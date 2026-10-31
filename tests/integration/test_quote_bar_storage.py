from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from trading_bot.data.quote_bar_storage import (
    QuoteBarConflict,
    QuoteBarRepository,
    QuoteDataset,
)
from trading_bot.domain.quote_bars import QuoteBar

pytestmark = pytest.mark.integration


def synthetic():
    start = datetime(2024, 1, 16, 5, tzinfo=UTC)
    dataset = QuoteDataset(
        provider="TEST_FIXTURE",
        provider_symbol="XAU/USD",
        source_archive="synthetic-not-real.zip",
        source_sha256="a" * 64,
        source_month="2024-01",
        selected_source_date="2024-01-16",
        start=start,
        end=start + timedelta(days=1),
        source_timezone="UTC-05:00 fixed; no DST",
        normalization_version="fixture-v1",
        aggregation_version="fixture-v1",
    )
    bars = []
    for i in range(288):
        t = start + timedelta(minutes=5 * i)
        if t.hour == 22:
            continue
        bars.append(
            QuoteBar(
                opening_timestamp=t,
                tick_count=1,
                **{
                    f"{side}_{k}": Decimal("2000") + offset
                    for side, offset in [("bid", Decimal(0)), ("ask", Decimal("0.5"))]
                    for k in ("open", "high", "low", "close")
                },
            )
        )
    return dataset, tuple(bars)


def test_storage_idempotency_query_gap_and_provenance(history_engine):
    dataset, bars = synthetic()
    repo = QuoteBarRepository(history_engine)
    a = repo.import_bars(dataset, tuple(reversed(bars)), raw_ticks=276, invalid_ticks=0)
    b = repo.import_bars(dataset, bars, raw_ticks=276, invalid_ticks=0)
    assert (a.inserted, b.inserted, b.existing) == (276, 0, 276)
    assert a.run_id != b.run_id
    assert len(a.missing_openings) == 12 and all(
        t.hour == 22 for t in a.missing_openings
    )
    rows = repo.get_bars(
        dataset_key=a.dataset_key,
        symbol="XAUUSD",
        interval="5minute",
        start=dataset.start,
        end=dataset.end,
    )
    assert rows == bars
    assert (
        repo.get_bars(
            dataset_key=a.dataset_key,
            symbol="XAUUSD",
            interval="5minute",
            start=datetime(2024, 1, 16, 22, tzinfo=UTC),
            end=datetime(2024, 1, 16, 23, tzinfo=UTC),
        )
        == ()
    )
    assert (
        repo.get_bars(
            dataset_key="b" * 64,
            symbol="XAUUSD",
            interval="5minute",
            start=dataset.start,
            end=dataset.end,
        )
        == ()
    )
    evidence = repo.get_run(a.run_id)
    assert evidence["manifest"]["source_sha256"] == "a" * 64
    assert evidence["manifest"]["provider"] == "TEST_FIXTURE"
    assert evidence["manifest"]["provider_symbol"] == "XAU/USD"
    assert evidence["manifest"]["expected_bins"] == 288
    assert len(evidence["manifest"]["missing_openings"]) == 12
    assert (
        dataset.dataset_key
        != dataset.model_copy(update={"provider": "OTHER"}).dataset_key
    )
    different_price = bars[-1].model_copy(
        update={
            f"{side}_{kind}": getattr(bars[-1], f"{side}_{kind}") + Decimal("0.1")
            for side in ("bid", "ask")
            for kind in ("open", "high", "low", "close")
        }
    )
    with pytest.raises(QuoteBarConflict, match="bar values"):
        repo.import_bars(
            dataset, bars[:-1] + (different_price,), raw_ticks=276, invalid_ticks=0
        )
    changed = bars[-1].model_copy(update={"tick_count": 2})
    with pytest.raises(QuoteBarConflict):
        repo.import_bars(
            dataset, bars[:-1] + (changed,), raw_ticks=277, invalid_ticks=0
        )
    with pytest.raises(QuoteBarConflict):
        repo.import_bars(dataset, bars[:-1], raw_ticks=275, invalid_ticks=0)
    assert (
        repo.get_bars(
            dataset_key=a.dataset_key,
            symbol="XAUUSD",
            interval="5minute",
            start=dataset.start,
            end=dataset.end,
        )
        == bars
    )
    with history_engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM bid_ask_bars")) == 276
        assert (
            conn.scalar(
                text(
                    "SELECT count(*) FROM system_events "
                    "WHERE event_type='quote_bar_dataset_import'"
                )
            )
            == 2
        )


def test_migration_roundtrip_and_guard(history_engine):
    with history_engine.begin() as conn:
        config = Config("alembic.ini")
        config.attributes["connection"] = conn
        command.downgrade(config, "0006")
        assert conn.scalar(text("SELECT to_regclass('bid_ask_bars')")) is None
        command.upgrade(config, "head")
        command.check(config)
    dataset, bars = synthetic()
    QuoteBarRepository(history_engine).import_bars(
        dataset, bars, raw_ticks=276, invalid_ticks=0
    )
    with (
        pytest.raises(RuntimeError, match="bars still exist"),
        history_engine.begin() as conn,
    ):
        config.attributes["connection"] = conn
        command.downgrade(config, "0006")


def test_invalid_import_and_query(history_engine):
    dataset, bars = synthetic()
    repo = QuoteBarRepository(history_engine)
    with pytest.raises(ValueError):
        repo.import_bars(dataset, bars, raw_ticks=1, invalid_ticks=0)
    with pytest.raises(ValueError):
        repo.import_bars(dataset, (bars[0], bars[0]), raw_ticks=2, invalid_ticks=0)
    with pytest.raises(ValueError):
        repo.get_bars(
            dataset_key=dataset.dataset_key,
            symbol="XAUUSD",
            interval="5minute",
            start=dataset.start.replace(tzinfo=None),
            end=dataset.end,
        )
