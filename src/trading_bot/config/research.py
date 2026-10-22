"""Metadata-only research profiles; never consumed as execution authorization."""

from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import Field, model_validator

from trading_bot.domain.instruments import Currency, Instrument
from trading_bot.domain.models import DomainModel


class ReferenceAccount(DomainModel):
    account_currency: Currency
    reference_starting_balance: Decimal = Field(gt=0, allow_inf_nan=False)


class FutureRiskSettings(DomainModel):
    """Unset means unspecified, not unlimited risk. No consumer applies these yet."""

    risk_per_trade_percent: Decimal | None = Field(default=None, gt=0, le=100)
    maximum_daily_loss_percent: Decimal | None = Field(default=None, gt=0, le=100)
    maximum_drawdown_percent: Decimal | None = Field(default=None, gt=0, le=100)
    maximum_open_positions: int | None = Field(default=None, gt=0, strict=True)


class XAUUSDResearchConfig(DomainModel):
    """V1 intent only. Capability declarations do not enable trading mechanics."""

    instrument: Instrument
    account: ReferenceAccount
    target_platform: Literal["MT5"] = "MT5"
    research_status: Literal["DOMAIN_CONFIGURATION_ONLY"] = "DOMAIN_CONFIGURATION_ONLY"
    future_risk: FutureRiskSettings = Field(default_factory=FutureRiskSettings)
    supports_long: Literal[True] = True
    supports_short: Literal[True] = True
    requires_bid_ask: Literal[True] = True
    uses_lot_quantity: Literal[True] = True
    requires_contract_specification: Literal[True] = True

    @model_validator(mode="after")
    def reference_profile(self) -> Self:
        if self.instrument.symbol != "XAUUSD":
            raise ValueError("XAUUSD research requires the canonical XAUUSD instrument")
        if self.account.account_currency != Currency.USD:
            raise ValueError("XAUUSD V1 reference account must be USD")
        if self.account.reference_starting_balance != Decimal("500"):
            raise ValueError("XAUUSD V1 reference starting balance must be USD 500")
        return self


def load_xauusd_research(path: Path) -> XAUUSDResearchConfig:
    """Explicit local YAML load, independent of runtime settings and credentials."""
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("research configuration must be a YAML mapping")
    return XAUUSDResearchConfig.model_validate(data)
