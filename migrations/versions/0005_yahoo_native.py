"""Isolate unverified Yahoo-native prices without relabeling existing policies."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_market_bars_adjustment"), "market_bars", type_="check")
    op.create_check_constraint(
        op.f("ck_market_bars_adjustment"),
        "market_bars",
        "adjustment_type IN ('RAW','SPLIT_ADJUSTED','FULLY_ADJUSTED','YAHOO_NATIVE')",
    )
    op.create_check_constraint(
        op.f("ck_market_bars_source_adjustment"),
        "market_bars",
        "(source = 'yahoo_finance') = (adjustment_type = 'YAHOO_NATIVE')",
    )


def downgrade() -> None:
    # Never delete or silently relabel native-price research data on downgrade.
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM market_bars "
            "WHERE adjustment_type='YAHOO_NATIVE')"
        )
    ):
        raise RuntimeError("Downgrade blocked: YAHOO_NATIVE bars still exist")
    op.drop_constraint(
        op.f("ck_market_bars_source_adjustment"), "market_bars", type_="check"
    )
    op.drop_constraint(op.f("ck_market_bars_adjustment"), "market_bars", type_="check")
    op.create_check_constraint(
        op.f("ck_market_bars_adjustment"),
        "market_bars",
        "adjustment_type IN ('RAW','SPLIT_ADJUSTED','FULLY_ADJUSTED')",
    )
