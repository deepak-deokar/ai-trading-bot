# XAUUSD support and resistance, round 2: each level against random entries

Rules fixed before running: [docs/xauusd-sr-v2-plan.md](xauusd-sr-v2-plan.md) (with amendments 1 and 2). Costs: xauusd_costs_equiti. $30 risk per trade. Development years 2014-2022, every setup counted on its own (no daily cap).

## 1. What price does after touching a level (no stops, no targets)

First touch of each level per day, 03:00-13:00 New York, price arriving from outside the zone. **Held** = within 60 minutes price first went 0.25 ADR beyond the zone back on the side it came from; **broke** = it went 0.25 ADR through to the other side first. **Move** = where price was 60 minutes later, in ADR units, positive = back on the approach side. **Fake** levels are the same levels moved 0.3-0.7 ADR up or down at random: the level's own effect is the gap between real and fake.

| Level | Touches | Held | Broke | Neither | Move (mean ± se) | Fake held | Fake broke | Fake move |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| prev_day | 1881 | 12% | 11% | 76% | +0.033 ± 0.005 | 13% | 9% | +0.050 |
| prev_week | 862 | 14% | 16% | 70% | +0.010 ± 0.008 | 14% | 10% | +0.052 |
| swing | 5849 | 14% | 10% | 76% | +0.044 ± 0.003 | 14% | 11% | +0.042 |
| round | 2331 | 15% | 14% | 71% | +0.035 ± 0.005 | 15% | 11% | +0.044 |
| asia | 3240 | 9% | 6% | 85% | +0.042 ± 0.003 | 15% | 11% | +0.039 |
| all | 14047 | 13% | 10% | 77% | +0.039 ± 0.002 | 14% | 10% | +0.045 |

## 2. Setups against random entries

Two baselines, 1,000 runs each. **After** twin: the same trade (direction, stop distance, target) entered at a random later 15-minute mark on the same day. **Hour** twin: the same trade at the same clock time on a random other day of the same year, stop in the same ADR units. **Beats** = share of runs the real setup's average $ per trade beat. Passing needs hour >= 99%, after >= 95%, money in 2014-20 (also at 2x costs) and 2021-22, 200+ trades.

| Level | Setup | Target | Trades | Win | $/trade | After avg | Beats | Hour avg | Beats | 2014-20 | 2014-20 2x | 2021-22 | Pass |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| swing | breakout | 1.5R | 4398 | 40% | -2.36 | -3.62 | 100.0% | -3.53 | 99.7% | -$9,526 | -$13,726 | -$833 | no |
| swing | breakout | 1.0R | 4398 | 46% | -2.64 | -3.52 | 100.0% | -3.57 | 99.6% | -$9,342 | -$13,446 | -$2,254 | no |
| prev_day | breakout | 1.0R | 1470 | 47% | -2.11 | -3.45 | 99.9% | -3.49 | 98.8% | -$1,767 | -$3,309 | -$1,337 | no |
| prev_day | breakout | 1.5R | 1470 | 41% | -2.05 | -3.68 | 100.0% | -3.42 | 97.6% | -$2,268 | -$3,740 | -$751 | no |
| swing | retest | 1.0R | 2351 | 44% | -3.00 | -3.43 | 90.8% | -3.47 | 83.3% | -$5,941 | -$8,164 | -$1,102 | no |
| prev_day | retest | 1.0R | 767 | 46% | -2.62 | -2.82 | 65.0% | -3.36 | 80.6% | -$1,464 | -$2,110 | -$547 | no |
| prev_week | breakout | 1.5R | 684 | 40% | -2.71 | -3.46 | 89.2% | -3.43 | 75.5% | -$1,155 | -$1,849 | -$697 | no |
| swing | retest | 1.5R | 2351 | 39% | -3.06 | -3.46 | 88.4% | -3.41 | 73.4% | -$6,125 | -$8,148 | -$1,077 | no |
| prev_day | retest | 1.5R | 767 | 41% | -2.88 | -2.88 | 50.6% | -3.37 | 71.7% | -$1,705 | -$2,368 | -$506 | no |
| prev_week | retest | 1.5R | 357 | 40% | -3.00 | -3.05 | 51.7% | -3.40 | 62.1% | -$804 | -$1,160 | -$269 | no |
| prev_day | bounce | 1.5R | 1423 | 40% | -3.04 | -3.13 | 58.6% | -3.25 | 59.9% | -$3,331 | -$4,700 | -$996 | no |
| round | breakout | 1.5R | 1814 | 39% | -3.33 | -3.88 | 92.5% | -3.45 | 58.8% | -$5,215 | -$7,090 | -$819 | no |
| round | breakout | 1.0R | 1814 | 44% | -3.39 | -3.74 | 80.3% | -3.46 | 55.4% | -$5,313 | -$7,089 | -$831 | no |
| prev_week | breakout | 1.0R | 684 | 45% | -3.52 | -3.55 | 51.9% | -3.43 | 46.1% | -$1,664 | -$2,194 | -$743 | no |
| asia | retest | 1.5R | 1557 | 38% | -3.45 | -3.17 | 26.4% | -3.37 | 45.5% | -$4,086 | -$5,403 | -$1,280 | no |
| swing | bounce | 1.0R | 4673 | 44% | -3.38 | -3.49 | 69.4% | -3.32 | 41.7% | -$13,196 | -$17,210 | -$2,619 | no |
| prev_day | bounce | 1.0R | 1423 | 44% | -3.42 | -3.18 | 27.1% | -3.26 | 40.2% | -$3,699 | -$4,795 | -$1,171 | no |
| prev_week | retest | 1.0R | 357 | 43% | -3.83 | -2.94 | 11.4% | -3.37 | 35.5% | -$1,090 | -$1,360 | -$275 | no |
| asia | bounce | 1.5R | 2922 | 38% | -3.56 | -3.40 | 33.2% | -3.36 | 34.4% | -$8,935 | -$11,636 | -$1,454 | no |
| asia | retest | 1.0R | 1557 | 44% | -3.64 | -3.21 | 14.9% | -3.39 | 34.2% | -$4,264 | -$5,557 | -$1,406 | no |
| swing | bounce | 1.5R | 4673 | 39% | -3.52 | -3.64 | 69.7% | -3.33 | 33.7% | -$13,442 | -$17,402 | -$2,987 | no |
| asia | bounce | 1.0R | 2922 | 44% | -3.63 | -3.47 | 30.1% | -3.36 | 26.6% | -$8,603 | -$11,578 | -$2,018 | no |
| prev_week | bounce | 1.5R | 655 | 38% | -4.11 | -2.98 | 3.9% | -3.27 | 20.2% | -$2,257 | -$2,764 | -$436 | no |
| asia | breakout | 1.0R | 2662 | 43% | -4.09 | -3.60 | 6.6% | -3.59 | 16.4% | -$8,206 | -$10,716 | -$2,683 | no |
| asia | breakout | 1.5R | 2662 | 37% | -4.13 | -3.51 | 3.4% | -3.59 | 15.3% | -$8,766 | -$11,291 | -$2,227 | no |
| prev_week | bounce | 1.0R | 655 | 42% | -4.49 | -2.75 | 0.0% | -3.30 | 8.7% | -$2,402 | -$2,942 | -$540 | no |
| round | retest | 1.0R | 961 | 42% | -4.37 | -3.32 | 2.0% | -3.27 | 6.5% | -$3,880 | -$4,733 | -$324 | no |
| round | retest | 1.5R | 961 | 37% | -4.56 | -3.34 | 1.0% | -3.23 | 5.2% | -$4,019 | -$5,010 | -$361 | no |
| round | bounce | 1.5R | 1792 | 37% | -4.38 | -3.94 | 13.2% | -3.29 | 5.1% | -$6,766 | -$8,481 | -$1,084 | no |
| round | bounce | 1.0R | 1792 | 42% | -4.33 | -3.81 | 8.6% | -3.29 | 4.1% | -$6,524 | -$8,058 | -$1,232 | no |
| all | breakout | 1.0R | 8108 | 44% | -3.26 | -3.60 | 97.0% | -3.53 | 84.2% | -$20,799 | -$28,559 | -$5,643 | no |
| all | breakout | 1.5R | 8108 | 39% | -3.20 | -3.67 | 99.6% | -3.50 | 81.7% | -$22,248 | -$29,841 | -$3,728 | no |
| all | retest | 1.0R | 4385 | 44% | -3.49 | -3.34 | 26.4% | -3.39 | 37.2% | -$12,930 | -$16,682 | -$2,372 | no |
| all | retest | 1.5R | 4385 | 38% | -3.52 | -3.38 | 26.9% | -3.36 | 32.7% | -$13,323 | -$17,016 | -$2,130 | no |
| all | bounce | 1.5R | 8460 | 38% | -3.64 | -3.52 | 25.2% | -3.32 | 14.6% | -$26,200 | -$33,747 | -$4,569 | no |
| all | bounce | 1.0R | 8460 | 43% | -3.63 | -3.45 | 15.6% | -3.32 | 12.6% | -$25,955 | -$33,464 | -$4,715 | no |

Of the 30 eligible combinations, **4** beat the 95th percentile of after-signal twins, **4** of hour-matched twins and **4** both; about 1.5 would by luck alone (more, in clusters, because the combinations share levels).

## 3. How often price sits at a level

Share of 15-minute candles (03:00-13:00, 2014-2022) that touch a level's zone:

| Level type | Share |
|---|---:|
| prev_day | 19% |
| prev_week | 9% |
| swing | 54% |
| round | 22% |
| asia | 42% |
| all | 81% |

## 4. Spreads in the data

The recorded spread is almost constant in 2014-2018 ($0.51 in 2014, $0.35 in 2015-2018, little widening at news), so costs in those years are likely too low. 2014-2020 must also be profitable at 2x costs to pass.

## 5. 2023-2024 test

Nothing passed development, so 2023-2024 was not looked at (as planned).
