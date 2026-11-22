# Support and resistance with an AI filter (Equiti costs)

Levels: yesterday's and last week's high/low, hourly swing levels with 2+ turns, $50 round numbers, the Asian range. Setups on 15-minute candles closing 03:00-13:00 New York: bounce off a level, or break and retest. Stop beyond the zone and wick plus a buffer ($5-$30), target 1R / 1.5R / next level, only with room to the next major level. One trade at a time, max 2 a day, out by 16:45. Costs: xauusd_costs_equiti, $30 risk on $3,000. Option chosen on 2014-2022; AI fitted on 2014-2020, cut-off chosen on 2021-2022; one look at 2023-2024. 2025-2026 not loaded.

## Rule options (2014-2022 only)

| Setups | Target | Stop buffer | 2014-20 trades | Win % | Net $ | 2021-22 trades | Win % | Net $ | Qualifies |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| retest | 1.5R | 0.15 x ADR | 22 | 36% | -174 | 24 | 54% | 136 | no |
| retest | next | 0.15 x ADR | 22 | 36% | -194 | 24 | 54% | 107 | no |
| retest | 1R | 0.15 x ADR | 45 | 38% | -309 | 42 | 57% | 103 | no |
| retest | next | 0.05 x ADR | 25 | 20% | -395 | 14 | 57% | 142 | no |
| retest | 1.5R | 0.05 x ADR | 25 | 24% | -333 | 14 | 57% | 81 | no |
| retest | 1R | 0.05 x ADR | 40 | 32% | -400 | 32 | 56% | 93 | no |
| both | next | 0.15 x ADR | 98 | 38% | -303 | 80 | 39% | -187 | no |
| bounce | next | 0.15 x ADR | 83 | 37% | -212 | 62 | 32% | -299 | no |
| bounce | next | 0.05 x ADR | 70 | 40% | -72 | 69 | 28% | -475 | no |
| both | 1.5R | 0.15 x ADR | 98 | 39% | -379 | 81 | 38% | -169 | no |
| bounce | 1.5R | 0.15 x ADR | 83 | 39% | -287 | 63 | 33% | -295 | no |
| bounce | 1.5R | 0.05 x ADR | 70 | 41% | -205 | 70 | 27% | -618 | no |
| both | next | 0.05 x ADR | 91 | 34% | -467 | 79 | 30% | -376 | no |
| both | 1.5R | 0.05 x ADR | 91 | 36% | -560 | 80 | 30% | -565 | no |
| bounce | 1R | 0.05 x ADR | 141 | 45% | -541 | 138 | 43% | -591 | no |
| bounce | 1R | 0.15 x ADR | 182 | 42% | -728 | 128 | 40% | -639 | no |
| both | 1R | 0.05 x ADR | 169 | 42% | -876 | 161 | 44% | -595 | no |
| both | 1R | 0.15 x ADR | 211 | 42% | -936 | 151 | 41% | -626 | no |

Chosen: **retest, target next, stop buffer 0.05 x ADR** (qualified: no - none did).

## AI cut-off (2021-2022)

| Cut-off | Trades | Win % | Net $/trade | Net $ | Max drop $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| no filter | 14 | 57% | 10.18 | 142 | 30 |
| >= 0.40 | 0 | | | | |
| >= 0.45 | 0 | | | | |
| >= 0.50 | 0 | | | | |
| >= 0.55 | 0 | | | | |
| >= 0.60 | 0 | | | | |

Chosen cut-off: **no filter**.

## 2023-2024 (one look)

| | Trades | Win % | Net $/trade | Net $ | Max drop $ |
| --- | ---: | ---: | ---: | ---: | ---: |
| With AI filter | 25 | 20% | -11.88 | -297 | 272 |
| With AI filter, 2x costs | 25 | 20% | -12.22 | -306 | 280 |
| Rules only | 25 | 20% | -11.88 | -297 | 272 |
| Rules only, 2x costs | 25 | 20% | -12.22 | -306 | 280 |

Passed: **no** (profitable at 1x and 2x, >= 60 trades, max drop < $600). 50% winners: **no**.

Replays: `docs/replays/xauusd-sr-2023-2024.html`.
