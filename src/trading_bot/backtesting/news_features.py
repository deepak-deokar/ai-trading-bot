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
