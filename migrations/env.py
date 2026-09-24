"""Migration engine uses the same validated settings as the application."""

from alembic import context

from trading_bot.config.settings import load_settings
from trading_bot.database.models import Base
from trading_bot.database.session import build_engine


def run_migrations() -> None:
    external = context.config.attributes.get("connection")
    if external is not None:
        context.configure(
            connection=external, target_metadata=Base.metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    settings = load_settings()
    if context.is_offline_mode():
        context.configure(
            url=settings.database_url.get_secret_value(),
            target_metadata=Base.metadata,
            literal_binds=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = build_engine(settings)
        try:
            with engine.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=Base.metadata,
                    compare_type=True,
                )
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            engine.dispose()


run_migrations()
