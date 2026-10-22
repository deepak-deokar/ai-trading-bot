"""Stable clock events built from bounded calendar slots; no wall-clock decisions."""

from dataclasses import dataclass
from datetime import datetime

from trading_bot.backtesting.decisions import ScriptedDecisionSource
from trading_bot.data.calendar import Session
from trading_bot.data.snapshot import HistorySnapshot


@dataclass(frozen=True, order=True)
class Tick:
    timestamp: datetime
    priority: int
    reference: str
    kind: str


def timeline(
    snapshot: HistorySnapshot,
    sessions: tuple[Session, ...],
    script: ScriptedDecisionSource,
) -> list[Tick]:
    ticks: list[Tick] = []
    for index, session in enumerate(sessions):
        ticks.extend(
            (
                Tick(session.opens, 0, str(index), "SESSION_OPEN"),
                Tick(session.closes, 4, str(index), "SESSION_CLOSE"),
            )
        )
    for index, item in enumerate(snapshot.bars):
        ticks.extend(
            (
                Tick(item.bar.timestamp, 3, str(index), "BAR_OPEN"),
                Tick(item.available_at, 1, str(index), "BAR_COMPLETE"),
            )
        )
    for index, intent in enumerate(script.intents):
        ticks.append(Tick(intent.created_at, 2, str(index), "DECISION"))
    return sorted(ticks)
