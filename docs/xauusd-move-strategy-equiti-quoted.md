# Breakouts only on predicted busy mornings

A news-aware model predicts the 08:00-12:00 New York range; on the busiest predicted mornings stop orders wait k x ADR above and below the 08:00 price. Rule chosen by fitting 2015-2020 and scoring 2021-2022; looked at once on 2023-2024 with the model refitted on 2015-2022. Costs: xauusd_costs_equiti_quoted, $30 risk on $3,000. 2025-2026 not loaded.

Chosen on 2021-2022: top 20% busiest mornings, k = 0.2, target 2.0R: 106 trades, 48% winners, -44 $ (every day with the same rule: -873 $).

Passed on 2023-2024: **no**.

Model check 2023-2024: rank correlation +0.26; mornings picked as busy moved 0.78 x ADR, the others 0.67 x ADR.

| 2023-2024 | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ | PF | Max DD $ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Predicted busy days | 121 | 46% | 24.19 | -18.25 | 1.39 | 168 | 1.14 | 195 |
| Predicted busy days, 2x costs | 121 | 46% | 24.02 | -18.73 | 1.06 | 128 | 1.10 | 228 |
| Every day | 430 | 42% | 20.09 | -16.00 | -0.89 | -382 | 0.90 | 943 |
| Predicted quiet days | 52 | 42% | 14.88 | -12.45 | -0.88 | -46 | 0.88 | 212 |

## All rule choices on 2021-2022 (best first)

| Top share | k | Target R | Trades | Win % | Net $ |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20% | 0.2 | 2.0 | 106 | 48% | -44 |
| 20% | 0.2 | 1.5 | 106 | 48% | -61 |
| 40% | 0.2 | 1.0 | 223 | 52% | -73 |
| 20% | 0.2 | 1.0 | 106 | 51% | -119 |
| 40% | 0.15 | 2.0 | 227 | 41% | -120 |
| 20% | 0.15 | 2.0 | 107 | 39% | -151 |
| 40% | 0.2 | 1.5 | 223 | 48% | -154 |
| 40% | 0.15 | 1.5 | 227 | 44% | -168 |
| 30% | 0.2 | 1.5 | 151 | 49% | -178 |
| 20% | 0.1 | 1.0 | 108 | 48% | -181 |
| 30% | 0.15 | 1.0 | 154 | 49% | -197 |
| 30% | 0.2 | 1.0 | 151 | 52% | -197 |
| 30% | 0.2 | 2.0 | 151 | 48% | -209 |
| 30% | 0.15 | 2.0 | 154 | 42% | -210 |
| 20% | 0.15 | 1.0 | 107 | 47% | -216 |
| 20% | 0.15 | 1.5 | 107 | 41% | -240 |
| 30% | 0.15 | 1.5 | 154 | 44% | -275 |
| 40% | 0.2 | 2.0 | 223 | 48% | -282 |
| 40% | 0.15 | 1.0 | 227 | 48% | -324 |
| 30% | 0.1 | 1.0 | 155 | 47% | -353 |
| 20% | 0.1 | 1.5 | 108 | 37% | -408 |
| 30% | 0.1 | 1.5 | 155 | 38% | -486 |
| 40% | 0.1 | 1.0 | 228 | 46% | -574 |
| 20% | 0.1 | 2.0 | 108 | 31% | -580 |
| 30% | 0.1 | 2.0 | 155 | 32% | -711 |
| 40% | 0.1 | 1.5 | 228 | 38% | -807 |
| 40% | 0.1 | 2.0 | 228 | 33% | -834 |
