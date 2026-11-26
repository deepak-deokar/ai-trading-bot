"""Gold headline inputs (rules: docs/xauusd-headlines-plan.md).

Reads the GDELT gold-headline file, cleans titles, marks each as up / down /
neither with fixed word lists, and answers "what did gold headlines say before
time t" with no look-ahead: only articles whose batch time is strictly before t.
"""

from __future__ import annotations

import csv
import html
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from trading_bot.backtesting.session_window import Array
from trading_bot.data.gdelt_news import GOLD_TITLE, HEADLINES_CSV, LAST_DAY

UP_WORDS = (
    "rise rises rising rose gain gains gained jump jumps jumped surge surges surged "
    "soar soars soared rally rallies rallied climb climbs climbed advance advances "
    "highest rebound rebounds rebounded buying demand up"
).split() + ["record high", "all-time high", "safe haven", "safe-haven"]
DOWN_WORDS = (
    "fall falls falling fell drop drops dropped slip slips slipped slide slides slid "
    "decline declines declined tumble tumbles tumbled plunge plunges plunged sink "
    "sinks sank slump slumps slumped retreat retreats retreated lowest losses lose "
    "loses weaker selling outflows down"
).split()


def _words(ws: list[str]) -> re.Pattern[str]:
    return re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, ws)) + r")(?![\w-])")


UP_RE, DOWN_RE = _words(UP_WORDS), _words(DOWN_WORDS)
GOLD_RE = re.compile(GOLD_TITLE)
FIRST_TITLE_DAY = "2019-09-22"  # GDELT page titles start here
HOUR, DAY = 3600, 86400


def clean(title: str) -> str:
    return " ".join(html.unescape(title).lower().split())


def mood(title: str) -> int:
    """+1 up, -1 down, 0 both or neither (title already cleaned)."""
    up, down = bool(UP_RE.search(title)), bool(DOWN_RE.search(title))
    return int(up) - int(down)


@dataclass(frozen=True)
class Headlines:
    ts: Array  # unix seconds, sorted
    titles: list[str]
    mood: Array  # +1 / -1 / 0
    tone: Array  # nan if missing
    cb: Array  # 1 if also a central-bank theme

    @classmethod
    def load(cls, path: Path = HEADLINES_CSV) -> Headlines:
        seen: set[tuple[str, str]] = set()
        rows = []
        with path.open(newline="") as fh:
            for r in csv.DictReader(fh):
                when = datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
                if when.date() > LAST_DAY:
                    raise ValueError("headlines must stop at 2024-12-31")
                t = clean(r["title"])
                if not GOLD_RE.search(t):  # amendment 1: title must mention gold
                    continue
                key = (r["ts"][:10], t)
                if key in seen:
                    continue
                seen.add(key)
                tone = float(r["tone"]) if r["tone"] else float("nan")
                rows.append((int(when.timestamp()), t, tone, int(r["cb_theme"])))
        rows.sort(key=lambda x: x[0])
        return cls.of(rows)

    @classmethod
    def of(cls, rows: list[tuple[int, str, float, int]]) -> Headlines:
        titles = [r[1] for r in rows]
        return cls(
            ts=np.array([r[0] for r in rows], dtype=np.int64),
            titles=titles,
            mood=np.array([mood(t) for t in titles], dtype=np.int64),
            tone=np.array([r[2] for r in rows], dtype=float),
            cb=np.array([r[3] for r in rows], dtype=np.int64),
        )

    def window(self, start: int, end: int) -> slice:
        """Articles with start <= ts < end."""
        a = int(np.searchsorted(self.ts, start, side="left"))
        b = int(np.searchsorted(self.ts, end, side="left"))
        return slice(a, b)

    def text_before(self, t: int, hours: int = 24) -> str:
        sl = self.window(t - hours * HOUR, t)
        return " | ".join(self.titles[sl])

    def _block(self, sl: slice) -> list[float]:
        n = sl.stop - sl.start
        m = self.mood[sl]
        tone = self.tone[sl]
        cb = self.cb[sl] == 1
        up = float(np.mean(m == 1)) if n else 0.0
        down = float(np.mean(m == -1)) if n else 0.0
        good = ~np.isnan(tone)
        avg_tone = float(tone[good].mean()) if good.any() else 0.0
        cb_good = cb & good
        cb_tone = float(tone[cb_good].mean()) if cb_good.any() else 0.0
        return [
            float(np.log1p(n)),
            up,
            down,
            up - down,
            avg_tone,
            float(np.log1p(cb.sum())),
            cb_tone,
        ]

    def features_at(self, t: int) -> list[float]:
        last24 = self.window(t - DAY, t)
        last3 = self.window(t - 3 * HOUR, t)
        week = self.window(t - 8 * DAY, t - DAY)
        n24 = last24.stop - last24.start
        per_day_week = (week.stop - week.start) / 7
        rel = float(np.log1p(n24) - np.log1p(per_day_week))
        return [*self._block(last24), rel, *self._block(last3)]


BLOCK = (
    "count_log",
    "up_share",
    "down_share",
    "up_minus_down",
    "tone",
    "cb_log",
    "cb_tone",
)


def feature_names() -> list[str]:
    return (
        [f"hl24_{b}" for b in BLOCK]
        + ["hl24_count_vs_week"]
        + [f"hl3_{b}" for b in BLOCK]
    )
