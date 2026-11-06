"""RESEARCH DEMONSTRATION ONLY: eight synthetic explicit-plan scenarios."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.domain.contracts import ContractSpecification, SpecificationSource
from trading_bot.domain.positions import PositionDirection
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.execution.accounting import Commission, LinearUSDContract
from trading_bot.execution.simulator import SimulationBar, TradePlan, simulate_trade


def main() -> None:
    timestamp = datetime(2024, 2, 20, 10, tzinfo=UTC)
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
    scenarios = (
        ("long_target", PositionDirection.LONG, "2000", "2005", "1998", "0.05"),
        ("long_stop", PositionDirection.LONG, "2000", "2002", "1995", "0.05"),
        ("short_target", PositionDirection.SHORT, "2000", "2002", "1994", "0.05"),
        ("short_stop", PositionDirection.SHORT, "2000", "2004", "1998", "0.05"),
        ("no_valid_volume", PositionDirection.LONG, "2000", "2002", "1998", "0.01"),
        ("gap_risk_breach", PositionDirection.LONG, "1990", "2002", "1990", "0.05"),
        ("ambiguous_stop", PositionDirection.LONG, "2000", "2006", "1994", "0.05"),
        ("open_at_end", PositionDirection.LONG, "2000", "2002", "1998", "0.05"),
    )
    results = []
    for index, (name, direction, opening, high, low, risk) in enumerate(scenarios, 1):
        plan = TradePlan(
            plan_id=UUID(int=index),
            direction=direction,
            created_at=timestamp,
            entry_timestamp=timestamp,
            stop_price=Decimal(
                "1995" if direction == PositionDirection.LONG else "2005"
            ),
            target_price=Decimal(
                "2005" if direction == PositionDirection.LONG else "1995"
            ),
            account_equity=Decimal("500"),
            account_currency="USD",
            risk_fraction=Decimal(risk),
            contract=contract,
            commission=Commission(currency="USD", fixed_round_trip_usd=Decimal("1.25")),
            source_identity=f"synthetic:{name}",
        )
        observations = []
        for bar_index, (bar_open, bar_high, bar_low) in enumerate(
            (("2000", "2002", "1998"), (opening, high, low))
        ):
            observations.append(
                SimulationBar(
                    bar=QuoteBar(
                        opening_timestamp=timestamp + timedelta(minutes=5 * bar_index),
                        bid_open=Decimal(bar_open),
                        bid_high=Decimal(bar_high),
                        bid_low=Decimal(bar_low),
                        bid_close=Decimal("2000"),
                        ask_open=Decimal(bar_open) + 1,
                        ask_high=Decimal(bar_high) + 1,
                        ask_low=Decimal(bar_low) + 1,
                        ask_close=Decimal("2001"),
                        tick_count=10,
                    ),
                    source_market_data_id=f"synthetic:{name}:bar:{bar_index}",
                )
            )
        result = simulate_trade(
            plan, observations, as_of=timestamp + timedelta(minutes=10)
        )
        summary = {
            "status": result.status.value,
            "volume": str(result.volume) if result.volume is not None else None,
            "entry": (
                str(result.entry_fill.executed_price) if result.entry_fill else None
            ),
            "exit": str(result.exit_fill.executed_price) if result.exit_fill else None,
            "risk_budget": (
                str(result.risk_budget) if result.risk_budget is not None else None
            ),
            "projected_stop_risk": (
                str(result.projected_stop_risk)
                if result.projected_stop_risk is not None
                else None
            ),
            "gross_usd": (
                str(result.gross_pnl) if result.gross_pnl is not None else None
            ),
            "commission_usd": str(result.costs) if result.costs is not None else None,
            "net_usd": str(result.net_pnl) if result.net_pnl is not None else None,
            "risk_budget_breached": result.risk_budget_breached,
        }
        results.append(
            {
                "scenario": name,
                "summary": summary,
                "result": result.model_dump(mode="json"),
            }
        )
        print(
            name, result.status.value, summary["net_usd"], result.risk_budget_breached
        )
    Path("docs/xauusd-simulator-demo.json").write_text(
        json.dumps(
            {
                "scope": (
                    "RESEARCH DEMONSTRATION ONLY; synthetic risk, contract and bars; "
                    "no strategy signals"
                ),
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
