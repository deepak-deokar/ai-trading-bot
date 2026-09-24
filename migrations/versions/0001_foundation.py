"""Create foundation tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(15), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(symbol) > 0", name="ck_instruments_symbol_nonempty"),
        sa.PrimaryKeyConstraint("id", name="pk_instruments"),
        sa.UniqueConstraint("symbol", name="uq_instruments_symbol"),
    )
    op.create_table(
        "system_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_system_events"),
    )
    op.create_index("ix_system_events_timestamp", "system_events", ["timestamp"])
    op.create_index("ix_system_events_run_id", "system_events", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_system_events_run_id", table_name="system_events")
    op.drop_index("ix_system_events_timestamp", table_name="system_events")
    op.drop_table("system_events")
    op.drop_table("instruments")
