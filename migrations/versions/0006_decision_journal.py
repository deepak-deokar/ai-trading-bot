"""Add the decision audit journal without changing existing market tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_symbol", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("strategy_id", sa.String(128)),
        sa.Column("trade_id", sa.Uuid()),
        sa.Column("evaluation_id", sa.Uuid()),
        sa.Column("order_id", sa.Uuid()),
        sa.Column("position_id", sa.Uuid()),
        sa.Column("strategy_run_id", sa.Uuid()),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.CheckConstraint("schema_version = 1", name="schema_version"),
    )
    op.create_index(
        "ix_decision_events_chronology", "decision_events", ["timestamp", "event_id"]
    )
    for name in (
        "canonical_symbol",
        "event_type",
        "reason_code",
        "trade_id",
        "strategy_id",
    ):
        op.create_index(
            f"ix_decision_events_{name}",
            "decision_events",
            [name, "timestamp", "event_id"],
        )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM decision_events)")):
        raise RuntimeError("Downgrade blocked: decision journal is not empty")
    op.drop_table("decision_events")
