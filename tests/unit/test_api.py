from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from trading_bot.api.app import SCHEMA_REVISION, create_app


def test_health_and_ready(settings):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalars.return_value.all.return_value = [
        SCHEMA_REVISION
    ]
    with TestClient(create_app(settings, engine)) as client:
        assert client.get("/health").json()["execution_enabled"] is False
        assert client.get("/ready").status_code == 200
        assert client.post("/orders", json={}).status_code == 404
    engine.dispose.assert_not_called()


def test_unavailable_database_does_not_leak_secrets(settings):
    engine = MagicMock()
    engine.connect.side_effect = OperationalError(
        "secret-url", {}, Exception("password")
    )
    with TestClient(create_app(settings, engine)) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/ready")
        assert response.status_code == 503
        assert "secret" not in response.text


def test_stale_schema_is_not_ready(settings):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalars.return_value.all.return_value = ["old"]
    with TestClient(create_app(settings, engine)) as client:
        assert client.get("/ready").status_code == 503
