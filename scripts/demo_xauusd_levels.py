"""Synthetic already-issued decisions and causal levels; never executes a trade."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from trading_bot.data.quote_bar_storage import QuoteDataset
from trading_bot.domain.contracts import ContractSpecification, SpecificationSource
from trading_bot.domain.models import Side
from trading_bot.domain.quote_bars import QuoteBar
from trading_bot.domain.quotes import MarketQuote, QuoteSource
from trading_bot.execution.accounting import Commission, LinearUSDContract
from trading_bot.strategies.xauusd import XAUUSDSignalDecision
from trading_bot.strategies.xauusd_levels import (
    StructureBar,
    finalize_levels,
    plan_structure,
)


def main() -> None:
    timestamp = datetime(2024, 2, 20, 10, tzinfo=UTC)
    dataset = QuoteDataset(
        provider="test_fixture",
        provider_symbol="synthetic_gold",
        source_archive="synthetic",
        source_sha256="a" * 64,
        source_month="2024-02",
        selected_source_date="2024-02-20",
        start=timestamp.replace(hour=5),
        end=timestamp.replace(hour=5) + timedelta(days=1),
        source_timezone="fixed UTC-05:00",
        normalization_version="synthetic-v1",
        aggregation_version="synthetic-v1",
    )
    items = tuple(
        StructureBar(
            dataset=dataset,
            bar=QuoteBar(
                opening_timestamp=timestamp + timedelta(minutes=5 * i),
                tick_count=10,
                bid_open=Decimal("2000"),
                bid_close=Decimal("2000"),
                bid_high=Decimal("2004"),
                bid_low=Decimal("1990") + Decimal(i) / 10,
                ask_open=Decimal("2001"),
                ask_close=Decimal("2001"),
                ask_low=Decimal("1991") + Decimal(i) / 10,
                ask_high=Decimal("2010") + Decimal(i) / 10,
            ),
        )
        for i in range(12)
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
    results = []
    for name, side, selected, bid, ask in (
        ("buy_valid", Side.BUY, items, "2001", "2002"),
        ("sell_valid", Side.SELL, items, "2001", "2002"),
        ("insufficient", Side.BUY, items[1:], "2001", "2002"),
        ("discontinuity", Side.BUY, items[:5] + items[6:], "2001", "2002"),
        ("entry_gap", Side.BUY, items, "1989", "1990"),
    ):
        decision = XAUUSDSignalDecision(
            opening_timestamp=items[-1].bar.opening_timestamp,
            available_at=items[-1].bar.closing_timestamp,
            side=side,
            reasons=("SYNTHETIC_ALREADY_ISSUED_DECISION",),
            feature_snapshot=(),
            source_dataset_key=dataset.dataset_key,
            source_feature_version="synthetic",
            source_feature_row_hash="synthetic-feature-hash",
        )
        structure = plan_structure(decision, selected, as_of=decision.available_at)
        entry = MarketQuote(
            canonical_symbol="XAUUSD",
            timestamp=decision.available_at,
            bid=Decimal(bid),
            ask=Decimal(ask),
            source=QuoteSource.TEST_FIXTURE,
        )
        final = finalize_levels(
            structure,
            entry,
            source_market_data_id=f"synthetic:{name}:entry",
            contract=contract,
            commission=Commission(currency="USD", fixed_round_trip_usd=Decimal("1.25")),
            account_equity=Decimal("500"),
            risk_fraction=Decimal("0.05"),
        )
        results.append(
            {
                "scenario": name,
                "source_bar_identities": [
                    x.source_identity for x in structure.source_bars
                ],
                "finalization": final.model_dump(mode="json"),
            }
        )
        print(name, final.status.value, structure.structural_stop, final.target)
    Path("docs/xauusd-initial-levels-demo.json").write_text(
        json.dumps(
            {
                "scope": (
                    "SYNTHETIC RESEARCH ONLY; "
                    "no trade execution or profitability claims"
                ),
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
