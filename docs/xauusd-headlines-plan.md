# XAUUSD gold headlines: does what the news says about gold predict direction? (rules written before running)

Follows `docs/xauusd-news-ml-v2.md`: counting world-news topics predicted *how much*
gold moves in the 08:00-12:00 New York window (rank correlation about +0.27), but not
*which way* (about 49% right). This round reads the actual headlines.

## Data (pulled once, about $13 of BigQuery)

GDELT 2.0 news articles 2015-02-18 to 2024-12-31 that GDELT tagged with a gold theme
(ECON_GOLDPRICE, WB_2936_GOLD) or whose page title mentions gold, bullion or precious
metals. Each article keeps its 15-minute GDELT batch time (GDELT reads articles after
they are published, so this time is at or after publication, so there's no hindsight),
title, tone, source and whether it also has a central-bank theme.
2025-2026 are never queried.

Headlines are cleaned the same way for every day: lower case, HTML entities decoded,
and the same title from the same source counted once per day.

## Daily setup (unchanged from news-ml-v2)

Decision at 08:00 New York; a 1:1 trade with stop and target at half the 20-day
average daily range, closed by 12:00, expensive costs, $30 risk. Buy if P(buy wins)
>= 0.55, sell if <= 0.45, otherwise no trade. Only headlines with a batch time before
08:00 New York that day are used.

## Headline inputs

**Word-list score (fixed now, never changed after a result is seen).** A title is
*up* if it contains any of: rise, rises, rising, rose, gain, gains, gained, jump,
jumps, jumped, surge, surges, surged, soar, soars, soared, rally, rallies, rallied,
climb, climbs, climbed, advance, advances, record high, all-time high, highest,
rebound, rebounds, rebounded, safe haven, safe-haven, buying, demand, up.
It is *down* if it contains any of: fall, falls, falling, fell, drop, drops, dropped,
slip, slips, slipped, slide, slides, slid, decline, declines, declined, tumble,
tumbles, tumbled, plunge, plunges, plunged, sink, sinks, sank, slump, slumps,
slumped, retreat, retreats, retreated, lowest, losses, lose, loses, weaker, selling,
outflows, down.
Whole words only. A title with both or neither counts as neither.

Per day, for the last 24 h and the last 3 h before 08:00:
* number of gold headlines (log, and relative to the 7 days before);
* share of up titles, share of down titles, and up minus down;
* average GDELT tone of gold articles;
* number and tone of gold articles that also have a central-bank theme.

**Learned headline model (the AI part).** All gold titles from the 24 h before 08:00
are joined into one document per day. Words and two-word phrases seen on at least 20
days of 2015-2020 are weighted by TF-IDF (vocabulary fitted on 2015-2020 only), and a
logistic regression learns which words come before gold rising in the window.
Strength chosen from 0.01 / 0.1 / 1 / 10.

## Candidates, all tuned the same way

1. **v2 news** (reference): news-ml-v2's best set, refitted unchanged.
2. **news + headline words**: v2 news inputs plus the word-list inputs above,
   gradient-boosted trees with the same grid as news-ml-v2.
3. **headline text**: the learned headline model on its own.
4. **headline words only**: the word-list inputs alone, gradient-boosted trees.

Every setting is fitted on 2015-03..2020 and scored on 2021-2022 by log loss
(0.693 = a coin flip). The candidate with the lowest 2021-2022 log loss wins. It is
refitted on 2015-03..2022 and looked at **once** on 2023-2024. This is the third look
at 2023-2024 for news models, and the report says so.

A diagnostic with no model is also reported on 2015-2022 only: how often gold went
up in the window on days the 24 h up-minus-down share was in its top vs bottom fifth.

## Pass (2023-2024)

* 2021-2022 log loss below 0.693;
* profitable after expensive costs and still not losing at 2x costs;
* at least 50% winning trades and at least 60 trades;
* better than always buying and than the v2 news reference.

The 2023-2024 move-size check (R-squared, rank correlation) is reported for
candidate 2 against v2 news.

## Expectation written down beforehand

Most gold headlines describe a move that has already happened ("gold rises as ..."),
and price inputs already contain that. If the headline inputs only repeat past
moves, direction accuracy will stay near 50%. Any real gain is more likely to come
from cause words (central-bank buying, safe-haven demand) than from move words.
