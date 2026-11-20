"""One row per trading day (08:00 New York) with gold, market and news inputs.

Shared by the news-model studies. Inputs sets:
  base  daily_model.FEATURES (gold, US dollar, yields, S&P 500, VIX, calendar)
  news  base + 24 h news topics (news_features.news_feature_names)
  full  news + 3 h fresh news + event records + people/organisations
Targets: ``label`` (a 1:1 buy wins by 12:00) and ``move`` (08:00-12:00 mid
high - low in units of the 20-day average daily range).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from trading_bot.backtesting.daily_model import FEATURES as BASE_FEATURES
from trading_bot.backtesting.daily_model import DayRow, build_rows
from trading_bot.backtesting.news_day import load_events
from trading_bot.backtesting.news_features import (
    HourlyTable,
    NewsHours,
    entity_feature_names,
    entity_features_at,
    event_feature_names,
    event_features_at,
    news_feature_names,
    short_feature_names,
    short_features_at,
)
from trading_bot.backtesting.session_window import Array
from trading_bot.backtesting.sweep_strategy import TradingDay
from trading_bot.data.gdelt_news import (
    ENTITIES_CSV,
    EVENTS_CSV,
    ORGANISATIONS,
    PERSONS,
    load_hourly,
    load_table,
)
from trading_bot.data.macro_daily import load as load_macro

FIRST_DAY = date(2015, 3, 2)  # GDELT starts 2015-02-18; 8 days of news history


@dataclass(frozen=True)
class NewsDataset:
    rows: list[DayRow]
    x: dict[str, Array]  # input set name -> matrix
    names: dict[str, list[str]]
    label: Array
    move: Array
    year: Array


def feature_names() -> dict[str, list[str]]:
    base = list(BASE_FEATURES)
    news = base + news_feature_names()
    full = news + short_feature_names() + event_feature_names() + entity_feature_names()
    return {"base": base, "news": news, "full": full}


def build_dataset(
    bars: dict[str, Array], days: Sequence[TradingDay], years: range
) -> NewsDataset:
    rows_all = build_rows(
        bars, days, load_macro(), load_events(one_per_day=False), years
    )
    news = NewsHours.from_columns(*load_hourly())
    eh, ed = load_table(EVENTS_CSV)
    events = HourlyTable.from_columns(eh, ed, weighted={"ev_goldstein": "ev_n"})
    nh, nd = load_table(ENTITIES_CSV)
    ents = HourlyTable.from_columns(
        nh, nd, weighted={f"tone_{n}": f"n_{n}" for n in [*PERSONS, *ORGANISATIONS]}
    )
    m = bars["minute_utc"]
    mh = (bars["bid_high"] + bars["ask_high"]) / 2
    ml = (bars["bid_low"] + bars["ask_low"]) / 2
    rows: list[DayRow] = []
    xb, xn, xf, move = [], [], [], []
    for r in rows_all:
        if r.day < FIRST_DAY:
            continue
        t = int(m[r.entry_minute])
        f24 = news.features_at(t)
        f3 = short_features_at(news, t)
        fe = event_features_at(events, t)
        fp = entity_features_at(ents, news, t)
        if f24 is None or f3 is None or fe is None or fp is None:
            continue
        rows.append(r)
        xb.append(r.features)
        xn.append(r.features + f24)
        xf.append(r.features + f24 + f3 + fe + fp)
        sl = slice(r.entry_minute, r.last_minute + 1)
        move.append(float(mh[sl].max() - ml[sl].min()) / (2 * r.risk))
    return NewsDataset(
        rows=rows,
        x={"base": np.array(xb), "news": np.array(xn), "full": np.array(xf)},
        names=feature_names(),
        label=np.array([r.label for r in rows]),
        move=np.array(move),
        year=np.array([r.year for r in rows]),
    )
