"""Deterministic synthetic records only: no engine, rules or broker calls."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.config.research import load_xauusd_research
from trading_bot.journal.models import (
    AccountSnapshot,
    DecisionEvent,
    EventType,
    MarketSnapshot,
    ReasonCode,
)


def synthetic_events(profile_path: Path) -> tuple[DecisionEvent, ...]:
    profile = load_xauusd_research(profile_path)
    account = AccountSnapshot(
        account_currency=profile.account.account_currency,
        balance=profile.account.reference_starting_balance,
    )
    steps = (
        (EventType.MARKET_EVALUATED, ReasonCode.SYNTHETIC_DEMONSTRATION),
        (EventType.SETUP_DETECTED, ReasonCode.SIGNAL_QUALIFIED),
        (EventType.TRADE_REJECTED, ReasonCode.MINIMUM_LOT_EXCEEDS_RISK),
        (EventType.POSITION_OPENED, ReasonCode.SYNTHETIC_DEMONSTRATION),
        (EventType.STOP_CREATED, ReasonCode.STOP_INITIALIZED),
        (EventType.STOP_MOVED, ReasonCode.STOP_MOVED_TO_BREAKEVEN),
        (EventType.POSITION_CLOSED, ReasonCode.MANUAL_EXIT),
    )
    events = []
    for i, (event_type, reason) in enumerate(steps):
        timestamp = datetime(2026, 1, 5, 12, tzinfo=UTC) + timedelta(minutes=i)
        details = {"synthetic": True, "rules_implemented": False}
        event = DecisionEvent(
            event_id=UUID(int=i + 1),
            timestamp=timestamp,
            event_type=event_type,
            canonical_symbol=profile.instrument.symbol,
            reason_code=reason,
            summary="Synthetic audit demonstration only: " + event_type.value,
            strategy_id="synthetic_audit_fixture",
            strategy_run_id=UUID(int=100),
            evaluation_id=UUID(int=101 if i < 3 else 102),
            trade_id=UUID(int=201 if i < 3 else 202),
            position_id=UUID(int=301) if i >= 3 else None,
            source="journal.synthetic_demo",
            account_snapshot=account,
            market_snapshot=MarketSnapshot(timestamp=timestamp),
            details=(
                details
                | {
                    "allowed_risk_usd": Decimal("2.50"),
                    "minimum_lot": Decimal("0.01"),
                    "calculated_risk_usd": Decimal("4.80"),
                }
                if i == 2
                else (
                    details
                    | {
                        "entry_price": Decimal("4102.50"),
                        "current_price": Decimal("4106.40"),
                        "r_multiple": Decimal("0.80"),
                    }
                    if i == 5
                    else details
                )
            ),
            previous_value=Decimal("4097.80") if i == 5 else None,
            new_value=Decimal("4102.60") if i == 5 else None,
        )
        events.append(event)
    return tuple(events)
