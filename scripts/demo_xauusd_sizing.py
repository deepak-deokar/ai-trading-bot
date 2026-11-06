"""RESEARCH DEMONSTRATION ONLY; synthetic contract and risk, no live defaults."""

import json
from decimal import Decimal
from pathlib import Path

from trading_bot.domain.contracts import ContractSpecification, SpecificationSource
from trading_bot.execution.accounting import Commission, LinearUSDContract
from trading_bot.execution.sizing import SizingRequest, size_position


def main() -> None:
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
    results = []
    for stop in ("0.1", "0.5", "1", "2"):
        result = size_position(
            SizingRequest(
                account_equity=Decimal("500"),
                account_currency="USD",
                risk_fraction=Decimal("0.01"),
                stop_distance=Decimal(stop),
                contract=contract,
                commission=Commission(
                    currency="USD", fixed_round_trip_usd=Decimal("1.25")
                ),
            )
        )
        results.append(result.model_dump(mode="json"))
        print(
            stop, result.selected_volume, result.projected_net_stop_loss, result.reason
        )
    Path("docs/xauusd-risk-sizing-demo.json").write_text(
        json.dumps(
            {"scope": "RESEARCH DEMONSTRATION ONLY", "results": results}, indent=2
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
