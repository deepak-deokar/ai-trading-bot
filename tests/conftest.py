import os

import pytest


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in list(os.environ):
        if key.upper() in {
            "DATABASE_URL",
            "GROWW_ACCESS_TOKEN",
            "CONFIG_FILE",
            "TRADING_MODE",
            "LIVE_TRADING_ENABLED",
            "LIVE_TRADING_CONFIRMATION",
            "UNIVERSE",
            "BAR_INTERVAL_SECONDS",
            "LOG_LEVEL",
        }:
            monkeypatch.delenv(key)


@pytest.fixture
def settings():
    from trading_bot.config.settings import Settings

    return Settings(database_url="postgresql+psycopg://test:test@localhost:5432/test")


@pytest.fixture
def feature_inputs():
    """Deterministic NSE snapshots with real calendar and explicit provenance."""
    from datetime import datetime
    from decimal import Decimal
    from pathlib import Path
    from uuid import uuid4

    from trading_bot.data.calendar import NSECalendar
    from trading_bot.data.contracts import HistoryRequest
    from trading_bot.data.identity import dataset_identity
    from trading_bot.data.snapshot import HistorySnapshot, SnapshotBar
    from trading_bot.domain.models import Bar
    from trading_bot.features.definitions import FeatureConfig

    def make(
        *,
        count=40,
        symbols=("RELIANCE",),
        start="2026-01-05T09:15:00+05:30",
        end=None,
        missing=(),
        adjustment="RAW",
        closes=None,
        volumes=None,
    ):
        calendar = NSECalendar()
        begin = datetime.fromisoformat(start)
        limit = (
            datetime.fromisoformat(end) if end else begin.replace(hour=15, minute=30)
        )
        slots = list(
            calendar.expected_bars(
                begin, limit, HistoryRequest.model_fields["timeframe"].default
            ).items()
        )
        if end is None:
            slots = slots[:count]
            limit = slots[-1][1]
        request = HistoryRequest(
            symbols=symbols, start=begin, end=limit, adjustment_type=adjustment
        )
        run = uuid4()
        identity = dataset_identity(
            request, "local", run, calendar.provenance(begin, limit), {"fixture": True}
        )
        rows = []
        for k, symbol in enumerate(symbols):
            instrument = uuid4()
            for i, (timestamp, available) in enumerate(slots):
                if i in missing:
                    continue
                close = Decimal(
                    str(closes[i] if closes is not None else 100 + i + k * 1000)
                )
                bar = Bar(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=close,
                    high=close + 2,
                    low=close - 2,
                    close=close,
                    volume=volumes[i] if volumes is not None else 100 + i,
                    adjustment_type=adjustment,
                )
                rows.append(SnapshotBar(bar, available, instrument, run))
        return (
            request,
            HistorySnapshot(tuple(rows), (identity,)),
            FeatureConfig.load(Path("config/features.yaml")),
        )

    return make
