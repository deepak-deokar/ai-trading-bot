# Gold on big US news days only (one trade a day)

Events: jobs report and CPI at 08:30 New York, scheduled Fed statements at 14:00 (`config/us_news_events.csv`). The 15-minute release candle sets the direction; entry at the next candle's open. Momentum trades with it (stop past the candle's other end), fade trades against it (stop past the candle's extreme). Exit at 2R or at the time limit (12:00 for 08:30 events, 16:45 for the Fed). $3,000 account, $30 risk per trade, expensive costs; 2x doubles them. Rules and pass criteria fixed before running. Development 2014-2024; 2026 not loaded.

Pass: profitable at 2x costs, profitable in at least 7 of 11 years, edge before costs with t >= 2.

## 2014-2024

| Version | Trades | Win % | Net $/trade | Net $ | PF | Net $ at 2x | Green years | Edge before costs $/oz | t | Median stop $/oz | Ordinary days at 08:30: edge $/oz (t) | Passed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| momentum/time-exit | 331 | 40% | -2.72 | -899 | 0.80 | -1,531 | 2/11 | +0.127 | +0.3 | 6.59 | +0.135 (+1.2) | no |
| momentum/2R | 331 | 41% | -4.11 | -1,359 | 0.69 | -1,843 | 2/11 | -0.111 | -0.2 | 6.59 | +0.042 (+0.5) | no |
| fade/time-exit | 314 | 21% | -6.61 | -2,076 | 0.71 | -3,287 | 3/11 | +0.346 | +1.0 | 2.47 | -0.038 (-0.6) | no |
| fade/2R | 314 | 27% | -9.39 | -2,949 | 0.55 | -3,768 | 1/11 | +0.191 | +0.7 | 2.47 | -0.045 (-1.1) | no |

## By event (normal expensive costs)

| Version | Event | Trades | Net $ | Net $/trade | Edge before costs $/oz | t |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| momentum/time-exit | Jobs report | 126 | -296 | -2.35 | -0.253 | -0.3 |
| momentum/time-exit | Inflation (CPI) | 127 | -202 | -1.59 | +0.269 | +0.4 |
| momentum/time-exit | Fed decision | 78 | -401 | -5.14 | +0.512 | +0.5 |
| momentum/2R | Jobs report | 126 | -567 | -4.50 | -0.631 | -0.9 |
| momentum/2R | Inflation (CPI) | 127 | -572 | -4.50 | -0.102 | -0.1 |
| momentum/2R | Fed decision | 78 | -220 | -2.82 | +0.716 | +0.7 |
| fade/time-exit | Jobs report | 122 | -1,155 | -9.47 | +0.100 | +0.2 |
| fade/time-exit | Inflation (CPI) | 117 | -40 | -0.34 | +1.088 | +1.9 |
| fade/time-exit | Fed decision | 75 | -881 | -11.75 | -0.459 | -0.7 |
| fade/2R | Jobs report | 122 | -979 | -8.02 | +0.085 | +0.2 |
| fade/2R | Inflation (CPI) | 117 | -769 | -6.57 | +0.562 | +1.5 |
| fade/2R | Fed decision | 75 | -1,201 | -16.01 | -0.240 | -0.5 |

Net $ per year:

| Version | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| momentum/time-exit | 11 | 564 | -175 | -247 | -402 | -23 | -127 | -57 | -332 | -4 | -108 |
| momentum/2R | -155 | 223 | -157 | -232 | -418 | -11 | -160 | -33 | -332 | 26 | -111 |
| fade/time-exit | -383 | -182 | -300 | 85 | -399 | -186 | -782 | -367 | 438 | -488 | 489 |
| fade/2R | -391 | -442 | -201 | -152 | -390 | -75 | -623 | -229 | 85 | -486 | -45 |

## 2025 check (versions profitable at 2x on 2014-2024)

| Version | Trades | Win % | Net $ | Net $ at 2x |
| --- | ---: | ---: | ---: | ---: |
| (none: no version was profitable at 2x on 2014-2024) | | | | |
