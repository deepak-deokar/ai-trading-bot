"""Explicit conservative intraday simulation assumptions."""

from decimal import Decimal
from typing import Literal

from pydantic import Field

from trading_bot.data.contracts import HistoryRequest
from trading_bot.domain.models import DomainModel


class BacktestConfig(DomainModel):
    history: HistoryRequest
    source: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    feature_set_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    starting_capital: Decimal = Field(gt=0, le=Decimal("1000000000000"))
    participation_rate: Decimal | None = Field(default=Decimal("0.1"), gt=0, le=1)
    exit_minutes_before_close: int = Field(default=10, ge=0, le=120, strict=True)
    execution_policy: Literal["STRICT_NEXT_OPEN_SETTLE_ON_COMPLETE_V1"] = (
        "STRICT_NEXT_OPEN_SETTLE_ON_COMPLETE_V1"
    )
    intrabar_policy: Literal["CONSERVATIVE"] = "CONSERVATIVE"
    gap_policy: Literal["FAIL_RUN"] = "FAIL_RUN"
    session_end: Literal["FORCE_FLATTEN"] = "FORCE_FLATTEN"
    capital_multiple: Literal[1] = 1
    shorts_enabled: Literal[False] = False
