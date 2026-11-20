"""Turn hourly GDELT news counts and tone into model inputs at a moment in time.

For a decision time t, only hours that ended at or before t are used. For each
news category (trading_bot.data.gdelt_news.CATEGORIES plus combined ones):

* share_24h: the category's share of all articles in the last 24 hours;
* surge: log of that share against its share over the 7 days before (days 2-8
  back), i.e. whether the topic is suddenly in the news;
* tone_24h: the article-weighted average tone of the category in the last 24 h;
* tone_change: tone_24h minus the category's tone over the 7 days before.

Plus the same tone and volume measures for all news together.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from math import log

import numpy as np

from trading_bot.backtesting.session_window import Array
from trading_bot.data.gdelt_news import CATEGORIES, COMBINED

HOUR = 3600
RECENT_H = 24
BASE_FROM_H, BASE_TO_H = 24 * 8, 24  # baseline window: 8 to 1 days before t
EPS = 1e-4
MIN_COVERAGE = 0.8  # share of hours that must have news data in each window


def news_feature_names() -> list[str]:
    names = ["all_volume_surge", "all_tone_24h", "all_tone_change"]
    for c in [*CATEGORIES, *COMBINED]:
        names += [f"{c}_share", f"{c}_surge", f"{c}_tone", f"{c}_tone_change"]
    return names


@dataclass(frozen=True)
class NewsHours:
    starts: Array  # hour starts, UTC epoch seconds, ascending
    count_cum: dict[str, Array]  # cumulative article counts (leading 0)
    tone_cum: dict[str, Array]  # cumulative sum of tone x count (leading 0)

    @classmethod
    def from_columns(
        cls, hours: Sequence[datetime], data: dict[str, list[float]]
    ) -> NewsHours:
        starts = np.array([int(h.timestamp()) for h in hours], dtype=np.int64)
        count_cum, tone_cum = {}, {}
        for c in ["all", *CATEGORIES, *COMBINED]:
            n = np.nan_to_num(np.array(data[f"n_{c}"], dtype=float))
            tone = np.nan_to_num(np.array(data[f"tone_{c}"], dtype=float))
            count_cum[c] = np.concatenate([[0.0], np.cumsum(n)])
            tone_cum[c] = np.concatenate([[0.0], np.cumsum(n * tone)])
        return cls(starts, count_cum, tone_cum)

    def _span(self, t: int, back_from_h: int, back_to_h: int) -> tuple[int, int]:
        """Index range of hours that start >= t - back_from_h hours and end at
        or before t - back_to_h hours."""
        lo = int(np.searchsorted(self.starts, t - back_from_h * HOUR, side="left"))
        hi = int(
            np.searchsorted(self.starts, t - back_to_h * HOUR - HOUR, side="right")
        )
        return lo, max(lo, hi)

    def window(
        self, c: str, t: int, back_from_h: int, back_to_h: int
    ) -> tuple[float, float]:
        """(article count, average tone) for category c in the window."""
        lo, hi = self._span(t, back_from_h, back_to_h)
        n = float(self.count_cum[c][hi] - self.count_cum[c][lo])
        s = float(self.tone_cum[c][hi] - self.tone_cum[c][lo])
        return n, (s / n if n > 0 else float("nan"))

    def features_at(self, t: int) -> tuple[float, ...] | None:
        """Inputs for decision time t (UTC epoch seconds); None without news."""
        base_hours = BASE_FROM_H - BASE_TO_H
        lo, hi = self._span(t, RECENT_H, 0)
        blo, bhi = self._span(t, BASE_FROM_H, BASE_TO_H)
        if hi - lo < MIN_COVERAGE * RECENT_H or bhi - blo < MIN_COVERAGE * base_hours:
            return None  # too many hours missing to compare fairly
        all_n, all_tone = self.window("all", t, RECENT_H, 0)
        base_n, base_tone = self.window("all", t, BASE_FROM_H, BASE_TO_H)
        if all_n <= 0 or base_n <= 0:
            return None
        out = [
            log((all_n / RECENT_H) / (base_n / base_hours)),
            all_tone,
            all_tone - base_tone,
        ]
        for c in [*CATEGORIES, *COMBINED]:
            n, tone = self.window(c, t, RECENT_H, 0)
            bn, btone = self.window(c, t, BASE_FROM_H, BASE_TO_H)
            share, bshare = n / all_n, bn / base_n
            out += [
                share,
                log((share + EPS) / (bshare + EPS)),
                tone if n > 0 else all_tone,
                (tone if n > 0 else all_tone) - (btone if bn > 0 else base_tone),
            ]
        return tuple(out)


SHORT_H = 3  # "fresh news": the last 3 completed hours


def short_feature_names() -> list[str]:
    return [f"{c}_surge_3h" for c in ["all", *CATEGORIES, *COMBINED]]


def short_features_at(news: NewsHours, t: int) -> tuple[float, ...] | None:
    """Share of each topic in the last 3 hours against the 24 hours before."""
    lo, hi = news._span(t, SHORT_H, 0)
    blo, bhi = news._span(t, SHORT_H + RECENT_H, SHORT_H)
    if hi - lo < SHORT_H or bhi - blo < MIN_COVERAGE * RECENT_H:
        return None
    n3, _ = news.window("all", t, SHORT_H, 0)
    n24, _ = news.window("all", t, SHORT_H + RECENT_H, SHORT_H)
    if n3 <= 0 or n24 <= 0:
        return None
    out = [log((n3 / SHORT_H) / (n24 / RECENT_H))]
    for c in [*CATEGORIES, *COMBINED]:
        a, _ = news.window(c, t, SHORT_H, 0)
        b, _ = news.window(c, t, SHORT_H + RECENT_H, SHORT_H)
        out.append(log((a / n3 + EPS) / (b / n24 + EPS)))
    return tuple(out)


@dataclass(frozen=True)
class HourlyTable:
    """Any hourly table: cumulative sums of each column (missing = 0)."""

    starts: Array
    cum: dict[str, Array]

    @classmethod
    def from_columns(
        cls,
        hours: Sequence[datetime],
        data: dict[str, list[float]],
        weighted: dict[str, str] | None = None,
    ) -> HourlyTable:
        """`weighted` maps an average column to the count column that weights
        it (stored as '<avg>*w' so averages over windows can be rebuilt)."""
        starts = np.array([int(h.timestamp()) for h in hours], dtype=np.int64)
        cum = {}
        for c, v in data.items():
            cum[c] = np.concatenate([[0.0], np.cumsum(np.nan_to_num(np.array(v)))])
        for avg, w in (weighted or {}).items():
            prod = np.nan_to_num(np.array(data[avg])) * np.nan_to_num(np.array(data[w]))
            cum[f"{avg}*w"] = np.concatenate([[0.0], np.cumsum(prod)])
        return cls(starts, cum)

    def span(self, t: int, back_from_h: int, back_to_h: int) -> tuple[int, int]:
        lo = int(np.searchsorted(self.starts, t - back_from_h * HOUR, side="left"))
        hi = int(
            np.searchsorted(self.starts, t - back_to_h * HOUR - HOUR, side="right")
        )
        return lo, max(lo, hi)

    def total(self, c: str, lo: int, hi: int) -> float:
        return float(self.cum[c][hi] - self.cum[c][lo])


def event_feature_names() -> list[str]:
    from trading_bot.data.gdelt_news import EVENT_GROUPS, EVENT_REGIONS

    names = ["ev_goldstein_24h", "ev_goldstein_change", "ev_volume_surge"]
    groups = [*EVENT_GROUPS] + [x for r in EVENT_REGIONS for x in (r, f"{r}_conflict")]
    for g in groups:
        names += [f"ev_{g}_share", f"ev_{g}_surge", f"ev_{g}_surge_3h"]
    return names


def event_features_at(ev: HourlyTable, t: int) -> tuple[float, ...] | None:
    """Event records: conflict score and each group's share of all mentions,
    last 24 h vs the week before, and last 3 h vs the 24 h before."""
    from trading_bot.data.gdelt_news import EVENT_GROUPS, EVENT_REGIONS

    r = ev.span(t, RECENT_H, 0)
    b = ev.span(t, BASE_FROM_H, BASE_TO_H)
    s = ev.span(t, SHORT_H, 0)
    sb = ev.span(t, SHORT_H + RECENT_H, SHORT_H)
    base_hours = BASE_FROM_H - BASE_TO_H
    if r[1] - r[0] < MIN_COVERAGE * RECENT_H or b[1] - b[0] < MIN_COVERAGE * base_hours:
        return None
    m_r, m_b = ev.total("ev_mentions", *r), ev.total("ev_mentions", *b)
    m_s, m_sb = ev.total("ev_mentions", *s), ev.total("ev_mentions", *sb)
    n_r, n_b = ev.total("ev_n", *r), ev.total("ev_n", *b)
    if min(m_r, m_b, n_r, n_b) <= 0:
        return None
    gold_r = ev.total("ev_goldstein*w", *r) / n_r
    gold_b = ev.total("ev_goldstein*w", *b) / n_b
    out = [gold_r, gold_r - gold_b, log((m_r / RECENT_H) / (m_b / base_hours))]
    groups = [*EVENT_GROUPS] + [x for g in EVENT_REGIONS for x in (g, f"{g}_conflict")]
    for g in groups:
        c = f"ev_{g}"
        share, bshare = ev.total(c, *r) / m_r, ev.total(c, *b) / m_b
        if m_s > 0 and m_sb > 0:
            s3 = log((ev.total(c, *s) / m_s + EPS) / (ev.total(c, *sb) / m_sb + EPS))
        else:
            s3 = 0.0
        out += [share, log((share + EPS) / (bshare + EPS)), s3]
    return tuple(out)


def entity_feature_names() -> list[str]:
    from trading_bot.data.gdelt_news import ORGANISATIONS, PERSONS

    names = []
    for n in [*PERSONS, *ORGANISATIONS]:
        names += [f"{n}_share", f"{n}_surge", f"{n}_tone", f"{n}_tone_change"]
    return names


def entity_features_at(
    ent: HourlyTable, news: NewsHours, t: int
) -> tuple[float, ...] | None:
    """People / organisations: share of all articles, surge vs the week before,
    tone and tone change (falls back to all-news tone when not mentioned)."""
    from trading_bot.data.gdelt_news import ORGANISATIONS, PERSONS

    r = ent.span(t, RECENT_H, 0)
    b = ent.span(t, BASE_FROM_H, BASE_TO_H)
    base_hours = BASE_FROM_H - BASE_TO_H
    if r[1] - r[0] < MIN_COVERAGE * RECENT_H or b[1] - b[0] < MIN_COVERAGE * base_hours:
        return None
    all_r, all_tone = news.window("all", t, RECENT_H, 0)
    all_b, base_tone = news.window("all", t, BASE_FROM_H, BASE_TO_H)
    if all_r <= 0 or all_b <= 0:
        return None
    out: list[float] = []
    for n in [*PERSONS, *ORGANISATIONS]:
        a, bb = ent.total(f"n_{n}", *r), ent.total(f"n_{n}", *b)
        tone = ent.total(f"tone_{n}*w", *r) / a if a > 0 else all_tone
        btone = ent.total(f"tone_{n}*w", *b) / bb if bb > 0 else base_tone
        share, bshare = a / all_r, bb / all_b
        out += [share, log((share + EPS) / (bshare + EPS)), tone, tone - btone]
    return tuple(out)
