"""Deterministic stratified random controls for frozen markout observations."""

import hashlib
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
from statistics import median

TRIALS = 1000
SEED_NAMESPACE = "xauusd-g2c4d3-matched-random-v1"
SCALE = 10**10
Stratum = tuple[str, str, str]  # source month, signal-time session, BUY/SELL


@dataclass(frozen=True)
class Observation:
    identity: str
    stratum: Stratum
    markout: Decimal
    favorable: Decimal
    adverse: Decimal


def units(value: Decimal) -> int:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("finite Decimal observation required")
    numerator, denominator = value.as_integer_ratio()
    scaled, remainder = divmod(numerator * SCALE, denominator)
    if remainder:
        raise ValueError("observation exceeds stored ten-decimal precision")
    return scaled


def matched_trials(
    pool: tuple[Observation, ...],
    counts: dict[Stratum, int],
    *,
    strategy: str,
    horizon: int,
) -> tuple[dict[str, object], ...]:
    """Price-blind sampling, exact strata; fail rather than silently fall back."""
    if horizon not in (5, 10, 20):
        raise ValueError("unsupported horizon")
    groups: dict[Stratum, list[tuple[str, int, int, int]]] = defaultdict(list)
    identities: set[str] = set()
    for item in pool:
        if item.identity in identities or item.stratum[2] not in ("BUY", "SELL"):
            raise ValueError("duplicate identity or invalid direction")
        identities.add(item.identity)
        groups[item.stratum].append(
            (
                item.identity,
                units(item.markout),
                units(item.favorable),
                units(item.adverse),
            )
        )
    for values in groups.values():
        values.sort(key=lambda v: v[0])
    for key, count in counts.items():
        if type(count) is not int or count < 0 or count > len(groups[key]):
            raise ValueError("insufficient candidate pool or invalid stratum count")
    if not sum(counts.values()):
        raise ValueError("empty population")
    output: list[dict[str, object]] = []
    for trial in range(TRIALS):
        seed = hashlib.sha256(
            f"{SEED_NAMESPACE}|{strategy}|{horizon}|{trial}".encode()
        ).digest()
        rng = random.Random(int.from_bytes(seed, "big"))
        totals = {side: [0, 0, 0, 0, 0] for side in ("BUY", "SELL", "ALL")}
        selection = hashlib.sha256()
        for key, count in sorted(counts.items()):
            for identity, markout, favorable, adverse in rng.sample(groups[key], count):
                selection.update((identity + "\n").encode())
                for side in (key[2], "ALL"):
                    stats = totals[side]
                    stats[0] += 1
                    stats[1] += markout
                    stats[2] += int(markout > 0)
                    stats[3] += favorable
                    stats[4] += adverse
        result: dict[str, object] = {
            "trial": trial,
            "selection_hash": selection.hexdigest(),
        }
        with localcontext() as ctx:
            ctx.prec = 60
            for side, (n, total, positive, favorable, adverse) in totals.items():
                result[side] = {
                    "count": n,
                    "mean_markout": Decimal(total) / (n * SCALE) if n else None,
                    "positive_pct": Decimal(positive) * 100 / n if n else None,
                    "mean_favorable": Decimal(favorable) / (n * SCALE) if n else None,
                    "mean_adverse": Decimal(adverse) / (n * SCALE) if n else None,
                }
        output.append(result)
    return tuple(output)


def distribution(values: list[Decimal], actual: Decimal) -> dict[str, Decimal]:
    if len(values) != TRIALS:
        raise ValueError("exactly 1000 trials required")
    ordered = sorted(values)
    with localcontext() as ctx:
        ctx.prec = 60
        return {
            "random_mean": sum(values, Decimal(0)) / TRIALS,
            "random_median": median(values),
            "p05": ordered[math.ceil(TRIALS * 0.05) - 1],
            "p95": ordered[math.ceil(TRIALS * 0.95) - 1],
            "actual": actual,
            "actual_percentile": (
                Decimal(sum(v < actual for v in values))
                + Decimal(sum(v == actual for v in values)) / 2
            )
            * 100
            / TRIALS,
        }
