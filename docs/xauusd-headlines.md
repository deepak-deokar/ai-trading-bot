# Gold headlines vs the 08:00-12:00 New York direction

Rules: `docs/xauusd-headlines-plan.md` (written before running). GDELT gold headlines (titles exist from 2019-09-22): 615,680 after cleaning; 1162 trading days had none in the 24 h before 08:00. Tuned on 2019-10..2021 -> 2022, looked at once on 2023-2024 (third look at those years for news models). Log loss 0.693 = coin flip. Expensive costs. 2025-2026 not loaded.

Winner on 2022: **headline_text**. Passed: **no**.

## No model: does the headline mood line up with the move? (2019-10 to 2022)

Share of days a buy won, split by the 24 h up-minus-down headline share:

| Bottom fifth (most down) | Middle | Top fifth (most up) | All days |
| ---: | ---: | ---: | ---: |
| 53.5% | 51.2% | 52.8% | 51.9% |

## Direction

| Candidate | 2022 log loss | 2022 right | 2023-24 log loss | 2023-24 right | Trades | Win % | Net $ | Net $ at 2x |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v2_news | 0.7013 | 50.4% | 0.7019 | 45.7% | 220 | 46% | -642 | -804 |
| news_words | 0.7029 | 48.4% | 0.6994 | 47.4% | 61 | 41% | -207 | -237 |
| headline_text | 0.6926 | 53.1% | 0.6940 | 50.9% | 50 | 40% | -127 | -159 |
| words_only | 0.6996 | 48.1% | 0.6983 | 48.9% | 95 | 44% | -150 | -244 |
| always buy (2023-24) | | | | | 462 | 45% | -856 | |

## Move size 2023-2024 (range in ADR units)

| Inputs | 2022 R-squared | 2023-24 R-squared | 2023-24 rank corr |
| --- | ---: | ---: | ---: |
| v2_news | +0.045 | +0.016 | +0.149 |
| news_words | +0.043 | +0.016 | +0.148 |

## What the headline text model learned (fitted on 2019-10..2022)

Words before gold rose: virus cases, holds, cases, may 2021, gold etfs, q4, 24k gold, gold bond, qatar, element79, year gold, element79 gold, treasure hunt, last week, 2021, crisis, pandemic, resources corp, jahr, northern

Words before gold fell: condor gold, condor, snowline gold, snowline, tonnes, 53, high as, aex, east, aex gold, targets at, one gold, plc, para, march 2021, kevin, zone, bill, zu, to create
