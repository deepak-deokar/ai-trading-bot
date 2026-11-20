from datetime import date, time

import numpy as np
import pytest

from trading_bot.backtesting.news_day import NewsEvent
from trading_bot.backtesting.news_model import (
    FEATURES,
    EventRow,
    fit_logistic,
    label_for,
    walk_forward,
)


def test_label_first_touch_wins() -> None:
    hi = np.array([101.0, 103.0, 101.0])
    lo = np.array([99.0, 99.0, 96.0])
    assert label_for(hi, lo, 100.0, entry=100.0, risk=3.0) == 1  # +3 at minute 1
    assert label_for(hi, lo, 100.0, entry=100.0, risk=4.0) == 0  # -4 at minute 2


def test_label_same_minute_counts_against_the_buy_and_time_limit_uses_close() -> None:
    assert label_for(np.array([104.0]), np.array([96.0]), 100.0, 100.0, 3.0) == 0
    flat_hi, flat_lo = np.array([101.0, 101.0]), np.array([99.0, 99.0])
    assert label_for(flat_hi, flat_lo, 100.5, 100.0, 5.0) == 1
    assert label_for(flat_hi, flat_lo, 99.5, 100.0, 5.0) == 0


def test_logistic_learns_a_clear_signal() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(400, 2))
    y = (x[:, 0] > 0).astype(float)
    m = fit_logistic(x, y, l2=1.0)
    assert m.weights[0] > 2 and abs(m.weights[1]) < 0.5
    acc = np.mean((m.proba(x) > 0.5) == (y == 1))
    assert acc > 0.95


def make_rows() -> list[EventRow]:
    rng = np.random.default_rng(1)
    rows = []
    for year in range(2014, 2019):
        for i in range(20):
            ev = NewsEvent(date(year, 1 + i % 12, 1 + i), "cpi", time(8, 30))
            f = tuple(float(v) for v in rng.normal(size=len(FEATURES)))
            rows.append(EventRow(ev, 0, 1, 100.0, 1.0, f, int(f[2] > 0)))
    return rows


def test_walk_forward_trains_only_on_earlier_years() -> None:
    rows = make_rows()
    preds = walk_forward(rows, first_test_year=2016)
    years = {rows[i].event.day.year for i in preds}
    assert years == {2016, 2017, 2018}
    # the 2016 model saw 40 rows (2014-2015); refitting on them gives the same model
    i2016 = next(i for i in preds if rows[i].event.day.year == 2016)
    train = [r for r in rows if r.event.day.year < 2016]
    m = fit_logistic(
        np.array([r.features for r in train]),
        np.array([r.label for r in train], dtype=float),
    )
    assert preds[i2016][1].weights == pytest.approx(m.weights)
