# XAUUSD Asia-session buy, especially after gold has fallen (rules written before running)

Follows `docs/xauusd-regimes.md` (descriptive): the 18:00-03:00 New York session rose
in 9 of 11 years, most strongly after a 20-day fall (+0.030 ADR, t 3.3, 56% up), and
peer-reviewed work finds gold's return comes overnight/in Asian hours
(Blose, Gondhalekar & Kort 2018). That finding was seen on all of 2014-2024, so the
2023-2024 test below is the only clean check; the 2021-2022 check is not fully clean.

## Trade

* Buy only, one trade a day, inside the New York trading day (17:00-17:00), never
  overnight past the London open.
* Entry at the first minute at or after the entry time; exit at the exit time (time
  exit), or earlier at the stop. No target.
* Stop k x ADR below the entry fill (ADR = average daily high-low of the 20 days
  before). Size: $30 risk on $3,000; skipped if the stop needs more than the $30 a
  0.01 lot can risk.
* Costs: Equiti cautious (recorded spread + $10/lot commission + $0.05 slippage per
  fill), and 2x as a stress test. The recorded spread is nearly flat in 2014-2018, so
  the widening at the 18:00 reopen is likely understated there; the 19:00 and 20:00
  entries are included partly for that reason.

## Variants (36)

* filter (known at the 17:00 close): **none** / **20-day fall** (20-day change in ADR
  units in the bottom third, cut point fixed from 2014-2020 only) / **below the
  50-day average**;
* entry 18:00 / 19:00 / 20:00 New York;
* exit 02:00 / 03:00 New York;
* stop 0.5 / 0.75 x ADR.

## Baseline (random-time twins, 1,000 runs)

For every real trade, a twin buys on the **same day** at a random half-hour mark
between 18:00 and (16:45 - holding time), holding for the same time with the same
ADR stop. This asks: is the Asia window better than buying at any other time of the
same day (so gold's long rise is removed)? "Beats" = share of the 1,000 runs whose
average net $ per trade is below the real average.

## Step 1: choose (2014-2020), confirm (2021-2022)

A variant passes if:
* net profit on 2014-2020 at Equiti cautious **and** at 2x costs;
* net profit on 2021-2022 at Equiti cautious;
* at least 200 trades over 2014-2022;
* beats >= 99% of twin runs on 2014-2022 (after costs).

How many of the 36 beat the 95th percentile is reported against the about 1.8
expected by luck. Of passing variants, the one with the highest 2014-2020 net $ per
trade is chosen.

## Step 2: 2023-2024, looked at once, only for the chosen variant

Profitable at Equiti cautious and at 2x costs, at least 60 trades, largest drop under
$600, beats >= 99% of twin runs. The share of winning trades is reported against the
50% goal. 2025-2026 are never loaded.

## Expectation written down beforehand

The raw drift is about $0.6-1.0 per ounce on filtered days against about $0.55-0.70
of costs. A time exit with a wide stop keeps most of the drift, so step 1 may pass
narrowly at 1x; 2x costs is the likely failure point.
