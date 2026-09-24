from decimal import Decimal

from trading_bot.domain.models import Bar


def test_price_json_roundtrip_is_exact():
    bar = Bar(
        symbol="SPY",
        timestamp="2026-01-02T15:05:00Z",
        open="0.10",
        high="0.30",
        low="0.10",
        close="0.20",
        volume=1,
    )
    restored = Bar.model_validate_json(bar.model_dump_json())
    assert restored == bar
    assert restored.close - restored.open == Decimal("0.10")
