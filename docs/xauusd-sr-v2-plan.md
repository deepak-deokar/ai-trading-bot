# XAUUSD support and resistance, round 2: rules written before running

Written and committed **before** any of these numbers were computed. Round 1
(`docs/xauusd-sr.md`) found no option that made money; this round asks a narrower
question: **do any of the levels carry information at all, compared with entering at
a random time?**

## What changed from round 1, and why

* **No AI filter this round.** A filter can only help a setup that already has an
  edge; round 1's chosen option had 14 trades in its validation years. The AI comes
  back once a base setup beats the random baseline.
* **Everything is scaled by ADR** (20-day average daily range) so 2014 and 2024 are
  measured the same way:
  * stop distance must be 0.15-0.6 x ADR (was $5-$30); still skipped above $30, the
    most a 0.01-lot trade can risk at $30;
  * round numbers: the step is whichever of $10 / $25 / $50 / $100 is closest to one
    ADR (was always $50).
* **Each level type is tested on its own**: yesterday's high/low, last week's
  high/low, hourly swing levels, round numbers, the Asian range. "All levels
  together" is shown for reference only and cannot be chosen.
* **No room filter and no "next level" target**: targets are 1R and 1.5R only. Fewer
  moving parts, more trades, and the random baseline can copy the trade exactly.
* **One stop buffer**: 0.1 x ADR beyond the stop base (round 1 tried 0.05 and 0.15).
* **New continuation setup, "breakout"** (rules fixed here, before any result):
  a finished 15-minute candle opens at or below the level and closes above the zone
  (level + 0.05 ADR) in the top half of its range -> buy at the next minute. Stop at
  level - zone - buffer. Mirror for sells. One breakout per level, direction and day.
* Bounce and retest rules are unchanged from round 1 (see
  `src/trading_bot/backtesting/sr_strategy.py`).

## Look-ahead check (done)

Swing levels use hourly candles from the 10 trading days **before** the day starts,
and a turning point needs 3 finished hourly candles after it, all before the day's
first minute. Yesterday's and last week's levels, ADR and the round-number step use
only earlier days. Asian levels are used only after 02:00 New York. Setups read only
finished 15-minute candles and enter on the next minute.

## The random-entry baseline

For every real trade, a "twin" trade on the **same day**, in the **same direction**,
with the **same stop distance in dollars** and the **same target (1R or 1.5R)**, but
entering at a random 15-minute mark between 03:00 and 13:00 New York. Same costs,
same touch stops, out by 16:45. Repeated 100 times with different random times. The
real setup's average dollars per trade is compared with the 100 twin averages.

## Combinations

5 level types x 3 setups (bounce, retest, breakout) x 2 targets (1R, 1.5R) = 30.

## Choosing (2014-2022 only)

A combination passes development if **all** hold:

1. its average $ per trade over 2014-2022 beats at least 95 of the 100 twin runs;
2. it makes money (Equiti cautious costs) on 2014-2020 **and** on 2021-2022, counted
   per setup with no daily cap;
3. at least 200 trades over 2014-2022.

With 30 combinations, about 1-2 could beat 95% of twins by luck alone, so rules 2-3
must also hold. If several pass, the one with the highest twin percentile (then the
highest average) is chosen.

## Test (2023-2024, looked at once, only if something passes)

The chosen combination, with one trade at a time and at most 2 a day, $30 risk:

* profitable at Equiti cautious costs and at 2x costs;
* at least 60 trades; largest drop under $600;
* average $ per trade beats at least 95 of 100 twin runs on 2023-2024.

The 50%-winners goal is reported separately. If nothing passes development,
2023-2024 is not looked at. 2025-2026 are never loaded.

## Amendment after the first run (baseline fix)

The first run's twins could enter at any mark 03:00-13:00, including **before** the
real signal, while keeping the signal's direction. A breakout twin entering before
the breakout trades the very move that created the signal, so it peeks ahead (the
breakout twins showed a profit; every real setup scored below its twins). Fixed:
a twin enters at a random 15-minute mark **after** the real entry, up to 13:00, and
is dropped if there is none. Nothing else changed: same combinations, same pass
rules, same costs. The first run's numbers are not used for any choice.

## Amendment 2: stricter baseline and a raw "what happens at a level" measure

Added after the second run, on outside review. All of these make passing harder or
add measurements; none loosens a rule.

* **Two baselines, 1,000 runs each.**
  * *After-signal twins* (as in amendment 1): same day, a random later 15-minute mark.
  * *Hour-matched twins*: the same clock time as the real entry, on a random other
    trading day of the same year; same direction and target, stop distance scaled
    by that day's ADR (same stop in ADR units). This gives the twins exactly the
    real trades' time-of-day mix (London and New York opens), with no peeking,
    because the twin's day did not produce the signal.
* **Development pass** now needs: beats >= 99% of hour-matched runs **and** >= 95%
  of after-signal runs, money on 2014-2020 and 2021-2022, >= 200 trades.
* **Multiple testing**: the report counts how many of the 30 combinations clear
  the 95th percentile of each baseline, next to the ~1.5 expected by luck (the
  combinations share levels and price paths, so luck can move several together).
* **Intrabar ties**: a minute that touches both stop and target counts as a stop
  (already so in the code; now covered by a test).
* **Spreads**: the data's 2014-2018 spread is almost constant ($0.51 in 2014,
  $0.35 in 2015-2018, little widening at news), so those years' costs are likely too
  low. The 2x-cost test stays; any pass must also survive it on 2014-2020.
* **After-touch behaviour, no stops or targets.** For each level type, the first
  time each level is touched (03:00-13:00, price arriving from outside the zone):
  * did price first move 0.25 ADR beyond the zone back on the side it came from
    (**held**) or through to the other side (**broke**), within 60 minutes, or
    neither;
  * the move after 60 minutes in ADR units, positive = back on the approach side.
  The same is measured on **fake levels** (each real level moved 0.3-0.7 ADR up or
  down at random), so the level's effect is the difference from the fake levels.
