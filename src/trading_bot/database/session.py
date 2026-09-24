"""Explicit engine ownership and transactional sessions."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from trading_bot.config.settings import Settings


def build_engine(settings: Settings) -> Engine:
    """Create a bounded pool without opening a connection until needed."""
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 3,
            "options": "-c timezone=UTC -c statement_timeout=3000",
        },
    )


def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Use factory.begin() to commit on success and roll back on errors."""
    return sessionmaker(bind=engine, expire_on_commit=False)
