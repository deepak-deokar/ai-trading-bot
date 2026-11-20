from datetime import UTC, datetime, timedelta
from math import log

import pytest

from trading_bot.backtesting.news_features import NewsHours, news_feature_names
from trading_bot.data.gdelt_news import CATEGORIES, COMBINED, columns

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def hours_data(n_hours: int, war_from: int) -> NewsHours:
    """100 articles an hour with tone -1; war: 5/hour (tone -3), 20/hour from
    `war_from` (tone -6)."""
    hours = [T0 + timedelta(hours=h) for h in range(n_hours)]
    data: dict[str, list[float]] = {c: [] for c in columns()[1:]}
    for h in range(n_hours):
        for c in ["all", *CATEGORIES, *COMBINED]:
            n, tone = (100.0, -1.0) if c == "all" else (0.0, float("nan"))
            if c == "war_conflict":
                n, tone = (20.0, -6.0) if h >= war_from else (5.0, -3.0)
            data[f"n_{c}"].append(n)
            data[f"tone_{c}"].append(tone)
    return NewsHours.from_columns(hours, data)


def at(hour: int, minute: int = 0) -> int:
    return int((T0 + timedelta(hours=hour, minutes=minute)).timestamp())


def test_war_surge_and_tone() -> None:
    news = hours_data(24 * 10, war_from=24 * 9)
    f = dict(
        zip(news_feature_names(), news.features_at(at(24 * 10)) or (), strict=True)
    )
    assert f["war_conflict_share"] == pytest.approx(0.20)
    assert f["war_conflict_surge"] == pytest.approx(log((0.20 + 1e-4) / (0.05 + 1e-4)))
    assert f["war_conflict_tone"] == pytest.approx(-6.0)
    assert f["war_conflict_tone_change"] == pytest.approx(-3.0)
    assert f["all_tone_24h"] == pytest.approx(-1.0)
    assert f["gold_share"] == 0.0


def test_an_unfinished_hour_is_not_used() -> None:
    # war jumps in the hour starting at 230; at 230:59 that hour has not ended
    news = hours_data(24 * 10, war_from=230)
    names = news_feature_names()
    before = dict(zip(names, news.features_at(at(230, 59)) or (), strict=True))
    after = dict(zip(names, news.features_at(at(231)) or (), strict=True))
    assert before["war_conflict_share"] == pytest.approx(0.05)
    assert after["war_conflict_share"] > 0.05


def test_no_history_gives_none() -> None:
    news = hours_data(30, war_from=0)
    assert news.features_at(at(30)) is None  # no baseline week yet


def test_event_features_conflict_share_and_goldstein() -> None:
    from trading_bot.backtesting.news_features import (
        HourlyTable,
        event_feature_names,
        event_features_at,
    )
    from trading_bot.data.gdelt_news import EVENT_GROUPS, EVENT_REGIONS

    n_hours = 24 * 10
    cols = ["ev_n", "ev_mentions", "ev_goldstein"]
    cols += [f"ev_{g}" for g in EVENT_GROUPS]
    cols += [f"ev_{r}{s}" for r in EVENT_REGIONS for s in ("", "_conflict")]
    data: dict[str, list[float]] = {c: [] for c in cols}
    for h in range(n_hours):
        late = h >= 24 * 9
        for c in cols:
            data[c].append(0.0)
        data["ev_n"][-1] = 10.0
        data["ev_mentions"][-1] = 100.0
        data["ev_goldstein"][-1] = -5.0 if late else 1.0
        data["ev_fighting"][-1] = 40.0 if late else 10.0
    hours = [T0 + timedelta(hours=h) for h in range(n_hours)]
    ev = HourlyTable.from_columns(hours, data, weighted={"ev_goldstein": "ev_n"})
    f = dict(
        zip(
            event_feature_names(), event_features_at(ev, at(n_hours)) or (), strict=True
        )
    )
    assert f["ev_goldstein_24h"] == pytest.approx(-5.0)
    assert f["ev_goldstein_change"] == pytest.approx(-6.0)
    assert f["ev_fighting_share"] == pytest.approx(0.40)
    assert f["ev_fighting_surge"] == pytest.approx(log((0.40 + 1e-4) / (0.10 + 1e-4)))


def test_extra_queries_refuse_dates_after_2024() -> None:
    from datetime import date

    from trading_bot.data.gdelt_news import entities_hourly_sql, events_hourly_sql

    with pytest.raises(ValueError):
        events_hourly_sql(date(2024, 12, 1), date(2025, 1, 2))
    with pytest.raises(ValueError):
        entities_hourly_sql(date(2015, 1, 1), date(2015, 2, 1))
    assert "DATEADDED" in events_hourly_sql(date(2020, 1, 1), date(2020, 1, 2))
