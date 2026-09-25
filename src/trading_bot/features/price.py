"""Price, trend, momentum and volatility formulas."""

import numpy as np

from trading_bot.features.definitions import FeatureSpec
from trading_bot.features.numerics import Array, divide, lag, rolling, smooth


def calculate(spec: FeatureSpec, close: Array, high: Array, low: Array) -> Array:
    name, p = spec.name, spec.params.get("period", 1)
    previous = lag(close)
    if name in {"return", "log_return", "momentum"}:
        old = lag(close, p)
        if name == "momentum":
            return close - old
        ratio = close / old
        return np.log(ratio) if name == "log_return" else ratio - 1
    if name in {"sma", "sma_distance"}:
        mean = rolling(close, p, "mean")
        return mean if name == "sma" else close / mean - 1
    if name == "ema":
        return smooth(close, p)
    if name == "ema_spread":
        return (
            smooth(close, spec.params["fast"]) - smooth(close, spec.params["slow"])
        ) / close
    if name == "rsi":
        delta = close - previous
        gains = smooth(np.maximum(delta, 0), p, wilder=True, offset=1)
        losses = smooth(np.maximum(-delta, 0), p, wilder=True, offset=1)
        total = gains + losses
        result = 100 * divide(gains, total)
        result[total == 0] = 50
        return result
    if name == "volatility":
        return rolling(close / previous - 1, p, "std")
    if name == "range_pct":
        return (high - low) / close
    if name in {"true_range", "atr"}:
        tr = np.maximum(
            high - low, np.maximum(np.abs(high - previous), np.abs(low - previous))
        )
        return tr if name == "true_range" else smooth(tr, p, wilder=True, offset=1)
    if name in {"rolling_high", "high_distance", "breakout_distance"}:
        highest = rolling(high, p, "max")
        if name == "rolling_high":
            return highest
        return close / (lag(highest) if name == "breakout_distance" else highest) - 1
    if name in {"rolling_low", "low_distance"}:
        lowest = rolling(low, p, "min")
        return lowest if name == "rolling_low" else close / lowest - 1
    raise ValueError("unsupported price feature")
