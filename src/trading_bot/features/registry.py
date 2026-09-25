"""Closed registry: no executable configuration or dynamic imports."""

from trading_bot.features.definitions import (
    FeatureDefinition,
    FeatureError,
    FeatureSpec,
)

# Description, input fields, accepted parameter names.
REGISTRY: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "return": ("Close ratio minus one", ("close",), ("period",)),
    "log_return": ("Natural log of close ratio", ("close",), ("period",)),
    "sma": ("Arithmetic mean of closes", ("close",), ("period",)),
    "ema": ("SMA-seeded exponential mean", ("close",), ("period",)),
    "sma_distance": ("Close / SMA minus one", ("close",), ("period",)),
    "ema_spread": ("(Fast EMA - slow EMA) / close", ("close",), ("fast", "slow")),
    "momentum": ("Close minus lagged close", ("close",), ("period",)),
    "rsi": ("Wilder smoothed RSI; flat seed returns 50", ("close",), ("period",)),
    "volatility": ("Population std of simple returns", ("close",), ("period",)),
    "atr": ("Wilder smoothed true range", ("high", "low", "close"), ("period",)),
    "range_pct": ("(High - low) / close", ("high", "low", "close"), ()),
    "true_range": ("Range including previous close", ("high", "low", "close"), ()),
    "volume_change": ("Volume ratio minus one", ("volume",), ()),
    "volume_mean": ("Rolling arithmetic volume mean", ("volume",), ("period",)),
    "volume_ratio": ("Volume / rolling mean", ("volume",), ("period",)),
    "rolling_high": ("Rolling maximum high", ("high",), ("period",)),
    "rolling_low": ("Rolling minimum low", ("low",), ("period",)),
    "high_distance": ("Close / rolling high minus one", ("high", "close"), ("period",)),
    "low_distance": ("Close / rolling low minus one", ("low", "close"), ("period",)),
    "breakout_distance": (
        "Close / prior rolling high minus one",
        ("high", "close"),
        ("period",),
    ),
    "minutes_since_open": (
        "Opening timestamp minutes since session open",
        ("timestamp",),
        (),
    ),
    "minutes_until_close": (
        "Opening timestamp minutes until session close",
        ("timestamp",),
        (),
    ),
    "session_progress": ("Elapsed / scheduled session duration", ("timestamp",), ()),
}


def resolve(spec: FeatureSpec) -> FeatureDefinition:
    if spec.name not in REGISTRY:
        raise FeatureError(f"unknown feature: {spec.name}")
    description, inputs, params = REGISTRY[spec.name]
    if set(spec.params) != set(params):
        raise FeatureError(f"{spec.name} requires explicit parameters {params}")
    if any(type(v) is not int or not 1 <= v <= 500 for v in spec.params.values()):
        raise FeatureError("periods must be integers in [1, 500]")
    period = spec.params.get("period", 1)
    if spec.name == "ema_spread":
        if spec.params["fast"] >= spec.params["slow"]:
            raise FeatureError("fast period must precede slow period")
        lookback = spec.params["slow"] - 1
    elif spec.name in {
        "return",
        "log_return",
        "momentum",
        "rsi",
        "atr",
        "volatility",
        "breakout_distance",
    }:
        lookback = period
    elif spec.name in {"true_range", "volume_change"}:
        lookback = 1
    elif params:
        lookback = period - 1
    else:
        lookback = 0
    return FeatureDefinition(
        name=spec.name,
        description=description,
        required_lookback=lookback,
        input_fields=inputs,
        parameters=spec.params,
        output=spec.output,
    )
