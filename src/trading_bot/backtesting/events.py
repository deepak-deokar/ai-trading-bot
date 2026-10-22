"""Serializable chronological simulation events, never wall-clock decisions."""

from datetime import datetime
from typing import Any, Literal

from trading_bot.domain.models import DomainModel


class Event(DomainModel):
    sequence: int
    timestamp: datetime
    kind: Literal[
        "SESSION_OPEN",
        "BAR_OPEN",
        "BAR_COMPLETE",
        "FEATURE",
        "DECISION",
        "ORDER",
        "FILL",
        "PORTFOLIO",
        "SESSION_CLOSE",
        "WARNING",
    ]
    symbol: str | None = None
    reference: str | None = None
    details: dict[str, Any] = {}
