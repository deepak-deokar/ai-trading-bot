"""NSE identities, historical candles, and ingestion auditing."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Do not relabel legacy U.S. instruments as Indian equities.
    op.add_column(
        "instruments",
        sa.Column(
            "exchange", sa.String(16), nullable=False, server_default="LEGACY_US"
        ),
    )
    op.add_column(
        "instruments",
        sa.Column("segment", sa.String(16), nullable=False, server_default="CASH"),
    )
    op.alter_column("instruments", "exchange", server_default=None)
    op.alter_column("instruments", "segment", server_default=None)
    op.alter_column(
        "instruments", "symbol", type_=sa.String(32), existing_type=sa.String(15)
    )
    op.drop_constraint("uq_instruments_symbol", "instruments", type_="unique")
    op.create_unique_constraint(
        "uq_instruments_identity", "instruments", ["exchange", "segment", "symbol"]
    )
    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("segment", sa.String(length=16), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("adjustment_type", sa.String(length=32), nullable=False),
        sa.Column("requested_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("calendar_version", sa.String(length=160), nullable=False),
        sa.Column("rows_received", sa.Integer(), nullable=False),
        sa.Column("rows_valid", sa.Integer(), nullable=False),
        sa.Column("rows_inserted", sa.Integer(), nullable=False),
        sa.Column("rows_skipped", sa.Integer(), nullable=False),
        sa.Column("rows_rejected", sa.Integer(), nullable=False),
        sa.Column("duplicates", sa.Integer(), nullable=False),
        sa.Column("conflicts", sa.Integer(), nullable=False),
        sa.Column("quality_issues", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('CREATED','RUNNING','COMPLETED','COMPLETED_WITH_WAR"
            "NINGS','FAILED')",
            name=op.f("ck_ingestion_runs_valid_status"),
        ),
        sa.CheckConstraint(
            "requested_start < requested_end",
            name=op.f("ck_ingestion_runs_ordered_range"),
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_ingestion_runs")),
    )
    op.create_table(
        "market_bars",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("open", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("high", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("low", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("close", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("open_interest", sa.BigInteger(), nullable=True),
        sa.Column("trade_count", sa.BigInteger(), nullable=True),
        sa.Column("vwap", sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("adjustment_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "adjustment_type IN ('RAW','SPLIT_ADJUSTED','FULLY_ADJUSTED')",
            name=op.f("ck_market_bars_adjustment"),
        ),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0 AND open < "
            "'Infinity'::numeric AND high < 'Infinity'::numeric AND low < "
            "'Infinity'::numeric AND close < 'Infinity'::numeric AND high "
            ">= open AND high >= close AND high >= low AND low <= open AND "
            "low <= close",
            name=op.f("ck_market_bars_valid_ohlc"),
        ),
        sa.CheckConstraint(
            "timeframe IN ('1minute','5minute','10minute','15minute','30min"
            "ute','1hour','1day')",
            name=op.f("ck_market_bars_timeframe"),
        ),
        sa.CheckConstraint(
            "available_at > timestamp", name=op.f("ck_market_bars_availability")
        ),
        sa.CheckConstraint(
            "volume >= 0 AND (open_interest IS NULL OR open_interest >= 0) "
            "AND (trade_count IS NULL OR trade_count >= 0)",
            name=op.f("ck_market_bars_quantities"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.run_id"],
            name=op.f("fk_market_bars_ingestion_run_id_ingestion_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_market_bars_instrument_id_instruments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_bars")),
        sa.UniqueConstraint(
            "instrument_id",
            "timeframe",
            "timestamp",
            "source",
            "adjustment_type",
            name="uq_market_bars_identity",
        ),
    )
    op.create_index(
        "ix_market_bars_lookup",
        "market_bars",
        ["instrument_id", "timeframe", "source", "adjustment_type", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    connection = op.get_bind()
    incompatible = connection.execute(
        sa.text(
            "SELECT 1 FROM instruments GROUP BY symbol HAVING count(*) > 1 "
            "UNION ALL SELECT 1 FROM instruments WHERE length(symbol) > 15 LIMIT 1"
        )
    ).first()
    if incompatible:
        raise RuntimeError("Phase 1 cannot represent current instrument identities")
    op.drop_index("ix_market_bars_lookup", table_name="market_bars")
    op.drop_table("market_bars")
    op.drop_table("ingestion_runs")
    op.drop_constraint("uq_instruments_identity", "instruments", type_="unique")
    op.create_unique_constraint("uq_instruments_symbol", "instruments", ["symbol"])
    op.alter_column(
        "instruments", "symbol", type_=sa.String(15), existing_type=sa.String(32)
    )
    op.drop_column("instruments", "segment")
    op.drop_column("instruments", "exchange")
