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
