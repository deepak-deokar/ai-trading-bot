"""Reuse historical/feature query layers; reject stale or incompatible feature sets."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine

from trading_bot.backtesting.config import BacktestConfig
from trading_bot.backtesting.orders import BacktestError
from trading_bot.data.query import HistoryQuery
from trading_bot.data.snapshot import HistorySnapshot
from trading_bot.features.definitions import FeatureConfig, FeatureRow, FeatureSpec
from trading_bot.features.engine import FeatureCalendar, FeatureEngine
from trading_bot.features.repository import FeatureRepository


@dataclass(frozen=True)
class BacktestInputs:
    snapshot: HistorySnapshot
    features: tuple[FeatureRow, ...]
    manifest: dict[str, Any]


def load_inputs(
    engine: Engine, config: BacktestConfig, calendar: FeatureCalendar
) -> BacktestInputs:
    repository = FeatureRepository(engine)
    manifest = repository.get_manifest(config.feature_set_key)
    if manifest is None:
        raise BacktestError("missing feature set")
    snapshot = HistoryQuery(engine).get_snapshot(config.history, source=config.source)
    definitions: Any = manifest["definitions"]
    feature_config = FeatureConfig(
        name=str(manifest["feature_config"]),
        features=tuple(
            FeatureSpec(name=d["name"], output=d["output"], params=d["parameters"])
            for d in definitions
        ),
    )
    expected = FeatureEngine(calendar).generate(
        snapshot, config.history, source=config.source, config=feature_config
    )
    if expected.feature_set_key != config.feature_set_key:
        raise BacktestError("stale or incompatible historical/feature selection")
    rows = []
    for symbol in sorted(config.history.symbols):
        rows.extend(
            repository.get_features(
                feature_set_key=config.feature_set_key,
                symbol=symbol,
                start=config.history.start,
                end=config.history.end,
                as_of=config.history.end,
            )
        )
    rows.sort(key=lambda r: (r.timestamp, r.symbol))
    if tuple(rows) != expected.rows:
        raise BacktestError("stored features disagree with reproducible input")
    return BacktestInputs(snapshot, tuple(rows), expected.manifest)
