"""JSON logs with allowlisted context; never serialize settings or exceptions."""

import json
import logging
from datetime import UTC, datetime
from typing import ClassVar


class JsonFormatter(logging.Formatter):
    context_fields: ClassVar[tuple[str, ...]] = (
        "run_id",
        "strategy_id",
        "symbol",
        "prediction_id",
        "order_id",
        "broker_order_id",
        "event_type",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **{key: getattr(record, key, None) for key in self.context_fields},
        }
        # Exception text may contain connection URLs or external secrets.
        if record.exc_info and record.exc_info[0]:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    """Own only the application logger, preserving host logging configuration."""
    logger = logging.getLogger("trading_bot")
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
