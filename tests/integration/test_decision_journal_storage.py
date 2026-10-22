from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from trading_bot.journal.demo import synthetic_events
from trading_bot.journal.models import DecisionEvent, EventType, ReasonCode
from trading_bot.journal.repository import DecisionJournal

pytestmark = pytest.mark.integration


def test_persist_query_roundtrip_and_append_only(history_engine):
    journal = DecisionJournal(history_engine)
    events = synthetic_events(Path("config/xauusd_v1.yaml"))
    for event in reversed(events):
        assert journal.record_event(event) == event.event_id
    assert journal.get_events() == events
    assert journal.get_trade_journal(events[3].trade_id) == events[3:]
    assert journal.get_events(event_type=EventType.TRADE_REJECTED) == (events[2],)
    assert journal.get_events_by_reason(ReasonCode.MINIMUM_LOT_EXCEEDS_RISK) == (
        events[2],
    )
    assert (
        journal.get_symbol_journal("XAUUSD", events[1].timestamp, events[3].timestamp)
        == events[1:3]
    )
    assert journal.get_events(canonical_symbol="RELIANCE") == ()
    assert journal.get_events(strategy_id="synthetic_audit_fixture") == events
    assert journal.get_events(strategy_id="absent") == ()
    assert journal.get_events(evaluation_id=events[0].evaluation_id) == events[:3]
    assert journal.get_events(position_id=events[3].position_id) == events[3:]
    assert journal.get_events(strategy_run_id=events[0].strategy_run_id) == events
    with pytest.raises(IntegrityError):
        journal.record_event(events[0].model_copy(update={"summary": "overwrite"}))
    assert journal.get_events()[0] == events[0]
    assert not any(hasattr(journal, name) for name in ("update", "delete", "upsert"))
    assert journal.get_events()[5].new_value == "4102.60"
    with history_engine.connect() as conn:
        payload = conn.execute(
            text("SELECT payload FROM decision_events WHERE event_id=:id"),
            {"id": events[2].event_id},
        ).scalar_one()
        assert payload["details"]["calculated_risk_usd"] == "4.80"
        assert payload["account_snapshot"]["balance"] == "500"


def test_ties_ranges_and_nse_events(history_engine):
    journal = DecisionJournal(history_engine)
    event = synthetic_events(Path("config/xauusd_v1.yaml"))[0]
    for i in (3, 1, 2):
        data = event.model_dump(mode="json") | {
            "event_id": str(UUID(int=i)),
            "canonical_symbol": "RELIANCE",
            "order_id": str(UUID(int=99)),
        }
        journal.record_event(DecisionEvent.model_validate(data))
    assert [e.event_id.int for e in journal.get_events()] == [1, 2, 3]
    assert len(journal.get_events(order_id=UUID(int=99))) == 3
    assert (
        len(
            journal.get_symbol_journal(
                "RELIANCE", event.timestamp, event.timestamp + timedelta(seconds=1)
            )
        )
        == 3
    )
    with pytest.raises(ValueError):
        journal.get_events(start=event.timestamp, end=event.timestamp)
    with pytest.raises(ValueError):
        journal.get_events(start=event.timestamp.replace(tzinfo=None))


def test_journal_migration_downgrade_upgrade_and_guard(history_engine):
    with history_engine.begin() as conn:
        config = Config("alembic.ini")
        config.attributes["connection"] = conn
        command.downgrade(config, "0005")
        assert conn.scalar(text("SELECT to_regclass('decision_events')")) is None
        command.upgrade(config, "head")
        command.check(config)
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0006"
    journal = DecisionJournal(history_engine)
    event = synthetic_events(Path("config/xauusd_v1.yaml"))[0]
    journal.record_event(event)
    with pytest.raises(RuntimeError, match="not empty"), history_engine.begin() as conn:
        config.attributes["connection"] = conn
        command.downgrade(config, "0005")
    assert journal.get_events() == (event,)
