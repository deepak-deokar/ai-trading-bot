# Every-day model with US dollar, yields, stocks and VIX (walk-forward)

Each trading day at 08:00 New York a logistic-regression model estimates the chance that a 1:1 buy wins by 12:00 (stop and target = half the 20-day average daily range, normal stops). Inputs: gold's own context, the previous US close of the US dollar index, 10-year and 3-month yields, S&P 500 and VIX, and the day's jobs/CPI/Fed calendar. For each year from 2016 the model is trained only on earlier years. Expensive costs, $30 risk on $3,000. 2025 and 2026 not loaded.

Days: 2763; traded years: 2269 days. A buy won 51% of them. Model direction right: 49.3% (when confident: 50.2%).

Pass: profitable, at least 50% winning trades, better than the best simple rule (main margin 0.05). Passed: **no**. Main model at 2x costs: -3,194 $.

| Rule | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ | PF | Max DD $ | Green years |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| model, margin 0.00 | 2266 | 44% | 13.97 | -14.83 | -2.15 | -4,880 | 0.74 | 4,916 | 0/9 |
| model, margin 0.05 | 1013 | 44% | 14.76 | -14.92 | -1.79 | -1,818 | 0.78 | 1,833 | 2/9 |
| model, margin 0.10 | 361 | 45% | 15.17 | -15.08 | -1.58 | -572 | 0.81 | 609 | 2/9 |
| simple: always buy | 2266 | 45% | 13.65 | -15.04 | -2.01 | -4,555 | 0.76 | 4,676 | 0/9 |
| simple: follow the overnight move | 2266 | 44% | 13.96 | -14.91 | -2.26 | -5,119 | 0.73 | 5,371 | 0/9 |
| simple: against the overnight move | 2266 | 45% | 13.55 | -15.01 | -2.14 | -4,848 | 0.74 | 4,820 | 0/9 |
| simple: follow the 20-day trend | 2266 | 44% | 13.81 | -14.86 | -2.11 | -4,771 | 0.74 | 4,901 | 0/9 |
| simple: against yesterday's US dollar move | 2246 | 43% | 13.86 | -14.89 | -2.47 | -5,549 | 0.71 | 5,522 | 1/9 |

Net $ per year:

| Rule | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| model, margin 0.00 | -523 | -390 | -927 | -528 | -488 | -19 | -589 | -642 | -775 |
| model, margin 0.05 | -394 | -126 | -444 | 91 | -212 | -74 | -155 | -532 | 28 |
| model, margin 0.10 | -100 | 12 | -169 | -90 | -41 | -1 | -72 | -144 | 34 |
| simple: always buy | -755 | -690 | -999 | -308 | -122 | -390 | -455 | -471 | -364 |
| simple: follow the overnight move | -687 | -813 | -958 | -960 | -245 | -377 | -369 | -421 | -289 |
| simple: against the overnight move | -633 | -1,044 | -907 | -307 | -553 | -318 | -443 | -220 | -425 |
| simple: follow the 20-day trend | -695 | -599 | -945 | -572 | -525 | -139 | -447 | -234 | -614 |
| simple: against yesterday's US dollar move | -561 | -1,090 | -1,403 | -845 | -608 | -95 | -548 | 126 | -524 |

What the model learned (positive = favours buying), averaged over the yearly models, and in how many yearly models the weight had that sign:

| Input | Avg weight | Same sign in years | Weight, trained on 2014-2024 |
| --- | ---: | ---: | ---: |
| overnight_move | -0.016 | 5/9 | +0.040 |
| overnight_range | +0.123 | 8/9 | -0.040 |
| pos_in_overnight | +0.026 | 7/9 | +0.031 |
| yday_candle | +0.017 | 5/9 | +0.104 |
| trend_5d | +0.088 | 9/9 | +0.049 |
| trend_20d | +0.084 | 9/9 | +0.023 |
| pos_in_yday_range | -0.053 | 8/9 | -0.070 |
| room_up | -0.059 | 7/9 | +0.026 |
| room_down | -0.146 | 9/9 | -0.045 |
| vol_ratio | +0.026 | 5/9 | -0.005 |
| usd_1d | +0.062 | 9/9 | +0.087 |
| usd_5d | +0.064 | 9/9 | +0.023 |
| us10y_1d | -0.059 | 9/9 | -0.006 |
| us10y_5d | -0.018 | 6/9 | +0.004 |
| curve_10y_3m | -0.061 | 8/9 | -0.034 |
| spx_1d | -0.044 | 9/9 | -0.005 |
| vix_level | +0.034 | 6/9 | +0.075 |
| vix_1d | -0.085 | 9/9 | -0.086 |
| jobs_today | +0.032 | 8/9 | +0.001 |
| cpi_today | -0.029 | 6/9 | +0.027 |
| fed_today | +0.018 | 5/9 | -0.020 |
