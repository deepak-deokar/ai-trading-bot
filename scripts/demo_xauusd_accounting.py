"""SYNTHETIC / TEST ONLY: explicit linear contract and volume, no broker claim."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.domain.contracts import ContractSpecification, SpecificationSource
from trading_bot.domain.positions import PositionDirection
from trading_bot.domain.quotes import MarketQuote, QuoteSource
from trading_bot.execution.accounting import Commission, LinearUSDContract, realize_usd
from trading_bot.execution.xauusd import XAUUSDExecution


def main() -> None:
    profile = LinearUSDContract(
        specification=ContractSpecification(
            contract_size=Decimal("10"),
            minimum_volume=Decimal("0.25"),
            maximum_volume=Decimal("2"),
            volume_step=Decimal("0.25"),
            tick_size=Decimal("0.01"),
            specification_source=SpecificationSource.TEST_FIXTURE,
        ),
        price_unit="USD_PER_TROY_OUNCE",
        contract_size_unit="TROY_OUNCES_PER_VOLUME_UNIT",
        quote_currency="USD",
        account_currency="USD",
    )
    commission = Commission(currency="USD", fixed_round_trip_usd=Decimal("1.25"))
    timestamp = datetime(2024, 2, 20, 10, tzinfo=UTC)
    entry = MarketQuote(
        canonical_symbol="XAUUSD",
        timestamp=timestamp,
        bid=Decimal("2000"),
        ask=Decimal("2000.50"),
        source=QuoteSource.TEST_FIXTURE,
    )
    results = []
    for i, direction in enumerate(PositionDirection, 1):
        bid = (
            Decimal("2002") if direction == PositionDirection.LONG else Decimal("1998")
        )
        exit_quote = MarketQuote(
            canonical_symbol="XAUUSD",
            timestamp=timestamp + timedelta(seconds=1),
            bid=bid,
            ask=bid + Decimal("0.50"),
            source=QuoteSource.TEST_FIXTURE,
        )
        opened = XAUUSDExecution(simulation_id=UUID(int=i)).open(
            direction,
            Decimal("0.5"),
            entry,
            timestamp=timestamp,
            source_market_data_id="synthetic:entry",
        )
        closed = opened.close(
            exit_quote,
            timestamp=exit_quote.timestamp,
            source_market_data_id="synthetic:exit",
        )
        result = realize_usd(closed, profile, commission)
        results.append(result.model_dump(mode="json"))
        print(
            direction.value,
            result.raw_price_movement,
            result.gross_usd,
            result.commission_usd,
            result.net_usd,
        )
    Path("docs/xauusd-usd-accounting-demo.json").write_text(
        json.dumps(
            {
                "scope": (
                    "SYNTHETIC / TEST ONLY; no broker specification "
                    "or strategy performance claim"
                ),
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
