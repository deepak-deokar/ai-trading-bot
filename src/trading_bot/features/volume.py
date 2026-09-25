"""Volume features; a zero denominator means unavailable, not zero."""

from trading_bot.features.definitions import FeatureSpec
from trading_bot.features.numerics import Array, divide, lag, rolling


def calculate(spec: FeatureSpec, volume: Array) -> Array:
    if spec.name == "volume_change":
        return divide(volume, lag(volume)) - 1
    mean = rolling(volume, spec.params["period"], "mean")
    return mean if spec.name == "volume_mean" else divide(volume, mean)
