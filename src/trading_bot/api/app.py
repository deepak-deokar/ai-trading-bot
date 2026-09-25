"""Observation-only API. No order submission endpoints or broker imports."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from trading_bot.config.settings import Settings, load_settings
from trading_bot.database.session import build_engine
from trading_bot.monitoring.logging import configure_logging

SCHEMA_REVISION = "0003"


def create_app(
    settings: Settings | None = None, engine: Engine | None = None
) -> FastAPI:
    """Inject settings/engine for testing; dispose only engines owned by the app."""
    config = settings if settings is not None else load_settings()
    configure_logging(config.log_level)
    database = engine if engine is not None else build_engine(config)
    logger = logging.getLogger("trading_bot.api")
    run_id = str(uuid4())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "Application started",
            extra={
                "run_id": run_id,
                "event_type": "application_started",
            },
        )
        try:
            yield
        finally:
            if engine is None:
                database.dispose()
            logger.info(
                "Application stopped",
                extra={
                    "run_id": run_id,
                    "event_type": "application_stopped",
                },
            )

    app = FastAPI(title="Trading Infrastructure", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "trading_mode": config.trading_mode,
            "execution_enabled": False,
        }

    @app.get("/ready", response_model=None)
    def ready() -> JSONResponse:
        try:
            with database.connect() as connection:
                connection.execute(text("SELECT 1"))
                revisions = (
                    connection.execute(text("SELECT version_num FROM alembic_version"))
                    .scalars()
                    .all()
                )
                if revisions != [SCHEMA_REVISION]:
                    return JSONResponse({"status": "not_ready"}, status_code=503)
        except SQLAlchemyError:
            logger.warning(
                "Database readiness failed",
                extra={
                    "run_id": run_id,
                    "event_type": "database_unavailable",
                },
            )
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return JSONResponse({"status": "ready"})

    return app
