"""Float64 causal array primitives. NaN is internal warm-up only."""

from typing import Literal

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


def lag(values: Array, period: int = 1) -> Array:
    result = np.full(len(values), np.nan)
    if period < len(values):
        result[period:] = values[:-period]
    return result


def rolling(
    values: Array, period: int, operation: Literal["mean", "std", "max", "min"]
) -> Array:
    result = np.full(len(values), np.nan)
    if len(values) >= period:
        windows = np.lib.stride_tricks.sliding_window_view(values, period)
        result[period - 1 :] = getattr(np, operation)(windows, axis=1)
    return result


def smooth(
    values: Array, period: int, *, wilder: bool = False, offset: int = 0
) -> Array:
    """Seed with n-value arithmetic mean, then causal O(n) recurrence."""
    result = np.full(len(values), np.nan)
    seed = offset + period - 1
    if seed < len(values):
        result[seed] = np.mean(values[offset : seed + 1])
        alpha = 1 / period if wilder else 2 / (period + 1)
        for i in range(seed + 1, len(values)):
            result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
    return result


def divide(numerator: Array, denominator: Array) -> Array:
    """Zero denominators are explicitly unavailable, never infinity."""
    result = np.full(len(numerator), np.nan)
    np.divide(numerator, denominator, out=result, where=denominator != 0)
    return result
