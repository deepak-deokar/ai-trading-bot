"""Validated feature configuration and output contracts."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Self
from uuid import UUID, uuid4

import yaml
from pydantic import Field, field_validator, model_validator

from trading_bot.domain.market import utc
from trading_bot.domain.models import DomainModel, Symbol


class FeatureError(ValueError):
    """Invalid feature input, provenance, configuration or calculation."""


class FeatureSpec(DomainModel):
    name: str
    output: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    params: dict[str, int] = Field(default_factory=dict)

    @field_validator("params", mode="before")
    @classmethod
    def strict_parameters(cls, value: Any) -> Any:
        if not isinstance(value, dict) or any(
            type(v) is not int for v in value.values()
        ):
            raise ValueError("feature parameters must be integers")
        return value


class FeatureConfig(DomainModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    features: tuple[FeatureSpec, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique_outputs(self) -> Self:
        if len({s.output for s in self.features}) != len(self.features):
            raise ValueError("feature output names must be unique")
        return self

    @classmethod
    def load(cls, path: Path, name: str = "baseline_v1") -> "FeatureConfig":
        configs = yaml.safe_load(path.read_text())
        return cls(name=name, features=configs["feature_sets"][name])


class FeatureDefinition(DomainModel):
    name: str
    version: str = "1"
    description: str
    required_lookback: int
    input_fields: tuple[str, ...]
    parameters: dict[str, int]
    output: str
    output_type: Literal["float64"] = "float64"


class FeatureRow(DomainModel):
    symbol: Symbol
    timestamp: datetime
    available_at: datetime
    close: Decimal
    values: dict[str, float | None]
    unavailable: dict[str, Literal["WARMUP", "GAP_WARMUP", "ZERO_DENOMINATOR"]]
    sufficient_history: bool
    gap_before: bool = False

    @field_validator("timestamp", "available_at")
    @classmethod
    def normalize(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def availability(self) -> Self:
        if self.available_at <= self.timestamp:
            raise ValueError("features must become available after candle opening")
        return self


class FeatureResult(DomainModel):
    feature_set_key: str
    dataset_key: str
    manifest: dict[str, Any]
    rows: tuple[FeatureRow, ...]
    missing_bars: int


class FeatureReport(DomainModel):
    feature_run_id: UUID = Field(default_factory=uuid4)
    dataset_key: str
    feature_set_key: str
    feature_set: str
    symbols: tuple[str, ...]
    timeframe: str
    range: tuple[datetime, datetime]
    features_requested: int
    bars_loaded: int
    rows_generated: int
    rows_inserted: int
    warmup_rows: int
    gap_affected_rows: int
    missing_bars: int
    invalid_outputs: int = 0
    duration: float
    status: Literal["COMPLETED", "COMPLETED_WITH_WARNINGS"]
