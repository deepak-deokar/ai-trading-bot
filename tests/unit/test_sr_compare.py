from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pytest

from trading_bot.backtesting import sr_compare as C
from trading_bot.backtesting.news_day import NY
from trading_bot.backtesting.session_window import CostModel
from trading_bot.backtesting.sr_strategy import ZONE, Level, Mids
from trading_bot.backtesting.sweep_strategy import build_days

COSTS = CostModel.from_yaml(Path("config/xauusd_costs_equiti.yaml"))


def ny(y: int, mo: int, d: int, h: int, mi: int = 0) -> int:
    return int(datetime(y, mo, d, h, mi, tzinfo=NY).timestamp())


def bars_with_day(path: Callable[[int], float]) -> dict[str, np.ndarray]:
    """Four weeks swinging +/-10 around 2000, then Monday 2024-02-05 whose mid at
    minute k after 03:00 New York is path(k) (k < 0 before 03:00)."""
    mins, mids = [], []
    t, end = ny(2024, 1, 7, 18), ny(2024, 2, 2, 17)
    while t < end:
        lt = datetime.fromtimestamp(t, NY)
        if (
            lt.hour != 17
            and lt.weekday() != 5
            and not (lt.weekday() == 6 and lt.hour < 18)
        ):
            mins.append(t)
            mids.append(2000 + 10 * np.sin(len(mins) / 60.0))
        t += 60
    t, end, start = ny(2024, 2, 4, 18), ny(2024, 2, 5, 16, 59), ny(2024, 2, 5, 3)
    while t <= end:
        mins.append(t)
        mids.append(path((t - start) // 60))
        t += 60
    m = np.array(mins, dtype=np.int64)
    mid = np.array(mids)
    bars: dict[str, np.ndarray] = {"minute_utc": m}
    for side, sign in (("bid", -1), ("ask", 1)):
        for part in ("open", "high", "low", "close"):
            bars[f"{side}_{part}"] = mid + sign * 0.15
    return bars


def breakout_path(k: int) -> float:
    if k < 0:
        return 1998.0
    if k < 15:  # 03:00-03:14 climbs from 1998 to 2004
        return 1998.0 + 6.0 * k / 14
    return min(2004.0 + 0.2 * (k - 15), 2040.0)


def only_prev_day(*_: object) -> dict[str, list[Level]]:
    return {
        "prev_day": [Level(2000.0, {"prev_day"})],
        "prev_week": [],
        "swing": [],
        "round": [],
    }


def test_round_step_follows_adr() -> None:
    assert C.round_step(12.0) == 10.0
    assert C.round_step(20.0) == 25.0
    assert C.round_step(40.0) == 50.0
    assert C.round_step(90.0) == 100.0


def test_breakout_found_with_stop_behind_the_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = bars_with_day(breakout_path)
    days = build_days(bars)
    k = len(days) - 1
    assert days[k].day == date(2024, 2, 5)
    monkeypatch.setattr(C, "type_levels", only_prev_day)
    mid = Mids.of(bars)
    sig = C.find_signals(bars, days, k, mid, ltypes=("prev_day",))
    brk = [s for s in sig if s.kind == "breakout"]
    assert len(brk) == 1
    s = brk[0]
    assert s.direction == 1 and s.ltype == "prev_day"
    assert bars["minute_utc"][s.entry_minute] == ny(2024, 2, 5, 3, 15)
    z = ZONE * s.adr
    assert s.stop == pytest.approx(2000.0 - z - C.BUFFER * s.adr)
    # nothing for level types with no levels
    assert C.find_signals(bars, days, k, mid, ltypes=("round",)) == []


def test_twin_copies_direction_stop_distance_and_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = bars_with_day(breakout_path)
    days = build_days(bars)
    k = len(days) - 1
    monkeypatch.setattr(C, "type_levels", only_prev_day)
    mid = Mids.of(bars)
    s = next(
        x
        for x in C.find_signals(bars, days, k, mid, ("prev_day",))
        if x.kind == "breakout"
    )
    r = C.simulate(bars, mid, days[k], s, 1.0, COSTS)
    assert r is not None and r.trade.exit_reason == "target"
    marks = C.entry_marks(bars, days[k])
    assert bars["minute_utc"][marks[0]] == ny(2024, 2, 5, 3)
    assert bars["minute_utc"][marks[-1]] == ny(2024, 2, 5, 13)
    t = C.twin(bars, mid, days[k], r, int(marks[20]), COSTS)
    assert t is not None and t.direction == r.trade.direction
    e = int(marks[20])
    assert mid.o[e] - t.stop == pytest.approx(r.risk_mid)
    assert t.target is not None
    assert t.target - t.entry == pytest.approx(t.entry - t.stop)


def test_risk_limits_scale_with_adr() -> None:
    assert C.risk_ok(3.0, 15.0)  # 0.2 ADR
    assert not C.risk_ok(2.0, 15.0)  # under 0.15 ADR
    assert not C.risk_ok(10.0, 15.0)  # over 0.6 ADR
    assert not C.risk_ok(31.0, 60.0)  # over the $30 cap
