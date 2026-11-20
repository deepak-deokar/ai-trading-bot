# News-reaction model (walk-forward, 2014-2024 only)

A logistic-regression model reads the first 15 minutes after US jobs, CPI and Fed releases and estimates the chance that a buy wins a 1:1 trade (stop and target = half the 20-day average daily range, normal stops, closed by 12:00 or 16:45 New York). For each year from 2016 the model is trained only on earlier years. Expensive costs, $30 risk on $3,000. 2025 and 2026 not loaded.

Events: 328; traded years 2016-2024: 270 events. A buy won 52% of them. Model direction right: 49%.

Pass: profitable, at least 50% winning trades, and better than the best simple rule (main margin 0.05). Passed: **no**.

| Rule | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ | PF | Max DD $ | Green years |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| model, margin 0.00 | 270 | 45% | 15.47 | -18.42 | -3.11 | -840 | 0.69 | 973 | 1/9 |
| model, margin 0.05 | 173 | 44% | 15.08 | -19.05 | -3.86 | -668 | 0.64 | 816 | 2/9 |
| model, margin 0.10 | 116 | 45% | 15.77 | -18.87 | -3.34 | -388 | 0.68 | 596 | 4/9 |
| simple: follow the news candle | 270 | 47% | 15.60 | -18.36 | -2.26 | -611 | 0.77 | 700 | 3/9 |
| simple: against the news candle | 270 | 44% | 17.36 | -16.97 | -1.84 | -498 | 0.81 | 596 | 3/9 |
| simple: always buy | 270 | 48% | 16.13 | -17.78 | -1.58 | -426 | 0.83 | 710 | 3/9 |

Net $ per year:

| Rule | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| model, margin 0.00 | 32 | -58 | -392 | -21 | -134 | -47 | -115 | -30 | -76 |
| model, margin 0.05 | 30 | -58 | -265 | -40 | -91 | -64 | -193 | 51 | -37 |
| model, margin 0.10 | 2 | -60 | -134 | -97 | -48 | 26 | -181 | 57 | 48 |
| simple: follow the news candle | -66 | -142 | -208 | 45 | -69 | 11 | -190 | 67 | -59 |
| simple: against the news candle | -83 | -2 | 19 | -182 | -103 | -131 | 132 | -168 | 21 |
| simple: always buy | -86 | -173 | 38 | -167 | -159 | 34 | 272 | -70 | -116 |

What the model learned (positive = favours buying), averaged over the yearly models, and in how many yearly models the weight had that sign:

| Input | Avg weight | Same sign in years | Weight, trained on 2014-2024 |
| --- | ---: | ---: | ---: |
| is_jobs | -0.066 | 7/9 | -0.186 |
| is_cpi | -0.171 | 9/9 | -0.218 |
| news_move | -0.064 | 5/9 | +0.111 |
| news_range | +0.048 | 6/9 | -0.007 |
| news_close_pos | +0.040 | 5/9 | -0.077 |
| pre_news_move | -0.461 | 9/9 | -0.104 |
| trend_5d | +0.172 | 5/9 | -0.179 |
| trend_20d | +0.048 | 8/9 | +0.044 |
| pos_in_yday_range | +0.321 | 9/9 | +0.272 |
| room_up | +0.115 | 6/9 | -0.029 |
| room_down | -0.069 | 6/9 | -0.105 |
| pre_news_range | -0.027 | 5/9 | -0.018 |
| broke_level | +0.192 | 5/9 | -0.044 |
