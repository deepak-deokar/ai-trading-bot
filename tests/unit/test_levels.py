from datetime import date

import numpy as np
import pytest

from trading_bot.backtesting.levels import Level, key_levels, protected, room
from trading_bot.backtesting.sweep_strategy import TradingDay


def test_key_levels_use_yesterday_and_today_so_far() -> None:
    mids = np.array([2000.0, 2005.0, 1995.0, 2010.0])  # minute 3 is after `until`
    bars = {f"{s}_{p}": mids for s in ("bid", "ask") for p in ("high", "low")}
    prev = TradingDay(date(2024, 1, 9), 0, 0, 2000.0, 2020.0, 1990.0, 2010.0)
    today = TradingDay(date(2024, 1, 10), 0, 4, 0, 0, 0, 0)
    lv = {x.name: x.price for x in key_levels(bars, [prev, today], 1, until=3)}
    assert lv == {
        "Yesterday's high": 2020.0,
        "Yesterday's low": 1990.0,
        "Today's high so far": 2005.0,
        "Today's low so far": 1995.0,
    }
    with pytest.raises(ValueError):
        key_levels(bars, [prev, today], 0, until=3)


def test_room_and_protection() -> None:
    lv = [Level(2010.0, "r"), Level(1990.0, "s"), Level(2004.0, "r2")]
    assert room(lv, 2000.0, 1) == 4.0
    assert room(lv, 2000.0, -1) == 10.0
    assert room(lv, 2020.0, 1) is None
    assert protected(lv, 2000.0, 1985.0)  # support at 1990 between entry and stop
    assert not protected(lv, 2000.0, 1995.0)
