from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from trading_bot.backtesting import sr_strategy as S
from trading_bot.backtesting.news_day import NY
from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import CostModel
from trading_bot.backtesting.sweep_strategy import build_days

COSTS = CostModel.from_yaml(Path("config/xauusd_costs_equiti.yaml"))


def ny(y: int, mo: int, d: int, h: int, mi: int = 0) -> int:
    return int(datetime(y, mo, d, h, mi, tzinfo=NY).timestamp())


def test_merge_levels_joins_close_levels_and_counts_touches() -> None:
    out = S.merge_levels(
        [S.Level(100.0, {"a"}), S.Level(100.5, {"b"}), S.Level(110.0, {"c"})], 1.0
    )
    assert len(out) == 2
    assert out[0].price == pytest.approx(100.25)
    assert out[0].kinds == {"a", "b"} and out[0].touches == 2


def test_swing_levels_need_two_turns() -> None:
    hi = np.array([1, 2, 3, 9, 3, 2, 1, 2, 3, 9.1, 3, 2, 1, 5, 6, 7, 6, 5, 4], float)
    lo = hi - 0.5
    levels = S.swing_levels(hi, lo, merge=0.5)
    # two lows at 0.5 and two highs near 9; the single peak at 7 does not count
    assert [round(x.price, 2) for x in levels] == [0.5, 9.05]
    assert [x.touches for x in levels] == [2, 2]


def weeks_then_setup_day() -> dict[str, np.ndarray]:
    """Four weeks swinging +/-10 around 2000 (ADR about 20), then a Monday that
    sits at 2003 and bounces off support at 2000 in the 03:00-03:15 candle."""
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
    t, end = ny(2024, 2, 4, 18), ny(2024, 2, 5, 16, 59)
    bounce = {0: 2003.0, 5: 2000.5, 10: 2002.0, 14: 2004.5}
    start = ny(2024, 2, 5, 3)
    while t <= end:
        mins.append(t)
        k = (t - start) // 60
        if t < start:
            mids.append(2003.0)
        elif k < 15:
            # 03:00-03:14: dip to 2000.5, close at 2004.5
            keys = sorted(bounce)
            lo_k = max(x for x in keys if x <= k)
            hi_k = min((x for x in keys if x >= k), default=lo_k)
            a, b = bounce[lo_k], bounce[hi_k]
            mids.append(a if hi_k == lo_k else a + (b - a) * (k - lo_k) / (hi_k - lo_k))
        else:
            mids.append(min(2004.5 + 0.2 * (k - 15), 2040.0))
        t += 60
    m = np.array(mins, dtype=np.int64)
    mid = np.array(mids)
    bars = {"minute_utc": m}
    for side, sign in (("bid", -1), ("ask", 1)):
        for part in ("open", "high", "low", "close"):
            bars[f"{side}_{part}"] = mid + sign * 0.15
    return bars


def test_bounce_off_support_is_found_and_traded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = weeks_then_setup_day()
    days = build_days(bars)
    k = len(days) - 1
    assert days[k].day == date(2024, 2, 5)

    def only_support(*_: object) -> list[S.Level]:
        return [S.Level(2000.0, {"prev_day"})]

    monkeypatch.setattr(S, "day_levels", only_support)
    mid = S.Mids.of(bars)
    setups = S.find_setups(bars, days, k, mid)
    bounces = [s for s in setups if s.kind == "bounce" and s.level == 2000.0]
    assert len(bounces) == 1
    s = bounces[0]
    assert s.direction == 1
    # entry is the first minute after the 03:00-03:15 candle
    assert bars["minute_utc"][s.entry_minute] == ny(2024, 2, 5, 3, 15)
    z = S.ZONE * s.adr
    assert s.stop_base == pytest.approx(min(2000.5, 2000.0 - z))
    # only finished candles: the setup candle's last minute is 03:14
    assert bars["minute_utc"][s.candle_close_minute] == ny(2024, 2, 5, 3, 14)

    c = S.candidates(bars, days, range(2024, 2025), COSTS)
    one_r = [x for x in c[("1R", 0.05)] if x.setup.day == date(2024, 2, 5)]
    assert one_r and one_r[0].trade.exit_reason == "target"
    t = one_r[0].trade
    assert t.target == pytest.approx(t.entry + (t.entry - t.stop))


def fake(day: date, entry: int, exit_bar: int, kind: str = "bounce") -> S.Candidate:
    setup = S.Setup(day, kind, 1, 1.0, frozenset(), 1, entry, 0.0, entry - 1, 1.0, {})
    trade = HoldTrade(day, 1, entry, 1.0, 0.0, 2.0, 0.01, 1.0, "target", 1, exit_bar)
    return S.Candidate(setup, "1R", 0.05, trade)


def test_take_keeps_one_trade_at_a_time_and_two_a_day() -> None:
    d = date(2024, 1, 2)
    cands = [
        fake(d, 10, 50),
        fake(d, 20, 30),  # overlaps the first
        fake(d, 60, 70),
        fake(d, 80, 90),  # third of the day
        fake(d + timedelta(days=1), 2000, 2010, kind="retest"),
    ]
    taken = S.take(cands)
    assert [t.entry_minute for t in taken] == [10, 60, 2000]
    assert [t.entry_minute for t in S.take(cands, kinds=frozenset({"retest"}))] == [
        2000
    ]
    skip_first = S.take(cands, keep=lambda c: c.setup.entry_minute != 10)
    assert [t.entry_minute for t in skip_first] == [20, 60, 2000]
