"""Explicit trusted-code registration; configuration never imports Python code."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import Field, ValidationError

from trading_bot.data.identity import digest
from trading_bot.domain.models import DomainModel
from trading_bot.strategies.contracts import Strategy, StrategyContext, StrategyError


class StrategyConfig(DomainModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    version: str = Field(min_length=1, max_length=64)
    parameters: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class NoOpParameters(DomainModel):
    pass


class NoOpStrategy:
    def evaluate(self, context: StrategyContext) -> tuple[()]:
        context.validate()
        return ()


@dataclass(frozen=True)
class Definition:
    name: str
    version: str
    implementation: str
    parameters: type[DomainModel]
    factory: Callable[[Any], Strategy]


@dataclass(frozen=True)
class StrategyPlan:
    """Validated immutable configuration; factories create fresh per-symbol state."""

    definition: Definition
    configuration_json: str

    def manifest(self) -> dict[str, Any]:
        configuration = json.loads(self.configuration_json)
        return {**configuration, "identity": digest(configuration)}

    def create(self) -> Strategy:
        values = self.manifest()["parameters"]
        return self.definition.factory(
            self.definition.parameters.model_validate(values)
        )


class StrategyRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, Definition] = {}

    def register(self, definition: Definition) -> None:
        if definition.name in self._definitions:
            raise StrategyError("strategy already registered")
        self._definitions[definition.name] = definition

    def resolve(self, config: StrategyConfig) -> StrategyPlan:
        definition = self._definitions.get(config.name)
        if definition is None or definition.version != config.version:
            raise StrategyError("unknown strategy name or version")
        try:
            params = definition.parameters.model_validate(config.parameters)
        except ValidationError as error:
            raise StrategyError("invalid strategy parameters") from error
        manifest = {
            "name": definition.name,
            "version": definition.version,
            "implementation": definition.implementation,
            "parameters": params.model_dump(mode="json"),
        }
        return StrategyPlan(definition, json.dumps(manifest, sort_keys=True))


def builtin_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(Definition("noop", "1", "noop-v1", NoOpParameters, noop_factory))
    from trading_bot.strategies.baseline import (
        BaselineParameters,
        BaselineTrendMomentumStrategy,
    )

    registry.register(
        Definition(
            "baseline_trend_momentum_v1",
            "1",
            "baseline-trend-momentum-v1",
            BaselineParameters,
            BaselineTrendMomentumStrategy,
        )
    )
    return registry


def noop_factory(parameters: NoOpParameters) -> Strategy:
    return NoOpStrategy()
