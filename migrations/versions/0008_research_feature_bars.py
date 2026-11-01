"""Exact bid/ask research feature rows, isolated from NSE float64 features."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_feature_bars",
        sa.Column("source_dataset_key", sa.String(64), primary_key=True),
        sa.Column("opening_timestamp", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("feature_version", sa.String(64), primary_key=True),
        sa.Column("canonical_symbol", sa.String(32), nullable=False),
        sa.Column("interval", sa.String(16), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature_dataset_key", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_dataset_key", "opening_timestamp"],
            ["bid_ask_bars.dataset_key", "bid_ask_bars.opening_timestamp"],
        ),
        sa.CheckConstraint("available_at > opening_timestamp", name="availability"),
    )
    op.create_index(
        "ix_research_feature_selection",
        "research_feature_bars",
        ["canonical_symbol", "feature_version", "opening_timestamp"],
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM research_feature_bars)")
    ):
        raise RuntimeError("Downgrade blocked: research features still exist")
    op.drop_table("research_feature_bars")
