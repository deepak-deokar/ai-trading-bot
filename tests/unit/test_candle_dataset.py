from datetime import datetime

import numpy as np
import pytest

from trading_bot.backtesting.candle_dataset import (
    build,
    build_buckets,
    feature_names,
)
from trading_bot.backtesting.news_day import NY
from trading_bot.backtesting.sweep_strategy import build_days


def ny(y: int, mo: int, d: int, h: int, mi: int = 0) -> int:
    return int(datetime(y, mo, d, h, mi, tzinfo=NY).timestamp())


def bars_for(minutes: np.ndarray, mids: np.ndarray) -> dict[str, np.ndarray]:
    bars = {"minute_utc": minutes.astype(np.int64)}
    for side, sign in (("bid", -1), ("ask", 1)):
        for part in ("open", "high", "low", "close"):
            bars[f"{side}_{part}"] = mids + sign * 0.15
    return bars


def test_green_share_counts_five_minute_candles_inside_the_hour() -> None:
    start = ny(2024, 1, 10, 9)
    minutes = start + np.arange(60) * 60
    mids = np.empty(60)
    for b in range(12):  # 8 rising 5-minute candles, then 4 falling
        step = 1.0 if b < 8 else -1.0
        mids[b * 5 : b * 5 + 5] = 2000 + b + step * np.arange(5) * 0.1
    _, bh = build_buckets(bars_for(minutes, mids))
    assert bh.extra["green_share"][0] == pytest.approx(8 / 12)
    assert bh.extra["chop"][0] > 0


def week_of_bars() -> dict[str, np.ndarray]:
    # Sunday 18:00 New York to Friday 17:00, with the daily 17:00-18:00 break
    t, end = ny(2024, 1, 7, 18), ny(2024, 1, 12, 17)
    mins = []
    while t < end:
        if datetime.fromtimestamp(t, NY).hour != 17:
            mins.append(t)
        t += 60
    m = np.array(mins)
    mids = 2000 + np.sin(np.arange(len(m)) / 50.0) * 5
    return bars_for(m, mids)


def weeks_of_bars(n_weeks: int) -> dict[str, np.ndarray]:
    t = ny(2024, 1, 7, 18)
    end = t + (7 * n_weeks - 2) * 86400  # through Friday of the last week
    mins = []
    while t < end:
        local = datetime.fromtimestamp(t, NY)
        if (
            local.hour != 17
            and local.weekday() != 5
            and not (local.weekday() == 6 and local.hour < 18)
            and not (local.weekday() == 4 and local.hour >= 17)
        ):
            mins.append(t)
        t += 60
    m = np.array(mins)
    return bars_for(m, 2000 + np.sin(np.arange(len(m)) / 50.0) * 5)


def test_rows_use_finished_candles_and_respect_the_1645_exit() -> None:
    bars = weeks_of_bars(6)
    days = build_days(bars)
    rows = build(bars, days, range(2024, 2025))
    assert len(rows.day) > 0 and rows.x.shape[1] == len(feature_names())
    names = feature_names()
    for i in np.flatnonzero(rows.hour == 15)[:3]:
        assert rows.label[240][i] == -1 and rows.label[120][i] == -1
        assert rows.label[60][i] in (0, 1)  # 16:00 end is allowed
    for i in np.flatnonzero(rows.hour == 14)[:3]:
        assert rows.label[120][i] in (0, 1) and rows.label[240][i] == -1
    # the newest 5-minute candle closes at the minute just before the decision
    i = int(np.flatnonzero(rows.hour == 10)[0])
    s = int(rows.entry_minute[i])
    mids_close = (bars["bid_close"] + bars["ask_close"]) / 2
    mids_open = (bars["bid_open"] + bars["ask_open"]) / 2
    expect = (mids_close[s - 1] - mids_open[s]) / rows.adr[i]
    assert rows.x[i, names.index("m5_1_dist")] == pytest.approx(expect)


def test_last_24_traded_candles_skip_the_daily_break() -> None:
    from trading_bot.backtesting.candle_dataset import _window

    bars = week_of_bars()
    b5, _ = build_buckets(bars)
    t = ny(2024, 1, 9, 18)  # just after the daily break
    idx = _window(b5, t // 300 - 1, 24)
    assert idx is not None
    last = datetime.fromtimestamp(int(b5.ids[idx[-1]]) * 300, NY)
    assert (last.hour, last.minute) == (16, 55)  # the break is skipped
    assert len(idx) == 24
