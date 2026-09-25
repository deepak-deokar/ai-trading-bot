"""Persist immutable numerical feature sets and completion-aware rows."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_sets",
        sa.Column("feature_set_key", sa.String(64), nullable=False),
        sa.Column("dataset_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("feature_set_key", name=op.f("pk_feature_sets")),
        sa.CheckConstraint("row_count > 0", name=op.f("ck_feature_sets_nonempty")),
    )
    op.create_index("ix_feature_sets_dataset_key", "feature_sets", ["dataset_key"])
    op.create_table(
        "feature_values",
        sa.Column("feature_set_key", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close", sa.Numeric(28, 10), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("unavailable", sa.JSON(), nullable=False),
        sa.Column("sufficient_history", sa.Boolean(), nullable=False),
        sa.Column("gap_before", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint(
            "feature_set_key", "symbol", "timestamp", name=op.f("pk_feature_values")
        ),
        sa.ForeignKeyConstraint(
            ["feature_set_key"],
            ["feature_sets.feature_set_key"],
            name=op.f("fk_feature_values_feature_set_key_feature_sets"),
        ),
        sa.CheckConstraint(
            "available_at > timestamp", name=op.f("ck_feature_values_availability")
        ),
    )
    op.create_index(
        "ix_feature_values_available",
        "feature_values",
        ["feature_set_key", "available_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_feature_values_available", table_name="feature_values")
    op.drop_table("feature_values")
    op.drop_index("ix_feature_sets_dataset_key", table_name="feature_sets")
    op.drop_table("feature_sets")
