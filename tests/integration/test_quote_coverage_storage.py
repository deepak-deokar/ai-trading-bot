from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from trading_bot.data.quote_bar_storage import QuoteBarRepository, QuoteDataset
from trading_bot.data.quote_coverage import coverage_for_run
from trading_bot.domain.quote_bars import QuoteBar

pytestmark = pytest.mark.integration


def test_run_scoped_coverage(history_engine):
    start = datetime(2024, 1, 16, 5, tzinfo=UTC)
    repo = QuoteBarRepository(history_engine)
    results = []
    for provider, offset in [("TEST_FIXTURE", 0), ("OTHER_FIXTURE", 1)]:
        ds = QuoteDataset(
            provider=provider,
            provider_symbol="XAU/USD",
            source_archive="fixture.zip",
            source_sha256="a" * 64,
            source_month="2024-01",
            selected_source_date="2024-01-16",
            start=start,
            end=start + timedelta(days=1),
            source_timezone="UTC-05:00",
            normalization_version="test-v1",
            aggregation_version="test-v1",
        )
        bar = QuoteBar(
            opening_timestamp=start + timedelta(minutes=5 * offset),
            tick_count=1,
            **{
                f"{side}_{key}": Decimal("2000")
                for side in ("bid", "ask")
                for key in ("open", "high", "low", "close")
            },
        )
        result = repo.import_bars(ds, (bar,), raw_ticks=1, invalid_ticks=0)
        summary = coverage_for_run(repo, result.run_id)
        assert summary.provenance.provider == provider
        assert summary.dataset_key == ds.dataset_key
        assert summary.observed_bars == 1 and len(summary.missing_openings) == 287
        assert summary.first_observed_bar == bar.opening_timestamp
        results.append(summary)
    assert results[0].dataset_key != results[1].dataset_key
    with pytest.raises(ValueError):
        coverage_for_run(repo, uuid4())
