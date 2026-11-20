# Gold + global news, round 2 (tuned on 2021-2022, tested on 2023-2024)

Daily 08:00-12:00 New York trade (1:1 at half the 20-day range). Three input sets: base 21, news 92, full 216 (adds fresh 3-hour news, event records, people and organisations). Every setting chosen by fitting 2015-2020 and scoring 2021-2022 (1456 / 505 days); then refitted on 2015-2022 and looked at once on 2023-2024 (462 days). Log loss 0.693 = no better than 50/50. Expensive costs. 2025-2026 not loaded.

Best on 2021-2022: **news** inputs, log loss 0.6946, accuracy 50.3% (fit years 66.3%). Passed: **no**.

## Direction

| Inputs | 2021-22 log loss | 2021-22 right | 2023-24 log loss | 2023-24 right | Trades | Win % | Net $ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 0.6965 | 48.9% | 0.6951 | 48.5% | 85 | 52% | -189 |
| news | 0.6946 | 50.3% | 0.6981 | 48.7% | 61 | 43% | -142 |
| full | 0.7003 | 48.1% | 0.6990 | 47.6% | 81 | 44% | -200 |
| always buy (2023-24) | | | | | 462 | 45% | -856 |

## How much gold moves 08:00-12:00 (range in units of the 20-day average daily range)

Average 2023-24 range: 0.69 x ADR. R-squared 0 = no better than predicting the average; rank correlation 0 = no ordering skill.

| Inputs | 2021-22 R-squared | 2021-22 rank corr | 2023-24 R-squared | 2023-24 rank corr |
| --- | ---: | ---: | ---: | ---: |
| base | +0.003 | +0.157 | +0.012 | +0.159 |
| news | +0.045 | +0.278 | +0.053 | +0.264 |
| full | +0.028 | +0.251 | +0.072 | +0.304 |
