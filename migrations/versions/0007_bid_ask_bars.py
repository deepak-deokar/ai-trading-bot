"""Dedicated bid/ask research bars; existing NSE tables remain unchanged."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bid_ask_bars",
        sa.Column("dataset_key", sa.String(64), primary_key=True),
        sa.Column("opening_timestamp", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("canonical_symbol", sa.String(32), nullable=False),
        sa.Column("interval", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_symbol", sa.String(128), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("tick_count", sa.BigInteger(), nullable=False),
        *(
            sa.Column(f"{side}_{kind}", sa.Numeric(28, 10), nullable=False)
            for side in ("bid", "ask")
            for kind in ("open", "high", "low", "close")
        ),
        sa.CheckConstraint("interval = '5minute'", name="interval"),
        sa.CheckConstraint("canonical_symbol = 'XAUUSD'", name="symbol"),
        sa.CheckConstraint("tick_count > 0", name="tick_count"),
        sa.CheckConstraint(
            "mod(extract(epoch from opening_timestamp),300)=0", name="opening"
        ),
        *(
            sa.CheckConstraint(
                f"{side}_low > 0 AND {side}_low <= {side}_open "
                f"AND {side}_low <= {side}_close "
                f"AND {side}_high >= {side}_open AND {side}_high >= {side}_close",
                name=f"{side}_ohlc",
            )
            for side in ("bid", "ask")
        ),
        sa.CheckConstraint(
            "ask_open >= bid_open AND ask_high >= bid_high "
            "AND ask_low >= bid_low AND ask_close >= bid_close",
            name="not_crossed",
        ),
    )
    op.create_index(
        "ix_bid_ask_bars_selection",
        "bid_ask_bars",
        ["canonical_symbol", "interval", "opening_timestamp", "provider"],
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM bid_ask_bars)")):
        raise RuntimeError("Downgrade blocked: bid/ask research bars still exist")
    op.drop_table("bid_ask_bars")
