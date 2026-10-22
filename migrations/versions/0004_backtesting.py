"""Auditable simulation-only runs and atomic result ledgers."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("config_key", sa.String(64)),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_backtest_runs")),
        sa.CheckConstraint(
            "status IN ('RUNNING','COMPLETED','COMPLETED_WITH_WARNINGS','FAILED')",
            name=op.f("ck_backtest_runs_status"),
        ),
    )
    op.create_index("ix_backtest_runs_config_key", "backtest_runs", ["config_key"])
    op.create_table(
        "backtest_orders",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "order_id", name=op.f("pk_backtest_orders")),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["backtest_runs.run_id"],
            name=op.f("fk_backtest_orders_run_id_backtest_runs"),
        ),
    )
    for name in (
        "backtest_fills",
        "backtest_trades",
        "backtest_equity_points",
        "backtest_events",
    ):
        columns = [
            sa.Column("run_id", sa.Uuid(), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
        ]
        constraints = [
            sa.PrimaryKeyConstraint("run_id", "sequence", name=op.f(f"pk_{name}")),
            sa.ForeignKeyConstraint(
                ["run_id"],
                ["backtest_runs.run_id"],
                name=op.f(f"fk_{name}_run_id_backtest_runs"),
            ),
        ]
        if name == "backtest_fills":
            columns.append(sa.Column("order_id", sa.String(64), nullable=False))
            constraints.append(
                sa.ForeignKeyConstraint(
                    ["run_id", "order_id"],
                    ["backtest_orders.run_id", "backtest_orders.order_id"],
                    name=op.f("fk_backtest_fills_run_id_backtest_orders"),
                )
            )
        op.create_table(name, *columns, *constraints)


def downgrade() -> None:
    for name in (
        "backtest_events",
        "backtest_equity_points",
        "backtest_trades",
        "backtest_fills",
        "backtest_orders",
    ):
        op.drop_table(name)
    op.drop_index("ix_backtest_runs_config_key", table_name="backtest_runs")
    op.drop_table("backtest_runs")
