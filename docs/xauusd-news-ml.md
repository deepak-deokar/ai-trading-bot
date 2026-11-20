# Gold with global news sentiment (train 2015-2022, test 2023-2024)

Every trading day at 08:00 New York a model estimates the chance that a 1:1 buy wins by 12:00 (stop = target = half the 20-day average daily range, normal stops). 92 inputs: gold, US dollar, yields, S&P 500, VIX, US news calendar, and 71 worldwide-news inputs from GDELT (share, surge, tone and tone change per topic over the last 24 hours vs the week before). Trained on 1962 days (2015-03-02 to 2022-12-31), tested once on 466 days (2023-01-01 to 2024-12-31). Settings fixed before running. Expensive costs, $30 risk on $3,000. 2025 and 2026 not loaded.

A buy won 49% of test days. Pass: profitable, at least 50% winning trades, better than the best simple rule. Passed: **no**.

## Direction right

| Model | Training years | Test years | Test, when confident |
| --- | ---: | ---: | ---: |
| trees, with global news | 84.4% | 47.9% | 46.6% |
| trees, without news | 75.6% | 49.1% | 49.4% |
| linear, with global news | 59.0% | 46.6% | 43.7% |

## Trades in 2023-2024

| Rule | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ | Net $ at 2x | PF | Max DD $ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| trees, with global news | 298 | 44% | 11.86 | -15.13 | -3.36 | -1,000 | -1,265 | 0.61 | 1,101 |
| trees, without news | 336 | 46% | 13.09 | -14.86 | -1.96 | -660 | -966 | 0.76 | 926 |
| linear, with global news | 316 | 41% | 12.85 | -15.47 | -3.91 | -1,235 | -1,436 | 0.57 | 1,369 |
| simple: always buy | 466 | 45% | 13.42 | -14.22 | -1.82 | -850 | - | 0.77 | 895 |
| simple: follow the overnight move | 466 | 46% | 13.23 | -14.33 | -1.56 | -725 | - | 0.80 | 900 |
| simple: against the overnight move | 466 | 47% | 13.23 | -14.15 | -1.34 | -626 | - | 0.82 | 821 |
| simple: follow the 20-day trend | 466 | 43% | 13.85 | -13.87 | -1.85 | -863 | - | 0.76 | 922 |

## Inputs that mattered most in the test years

Drop in test accuracy when the input is shuffled (trees, with news). Values near zero mean the input did not help.

| Input | Accuracy drop | +/- |
| --- | ---: | ---: |
| overnight_range | +0.0079 | 0.0069 |
| debt_crisis_surge | +0.0062 | 0.0057 |
| gold_surge | +0.0062 | 0.0040 |
| war_conflict_surge | +0.0062 | 0.0030 |
| policy_uncertainty_tone_change | +0.0056 | 0.0022 |
| gold_central_banks_tone_change | +0.0049 | 0.0037 |
| pos_in_yday_range | +0.0049 | 0.0046 |
| all_tone_change | +0.0043 | 0.0021 |
| elections_government_share | +0.0034 | 0.0043 |
| crypto_tone | +0.0028 | 0.0054 |
| war_conflict_share | +0.0028 | 0.0050 |
| policy_uncertainty_tone | +0.0028 | 0.0027 |
| pos_in_overnight | +0.0026 | 0.0068 |
| vix_level | +0.0026 | 0.0016 |
| usd_1d | +0.0024 | 0.0030 |
