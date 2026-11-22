# Candle patterns at every hour (train 2014-2020, choose 2021-22, test 2023-24)

Inputs: last 24 five-minute candles and last 24 hourly candles (with the share of green 5-minute candles and choppiness inside each hour), time of day, weekday, volatility; all in units of the 20-day average daily range. Decision every hour 18:00-15:00 New York; 1:1 trade with R = 0.5 x ADR x sqrt(hold/240), out at the end of the hold (by 16:45). Trade when the model gives >= 55% to one side. Costs: xauusd_costs_equiti_quoted, $30 risk on $3,000. 2025-2026 not loaded.

## Direction right, by holding time

| Hold | Settings (depth / rows per leaf / rounds) | Fit years | 2021-22 | 2023-24 | 2021-22 net $ (all hours) | 2023-24 net $ (all hours) | Hours kept from 2021-22 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 30 min | 3 / 300 / 200 | 59.0% | 51.9% | 51.2% | -5,461 | -5,472 | none |
| 60 min | 3 / 1500 / 200 | 58.5% | 50.8% | 49.6% | -4,591 | -2,539 | none |
| 120 min | 3 / 1500 / 200 | 59.3% | 50.6% | 51.1% | -2,864 | -1,450 | 22:00 |
| 240 min | 3 / 1500 / 200 | 60.0% | 50.9% | 50.2% | -815 | -979 | 18:00, 19:00, 20:00, 21:00, 22:00, 00:00, 06:00, 11:00 |

## Kept hour + hold cells together

| Period | Trades | Win % | Net $/trade | Net $ |
| --- | ---: | ---: | ---: | ---: |
| 2021-22 (where they were chosen) | 834 | 55% | 0.54 | 449 |
| 2023-24 | 478 | 47% | -1.25 | -596 |
| 2023-24 at 2x costs | 478 | 47% | -1.35 | -644 |

Passed: **no**. Heat map: `docs/xauusd-candle-ml-heatmap-equiti-quoted.html`.
