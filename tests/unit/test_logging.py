import json
import logging

from trading_bot.monitoring.logging import JsonFormatter


def test_structured_context_and_exceptions():
    record = logging.LogRecord(
        "trading_bot",
        logging.ERROR,
        __file__,
        1,
        "Database unavailable",
        (),
        (ValueError, ValueError("password=secret"), None),
    )
    record.run_id = "run-1"
    record.api_key = "secret"
    result = JsonFormatter().format(record)
    payload = json.loads(result)
    assert payload["run_id"] == "run-1"
    assert payload["error_type"] == "ValueError"
    assert "secret" not in result
    assert payload["timestamp"].endswith("+00:00")
