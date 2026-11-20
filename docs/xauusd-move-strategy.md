# Breakouts only on predicted busy mornings

A news-aware model predicts the 08:00-12:00 New York range; on the busiest predicted mornings stop orders wait k x ADR above and below the 08:00 price. Rule chosen by fitting 2015-2020 and scoring 2021-2022; looked at once on 2023-2024 with the model refitted on 2015-2022. Expensive costs, $30 risk on $3,000. 2025-2026 not loaded.

Chosen on 2021-2022: top 20% busiest mornings, k = 0.2, target 2.0R: 106 trades, 46% winners, -107 $ (every day with the same rule: -1,094 $).

Passed on 2023-2024: **no**.

Model check 2023-2024: rank correlation +0.26; mornings picked as busy moved 0.78 x ADR, the others 0.67 x ADR.

| 2023-2024 | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ | PF | Max DD $ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Predicted busy days | 121 | 45% | 23.00 | -17.66 | 0.48 | 59 | 1.05 | 257 |
| Predicted busy days, 2x costs | 121 | 41% | 21.75 | -17.33 | -1.18 | -143 | 0.88 | 433 |
| Every day | 430 | 41% | 18.70 | -15.49 | -1.57 | -676 | 0.83 | 1,114 |
| Predicted quiet days | 52 | 40% | 13.04 | -11.98 | -1.87 | -97 | 0.74 | 228 |

## All rule choices on 2021-2022 (best first)

| Top share | k | Target R | Trades | Win % | Net $ |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20% | 0.2 | 2.0 | 106 | 46% | -107 |
| 20% | 0.2 | 1.5 | 106 | 47% | -176 |
| 20% | 0.2 | 1.0 | 106 | 50% | -217 |
| 20% | 0.15 | 2.0 | 107 | 38% | -273 |
| 40% | 0.2 | 1.0 | 223 | 51% | -298 |
| 30% | 0.2 | 2.0 | 151 | 47% | -300 |
| 30% | 0.2 | 1.5 | 151 | 48% | -332 |
| 30% | 0.2 | 1.0 | 151 | 51% | -340 |
| 20% | 0.15 | 1.5 | 107 | 40% | -381 |
| 40% | 0.2 | 1.5 | 223 | 48% | -390 |
| 30% | 0.15 | 2.0 | 154 | 40% | -407 |
| 20% | 0.1 | 1.0 | 108 | 46% | -407 |
| 40% | 0.2 | 2.0 | 223 | 46% | -437 |
| 40% | 0.15 | 1.5 | 227 | 43% | -450 |
| 20% | 0.15 | 1.0 | 107 | 44% | -452 |
| 40% | 0.15 | 2.0 | 227 | 40% | -457 |
| 30% | 0.15 | 1.0 | 154 | 46% | -462 |
| 30% | 0.15 | 1.5 | 154 | 42% | -486 |
| 30% | 0.1 | 1.0 | 155 | 46% | -608 |
| 40% | 0.15 | 1.0 | 227 | 46% | -634 |
| 20% | 0.1 | 1.5 | 108 | 35% | -670 |
| 20% | 0.1 | 2.0 | 108 | 30% | -778 |
| 30% | 0.1 | 1.5 | 155 | 36% | -855 |
| 40% | 0.1 | 1.0 | 228 | 45% | -956 |
| 30% | 0.1 | 2.0 | 155 | 32% | -996 |
| 40% | 0.1 | 1.5 | 228 | 36% | -1,222 |
| 40% | 0.1 | 2.0 | 228 | 32% | -1,273 |
