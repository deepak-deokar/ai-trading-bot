# XAUUSD level breakouts: raw edge first, costs second (rules written before running)

Follows `docs/xauusd-sr-compare.md`, where breakouts at yesterday's high/low and at
swing levels beat random entries (by about $1-1.60 a trade, about 4-5% of the $30
risk) but lost after costs (about $3.50 a trade). Question: **does the raw edge stay
or grow when stops are wider, so costs take a smaller share?**

## Setup (unchanged from round 2)

A finished 15-minute candle (closing 03:00-13:00 New York) opens at or below a level
and closes above its zone (level + 0.05 ADR) in the top half of its range: buy at the
next minute. Mirror for sells. One breakout per level, direction and day. Out by
16:45 New York, touch stops and targets, a minute touching both counts as the stop.

**Levels**: yesterday's high/low; swing levels (hourly turning points, last 10 days,
2+ turns); and both together. These two were picked from round 2's development
results, so the 2023-2024 test below is what guards against that choice.

## Variants (60)

* stop: behind the level (round 2: level - zone - 0.1 ADR, 0.15-0.6 ADR from entry)
  or a fixed distance from the entry of 0.25 / 0.4 / 0.6 / 0.8 x ADR; any stop over
  $30 is skipped (the most a 0.01-lot trade can risk at $30);
* target: 1R / 1.5R / 2R / none (hold to 16:45);
* levels: yesterday / swing / both.

3 x 5 x 4 = 60.

## Step 1: raw edge, no costs (2014-2022)

Trades filled at the **mid price**, no spread, commission or slippage. For each
variant, every setup on its own (no daily cap):

* **raw R** per trade = price gained / stop distance;
* **excess R** = raw R minus the average of hour-matched twins (the same trade at the
  same clock time on a random other day of the same year, stop in the same ADR
  units), 200 runs; gold's long uptrend makes plain buying look good, the twins
  remove that;
* **cost R** per trade = raw R minus R after Equiti cautious costs on the same setup
  (recorded spread + $10/lot commission + $0.05 slippage per fill), so it includes
  stops hit earlier because of the spread.

A variant goes on to step 2 only if **excess R >= 2 x cost R** in both 2014-2020
and 2021-2022, with at least 200 trades over 2014-2022.

## Step 2: costs back in (2014-2022)

For variants that survive step 1, with Equiti cautious costs, every setup on its
own:

* money made on 2014-2020 (also at 2x costs) and on 2021-2022;
* beats >= 99% of 1,000 hour-matched twin runs (after costs).

The chosen variant is the one with the highest net R per trade over 2014-2022.

## Step 3: 2023-2024, looked at once, only if something passes step 2

One trade at a time, at most 2 a day, $30 risk: profitable at Equiti cautious and at
2x costs, at least 60 trades, largest drop under $600, beats >= 99% of 1,000
hour-matched twin runs. The 50%-winners goal is reported separately (wider stops with
1.5R+ targets will usually win under 50%). 2025-2026 are never loaded.

## Expectation written down beforehand

Cost per trade in R is about $0.55 / stop: 11% at $5, 5.5% at $10, 2.75% at $20.
If the raw edge stays near 5% of R with $15-25 stops, step 1 should pass; if it
shrinks as stops widen, breakouts are a dead end.
