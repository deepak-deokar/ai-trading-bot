"""Reject invalid calculations; distinguish expected nulls explicitly."""

import math

from trading_bot.features.definitions import FeatureError, FeatureRow, FeatureSpec


def validate_row(row: FeatureRow, specs: tuple[FeatureSpec, ...]) -> None:
    if set(row.values) != {s.output for s in specs}:
        raise FeatureError("output names do not match configuration")
    nulls = {k for k, v in row.values.items() if v is None}
    if nulls != set(row.unavailable):
        raise FeatureError("each null requires an explicit unavailability reason")
    history = not any(v in {"WARMUP", "GAP_WARMUP"} for v in row.unavailable.values())
    if row.sufficient_history != history:
        raise FeatureError("inconsistent sufficient-history flag")
    for spec in specs:
        value = row.values[spec.output]
        if value is None:
            continue
        if not math.isfinite(value):
            raise FeatureError("non-finite feature output")
        if spec.name == "session_progress" and not 0 <= value < 1:
            raise FeatureError("impossible session progress")
        if spec.name in {"minutes_since_open", "minutes_until_close"} and value < 0:
            raise FeatureError("impossible session time")
