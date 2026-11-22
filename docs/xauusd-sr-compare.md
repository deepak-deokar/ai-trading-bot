# XAUUSD support and resistance, round 2: each level against random entries

Rules fixed before running: [docs/xauusd-sr-v2-plan.md](xauusd-sr-v2-plan.md). Costs: xauusd_costs_equiti. $30 risk per trade. Development years 2014-2022, every setup counted on its own (no daily cap).

**Twin** = the same trade (day, direction, stop distance, target) entered at a random 15-minute mark after the real entry, up to 13:00 New York, 100 times. **Beats** = how many of those runs the real setup's average $ per trade beat. Passing needs 95+, money made in 2014-20 and 2021-22, and 200+ trades.

| Level | Setup | Target | Trades | Win rate | Avg $/trade | Twin avg | Beats | 2014-20 | 2021-22 | Pass |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| prev_day | breakout | 1.5R | 1470 | 41% | -2.05 | -3.75 | 100 | -$2,268 | -$751 | no |
| swing | breakout | 1.0R | 4398 | 46% | -2.64 | -3.51 | 100 | -$9,342 | -$2,254 | no |
| swing | breakout | 1.5R | 4398 | 40% | -2.36 | -3.62 | 100 | -$9,526 | -$833 | no |
| prev_day | breakout | 1.0R | 1470 | 47% | -2.11 | -3.31 | 99 | -$1,767 | -$1,337 | no |
| round | breakout | 1.5R | 1814 | 39% | -3.33 | -3.87 | 92 | -$5,215 | -$819 | no |
| swing | retest | 1.0R | 2351 | 44% | -3.00 | -3.43 | 90 | -$5,941 | -$1,102 | no |
| swing | retest | 1.5R | 2351 | 39% | -3.06 | -3.44 | 89 | -$6,125 | -$1,077 | no |
| prev_week | breakout | 1.5R | 684 | 40% | -2.71 | -3.46 | 85 | -$1,155 | -$697 | no |
| round | breakout | 1.0R | 1814 | 44% | -3.39 | -3.78 | 83 | -$5,313 | -$831 | no |
| prev_day | retest | 1.0R | 767 | 46% | -2.62 | -2.85 | 66 | -$1,464 | -$547 | no |
| swing | bounce | 1.0R | 4673 | 44% | -3.38 | -3.46 | 64 | -$13,196 | -$2,619 | no |
| swing | bounce | 1.5R | 4673 | 39% | -3.52 | -3.61 | 62 | -$13,442 | -$2,987 | no |
| prev_day | bounce | 1.5R | 1423 | 40% | -3.04 | -3.08 | 54 | -$3,331 | -$996 | no |
| prev_day | retest | 1.5R | 767 | 41% | -2.88 | -2.84 | 48 | -$1,705 | -$506 | no |
| prev_week | retest | 1.5R | 357 | 40% | -3.00 | -2.96 | 47 | -$804 | -$269 | no |
| prev_week | breakout | 1.0R | 684 | 45% | -3.52 | -3.40 | 45 | -$1,664 | -$743 | no |
| asia | bounce | 1.5R | 2922 | 38% | -3.56 | -3.42 | 35 | -$8,935 | -$1,454 | no |
| asia | bounce | 1.0R | 2922 | 44% | -3.63 | -3.46 | 31 | -$8,603 | -$2,018 | no |
| prev_day | bounce | 1.0R | 1423 | 44% | -3.42 | -3.22 | 31 | -$3,699 | -$1,171 | no |
| asia | retest | 1.5R | 1557 | 38% | -3.45 | -3.13 | 22 | -$4,086 | -$1,280 | no |
| asia | retest | 1.0R | 1557 | 44% | -3.64 | -3.28 | 14 | -$4,264 | -$1,406 | no |
| prev_week | retest | 1.0R | 357 | 43% | -3.83 | -3.00 | 14 | -$1,090 | -$275 | no |
| round | bounce | 1.5R | 1792 | 37% | -4.38 | -3.92 | 13 | -$6,766 | -$1,084 | no |
| asia | breakout | 1.0R | 2662 | 43% | -4.09 | -3.57 | 7 | -$8,206 | -$2,683 | no |
| round | bounce | 1.0R | 1792 | 42% | -4.33 | -3.76 | 7 | -$6,524 | -$1,232 | no |
| asia | breakout | 1.5R | 2662 | 37% | -4.13 | -3.52 | 3 | -$8,766 | -$2,227 | no |
| prev_week | bounce | 1.5R | 655 | 38% | -4.11 | -2.98 | 2 | -$2,257 | -$436 | no |
| prev_week | bounce | 1.0R | 655 | 42% | -4.49 | -2.80 | 0 | -$2,402 | -$540 | no |
| round | retest | 1.0R | 961 | 42% | -4.37 | -3.29 | 0 | -$3,880 | -$324 | no |
| round | retest | 1.5R | 961 | 37% | -4.56 | -3.35 | 0 | -$4,019 | -$361 | no |
| all | breakout | 1.5R | 8108 | 39% | -3.20 | -3.68 | 100 | -$22,248 | -$3,728 | no |
| all | breakout | 1.0R | 8108 | 44% | -3.26 | -3.56 | 96 | -$20,799 | -$5,643 | no |
| all | retest | 1.0R | 4385 | 44% | -3.49 | -3.37 | 32 | -$12,930 | -$2,372 | no |
| all | retest | 1.5R | 4385 | 38% | -3.52 | -3.38 | 32 | -$13,323 | -$2,130 | no |
| all | bounce | 1.5R | 8460 | 38% | -3.64 | -3.53 | 24 | -$26,200 | -$4,569 | no |
| all | bounce | 1.0R | 8460 | 43% | -3.63 | -3.45 | 11 | -$25,955 | -$4,715 | no |

## How often price sits at a level

Share of 15-minute candles (03:00-13:00, 2014-2022) that touch a level's zone:

| Level type | Share |
|---|---:|
| prev_day | 19% |
| prev_week | 9% |
| swing | 54% |
| round | 22% |
| asia | 42% |
| all | 81% |

## 2023-2024 test

Nothing passed development, so 2023-2024 was not looked at (as planned).
