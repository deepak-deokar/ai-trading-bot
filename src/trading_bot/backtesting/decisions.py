"""Explicit scripted test intents only; no indicators or decision rules."""

from pathlib import Path
from typing import Self

import yaml
from pydantic import Field, model_validator

from trading_bot.backtesting.orders import TradeIntent
from trading_bot.domain.models import DomainModel


class ScriptedDecisionSource(DomainModel):
    intents: tuple[TradeIntent, ...] = Field(default=(), max_length=10000)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({i.reference for i in self.intents}) != len(self.intents):
            raise ValueError("script references must be unique")
        return self

    @classmethod
    def load(cls, path: Path) -> "ScriptedDecisionSource":
        return cls.model_validate(yaml.safe_load(path.read_text()))
