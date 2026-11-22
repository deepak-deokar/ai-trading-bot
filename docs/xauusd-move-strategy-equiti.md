# Breakouts only on predicted busy mornings

A news-aware model predicts the 08:00-12:00 New York range; on the busiest predicted mornings stop orders wait k x ADR above and below the 08:00 price. Rule chosen by fitting 2015-2020 and scoring 2021-2022; looked at once on 2023-2024 with the model refitted on 2015-2022. Costs: xauusd_costs_equiti, $30 risk on $3,000. 2025-2026 not loaded.

Chosen on 2021-2022: top 20% busiest mornings, k = 0.2, target 2.0R: 106 trades, 48% winners, -47 $ (every day with the same rule: -934 $).

Passed on 2023-2024: **no**.

Model check 2023-2024: rank correlation +0.26; mornings picked as busy moved 0.78 x ADR, the others 0.67 x ADR.

| 2023-2024 | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ | PF | Max DD $ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Predicted busy days | 121 | 46% | 23.32 | -18.32 | 0.95 | 115 | 1.10 | 201 |
| Predicted busy days, 2x costs | 121 | 45% | 23.71 | -18.02 | 0.61 | 73 | 1.06 | 230 |
| Every day | 430 | 42% | 19.41 | -16.03 | -1.20 | -515 | 0.87 | 989 |
| Predicted quiet days | 52 | 42% | 13.30 | -12.59 | -1.63 | -85 | 0.78 | 219 |

## All rule choices on 2021-2022 (best first)

| Top share | k | Target R | Trades | Win % | Net $ |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20% | 0.2 | 2.0 | 106 | 48% | -47 |
| 20% | 0.2 | 1.5 | 106 | 48% | -95 |
| 20% | 0.2 | 1.0 | 106 | 51% | -132 |
| 40% | 0.2 | 1.0 | 223 | 51% | -140 |
| 20% | 0.15 | 2.0 | 107 | 39% | -162 |
| 40% | 0.15 | 2.0 | 227 | 41% | -186 |
| 20% | 0.1 | 1.0 | 108 | 48% | -217 |
| 30% | 0.2 | 1.0 | 151 | 52% | -243 |
| 30% | 0.2 | 2.0 | 151 | 48% | -244 |
| 30% | 0.15 | 2.0 | 154 | 41% | -252 |
| 30% | 0.2 | 1.5 | 151 | 49% | -256 |
| 40% | 0.2 | 1.5 | 223 | 48% | -256 |
| 20% | 0.15 | 1.5 | 107 | 41% | -262 |
| 40% | 0.15 | 1.5 | 227 | 43% | -279 |
| 30% | 0.15 | 1.0 | 154 | 47% | -302 |
| 20% | 0.15 | 1.0 | 107 | 46% | -303 |
| 40% | 0.2 | 2.0 | 223 | 47% | -345 |
| 30% | 0.15 | 1.5 | 154 | 43% | -358 |
| 30% | 0.1 | 1.0 | 155 | 47% | -418 |
| 40% | 0.15 | 1.0 | 227 | 47% | -452 |
| 20% | 0.1 | 1.5 | 108 | 37% | -467 |
| 30% | 0.1 | 1.5 | 155 | 38% | -574 |
| 20% | 0.1 | 2.0 | 108 | 31% | -611 |
| 40% | 0.1 | 1.0 | 228 | 46% | -749 |
| 30% | 0.1 | 2.0 | 155 | 32% | -803 |
| 40% | 0.1 | 1.5 | 228 | 38% | -945 |
| 40% | 0.1 | 2.0 | 228 | 33% | -975 |
