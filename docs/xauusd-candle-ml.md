# Candle patterns at every hour (train 2014-2020, choose 2021-22, test 2023-24)

Inputs: last 24 five-minute candles and last 24 hourly candles (with the share of green 5-minute candles and choppiness inside each hour), time of day, weekday, volatility; all in units of the 20-day average daily range. Decision every hour 18:00-15:00 New York; 1:1 trade with R = 0.5 x ADR x sqrt(hold/240), out at the end of the hold (by 16:45). Trade when the model gives >= 55% to one side. Expensive costs, $30 risk on $3,000. 2025-2026 not loaded.

## Direction right, by holding time

| Hold | Settings (depth / rows per leaf / rounds) | Fit years | 2021-22 | 2023-24 | 2021-22 net $ (all hours) | 2023-24 net $ (all hours) | Hours kept from 2021-22 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 30 min | 3 / 300 / 200 | 59.0% | 51.9% | 51.2% | -12,089 | -10,038 | none |
| 60 min | 3 / 1500 / 200 | 58.5% | 50.8% | 49.6% | -8,930 | -4,754 | none |
| 120 min | 3 / 1500 / 200 | 59.3% | 50.6% | 51.1% | -4,968 | -2,535 | none |
| 240 min | 3 / 1500 / 200 | 60.0% | 50.9% | 50.2% | -2,022 | -1,540 | 21:00, 00:00 |

## Kept hour + hold cells together

| Period | Trades | Win % | Net $/trade | Net $ |
| --- | ---: | ---: | ---: | ---: |
| 2021-22 (where they were chosen) | 149 | 51% | 0.33 | 49 |
| 2023-24 | 102 | 48% | -0.57 | -58 |
| 2023-24 at 2x costs | 102 | 46% | -1.84 | -187 |

Passed: **no**. Heat map: `docs/xauusd-candle-ml-heatmap.html`.
