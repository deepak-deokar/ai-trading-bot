"""RESEARCH DEMONSTRATION ONLY: bounded synthetic exit mechanics."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.domain.contracts import ContractSpecification, SpecificationSource
from trading_bot.domain.positions import PositionDirection
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote, QuoteSource
from trading_bot.execution.accounting import Commission, LinearUSDContract, realize_usd
from trading_bot.execution.protection import ProtectiveInstruction
from trading_bot.execution.protective_exits import evaluate_bar
from trading_bot.execution.xauusd import XAUUSDExecution


def main() -> None:
    timestamp = datetime(2024, 2, 20, 10, tzinfo=UTC)
    quote = MarketQuote(
        canonical_symbol="XAUUSD",
        timestamp=timestamp,
        bid=Decimal("2000"),
        ask=Decimal("2001"),
        source=QuoteSource.TEST_FIXTURE,
    )
    contract = LinearUSDContract(
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
    scenarios = (
        ("long_target", PositionDirection.LONG, "2000", "2006", "1998"),
        ("long_stop", PositionDirection.LONG, "2000", "2002", "1994"),
        ("short_target", PositionDirection.SHORT, "2000", "2002", "1994"),
        ("short_stop", PositionDirection.SHORT, "2000", "2004", "1998"),
        ("long_gap_stop", PositionDirection.LONG, "1993", "2002", "1993"),
        ("long_ambiguous", PositionDirection.LONG, "2000", "2006", "1994"),
    )
    rows = []
    for index, (name, direction, opening, high, low) in enumerate(scenarios, 1):
        state = XAUUSDExecution(simulation_id=UUID(int=index)).open(
            direction,
            Decimal("0.5"),
            quote,
            timestamp=timestamp,
            source_market_data_id=f"synthetic:{name}:entry",
        )
        assert state.position is not None
        instruction = ProtectiveInstruction(
            position_id=state.position.position_id,
            direction=direction,
            stop_price=Decimal(
                "1995" if direction == PositionDirection.LONG else "2005"
            ),
            target_price=Decimal(
                "2005" if direction == PositionDirection.LONG else "1995"
            ),
            created_at=timestamp,
            creation_quote=quote,
            source_identity=f"synthetic:{name}:instruction",
        )
        bar = QuoteBar(
            opening_timestamp=timestamp,
            tick_count=10,
            bid_open=Decimal(opening),
            bid_high=Decimal(high),
            bid_low=Decimal(low),
            bid_close=Decimal("2000"),
            ask_open=Decimal(opening) + 1,
            ask_high=Decimal(high) + 1,
            ask_low=Decimal(low) + 1,
            ask_close=Decimal("2001"),
        )
        result = evaluate_bar(
            state,
            instruction,
            bar,
            evaluated_at=bar.closing_timestamp,
            source_market_data_id=f"synthetic:{name}:bar",
        )
        accounting = realize_usd(result.lifecycle, contract, commission)
        rows.append(
            {
                "scenario": name,
                "evaluation": result.model_dump(mode="json"),
                "audit": {
                    "position_id": str(result.position_id),
                    "execution_side": result.execution_side.value,
                    "trigger_market_side": result.trigger_market_side,
                    "fill_price": str(result.fill_price),
                    "fill_id": str(result.fill_id),
                    "intrabar_ambiguous": result.intrabar_ambiguous,
                    "ambiguity_reason": result.ambiguity_reason,
                    "raw_price_movement": str(result.lifecycle.price_movement),
                },
                "accounting": accounting.model_dump(mode="json"),
            }
        )
        print(
            name,
            result.trigger.value,
            result.fill_price,
            result.lifecycle.price_movement,
        )
    Path("docs/xauusd-protective-exits-demo.json").write_text(
        json.dumps(
            {"scope": "RESEARCH DEMONSTRATION ONLY", "scenarios": rows}, indent=2
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
