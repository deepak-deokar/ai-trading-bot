"""Append-only application API with deterministic, chronological reads."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Engine, insert, select

from trading_bot.database.models import DecisionEventRecord as Record
from trading_bot.domain.market import utc
from trading_bot.journal.models import DecisionEvent, EventType, ReasonCode


class DecisionJournal:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def record_event(self, event: DecisionEvent) -> UUID:
        # Revalidate even model_construct/model_copy inputs at the persistence boundary.
        event = DecisionEvent.model_validate(event.model_dump(mode="json"))
        payload = event.model_dump(mode="json")
        columns = {
            column.name: getattr(event, column.name)
            for column in Record.__table__.columns
            if column.name != "payload"
        }
        with self._engine.begin() as connection:
            # Plain INSERT: duplicate IDs fail; never update/upsert previous history.
            connection.execute(insert(Record).values(**columns, payload=payload))
        return event.event_id

    def get_events(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        canonical_symbol: str | None = None,
        event_type: EventType | None = None,
        reason_code: ReasonCode | None = None,
        trade_id: UUID | None = None,
        strategy_id: str | None = None,
        evaluation_id: UUID | None = None,
        order_id: UUID | None = None,
        position_id: UUID | None = None,
        strategy_run_id: UUID | None = None,
    ) -> tuple[DecisionEvent, ...]:
        """UTC [start, end), sorted by timestamp then event UUID for ties."""
        begin = utc(start) if start is not None else None
        stop = utc(end) if end is not None else None
        if begin is not None and stop is not None and begin >= stop:
            raise ValueError("journal range must have start < end")
        statement = select(Record.payload)
        if begin is not None:
            statement = statement.where(Record.timestamp >= begin)
        if stop is not None:
            statement = statement.where(Record.timestamp < stop)
        for name, value in {
            "canonical_symbol": canonical_symbol,
            "event_type": event_type,
            "reason_code": reason_code,
            "trade_id": trade_id,
            "strategy_id": strategy_id,
            "evaluation_id": evaluation_id,
            "order_id": order_id,
            "position_id": position_id,
            "strategy_run_id": strategy_run_id,
        }.items():
            if value is not None:
                statement = statement.where(getattr(Record, name) == value)
        statement = statement.order_by(Record.timestamp, Record.event_id)
        with self._engine.connect() as connection:
            return tuple(
                DecisionEvent.model_validate(row)
                for row in connection.scalars(statement)
            )

    def get_trade_journal(self, trade_id: UUID) -> tuple[DecisionEvent, ...]:
        return self.get_events(trade_id=trade_id)

    def get_symbol_journal(
        self, symbol: str, start: datetime, end: datetime
    ) -> tuple[DecisionEvent, ...]:
        return self.get_events(canonical_symbol=symbol, start=start, end=end)

    def get_events_by_reason(self, reason: ReasonCode) -> tuple[DecisionEvent, ...]:
        return self.get_events(reason_code=reason)
