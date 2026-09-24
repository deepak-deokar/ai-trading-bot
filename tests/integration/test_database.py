import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from trading_bot.api.app import create_app
from trading_bot.config.settings import Settings
from trading_bot.database.models import Instrument, SystemEvent
from trading_bot.database.session import build_engine, session_factory

pytestmark = pytest.mark.integration


def test_postgresql_roundtrip_rollback_and_readiness():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated PostgreSQL database")
    settings = Settings(database_url=url)
    engine = build_engine(settings)
    try:
        with TestClient(create_app(settings, engine)) as client:
            assert client.get("/ready").status_code == 200
        # All test writes are rolled back, including server-generated timestamps.
        with engine.connect() as connection:
            transaction = connection.begin()
            from sqlalchemy.orm import Session

            with Session(
                bind=connection, join_transaction_mode="create_savepoint"
            ) as session:
                symbol = "T" + uuid4().hex[:10].upper()
                instrument = Instrument(symbol=symbol)
                event = SystemEvent(
                    run_id=uuid4(),
                    event_type="test",
                    severity="INFO",
                    message="Integration test",
                    details={"phase": 1},
                )
                session.add_all([instrument, event])
                session.commit()
                session.refresh(event)
                assert event.timestamp.utcoffset().total_seconds() == 0
                assert session.scalar(
                    select(Instrument).where(Instrument.symbol == symbol)
                )
                session.add(Instrument(symbol=symbol))
                with pytest.raises(IntegrityError):
                    session.flush()
                session.rollback()
            transaction.rollback()
        factory = session_factory(engine)
        with factory.begin() as session:
            assert (
                session.scalar(select(Instrument).where(Instrument.symbol == symbol))
                is None
            )
    finally:
        engine.dispose()
