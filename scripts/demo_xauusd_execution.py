"""Two deterministic synthetic lifecycles only; no strategies or broker access."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.domain.positions import PositionDirection
from trading_bot.domain.quotes import MarketQuote, QuoteSource
from trading_bot.execution.xauusd import XAUUSDExecution


def main() -> None:
    timestamp = datetime(2024, 2, 20, 10, tzinfo=UTC)
    quote = MarketQuote(
        canonical_symbol="XAUUSD",
        timestamp=timestamp,
        bid=Decimal("2000.00"),
        ask=Decimal("2000.50"),
        source=QuoteSource.TEST_FIXTURE,
    )
    examples = []
    for number, direction in enumerate(PositionDirection, 1):
        initial = XAUUSDExecution(simulation_id=UUID(int=number))
        opened = initial.open(
            direction,
            Decimal("0.37"),
            quote,
            timestamp=timestamp,
            source_market_data_id="synthetic:unchanged-quote",
        )
        closed = opened.close(
            quote,
            timestamp=timestamp,
            source_market_data_id="synthetic:unchanged-quote",
        )
        examples.append(
            {
                "direction": direction.value,
                "synthetic_volume": "0.37",
                "lifecycle": closed.model_dump(mode="json"),
                "entry_fill": str(closed.fills[0].executed_price),
                "exit_fill": str(closed.fills[1].executed_price),
                "quote_spread": str(quote.spread),
                "raw_directional_price_movement": str(closed.price_movement),
                "spread_disadvantage_price_units": str(quote.spread),
            }
        )
    report = {
        "scope": "synthetic execution mechanics only; no account P&L",
        "examples": examples,
    }
    Path("docs/xauusd-execution-demo.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    for example in examples:
        print(
            example["direction"],
            example["entry_fill"],
            example["exit_fill"],
            example["raw_directional_price_movement"],
        )


if __name__ == "__main__":
    main()
