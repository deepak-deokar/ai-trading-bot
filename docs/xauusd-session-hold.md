# XAUUSD same-day session breakouts held for hours (step 2b)

$3,000 account, $30 risk (1%) per trade, at most one trade per plan per day, always closed the same day. Expensive costs: recorded bid/ask + $0.20 extra spread, $0.10 slippage per fill, $8/lot commission; '2x' doubles all three. Stop at the middle of the reference range. Development 2014-2024; 2025 shown only for rules positive at 2x on development; 2026 not loaded.

## Plans

| Plan | Rules | Days | Median range $ | Round-trip cost $/oz | Skipped days |
| --- | --- | ---: | ---: | ---: | ---: |
| london_asia_break | Asian range (00:00-07:00 London) broken 07:00-10:00, out by 16:00 London | 2703 | 6.66 | 0.83 | 136 |
| ny_opening_drive | NY first 30 min (09:30-10:00) broken 10:00-12:00, out by 14:00 New York | 2666 | 4.48 | 0.83 | 172 |

## All 24 rules on 2014-2024 (0 profitable after expensive costs)

'Edge $/oz' is the average mid-price gain per trade with no spread and no costs (|t| above ~2 suggests a real effect).

| Plan | Rule | Trades | Win % | Net $ | $/day | Worst day $ | Max DD $ | PF | Net $ at 2x | Edge $/oz | t | Hold min | Stop/target/time |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| london_asia_break | time-exit/trend+cond | 1026 | 27% | -5,504 | -2.04 | -85 | 5,818 | 0.73 | -7,828 | -0.10 | -0.5 | 310 | 701/0/325 |
| london_asia_break | time-exit/trend | 1071 | 26% | -5,556 | -2.06 | -85 | 5,870 | 0.74 | -8,601 | -0.11 | -0.5 | 311 | 733/0/338 |
| london_asia_break | 3R/trend+cond | 1026 | 28% | -6,291 | -2.33 | -85 | 6,700 | 0.69 | -8,559 | -0.18 | -0.9 | 282 | 692/123/211 |
| london_asia_break | 3R/trend | 1071 | 28% | -6,342 | -2.35 | -85 | 6,751 | 0.70 | -9,198 | -0.14 | -0.7 | 280 | 721/133/217 |
| london_asia_break | 2R/trend+cond | 1026 | 31% | -6,417 | -2.37 | -85 | 6,729 | 0.67 | -8,550 | -0.09 | -0.5 | 240 | 668/225/133 |
| london_asia_break | 2R/trend | 1071 | 31% | -6,540 | -2.42 | -85 | 6,900 | 0.68 | -9,509 | -0.08 | -0.4 | 236 | 695/238/138 |
| ny_opening_drive | 3R/trend+cond | 1208 | 30% | -8,500 | -3.19 | -33 | 8,783 | 0.61 | -8,256 | +0.04 | +0.3 | 72 | 705/95/408 |
| ny_opening_drive | time-exit/trend+cond | 1208 | 30% | -9,064 | -3.40 | -33 | 9,290 | 0.59 | -8,783 | -0.01 | -0.1 | 93 | 709/0/499 |
| ny_opening_drive | 2R/trend+cond | 1208 | 31% | -9,165 | -3.44 | -33 | 9,336 | 0.58 | -8,775 | -0.00 | -0.0 | 60 | 699/187/322 |
| ny_opening_drive | 3R/trend | 1335 | 29% | -10,067 | -3.78 | -33 | 10,320 | 0.59 | -13,682 | +0.08 | +0.6 | 68 | 797/109/429 |
| london_asia_break | time-exit/cond | 1975 | 27% | -10,469 | -3.87 | -120 | 11,096 | 0.73 | -14,442 | +0.18 | +1.0 | 325 | 1323/0/652 |
| london_asia_break | time-exit/no-filter | 2083 | 27% | -10,578 | -3.91 | -120 | 11,163 | 0.74 | -16,020 | +0.18 | +1.1 | 324 | 1399/0/684 |
| ny_opening_drive | time-exit/trend | 1335 | 29% | -10,643 | -3.99 | -33 | 10,840 | 0.57 | -14,363 | +0.04 | +0.3 | 84 | 802/0/533 |
| ny_opening_drive | 2R/trend | 1335 | 30% | -10,647 | -3.99 | -33 | 10,789 | 0.56 | -14,418 | +0.06 | +0.5 | 54 | 786/211/338 |
| london_asia_break | 3R/cond | 1975 | 28% | -11,191 | -4.14 | -120 | 11,558 | 0.71 | -15,248 | +0.07 | +0.5 | 294 | 1303/241/431 |
| london_asia_break | 3R/no-filter | 2083 | 28% | -11,411 | -4.22 | -120 | 11,907 | 0.72 | -16,657 | +0.11 | +0.7 | 288 | 1372/263/448 |
| london_asia_break | 2R/cond | 1975 | 31% | -12,011 | -4.44 | -120 | 12,260 | 0.68 | -16,001 | +0.07 | +0.5 | 251 | 1263/429/283 |
| london_asia_break | 2R/no-filter | 2083 | 31% | -12,453 | -4.61 | -120 | 12,833 | 0.68 | -17,835 | +0.07 | +0.5 | 247 | 1328/458/297 |
| ny_opening_drive | 3R/cond | 2234 | 31% | -14,257 | -5.35 | -33 | 14,693 | 0.64 | -14,235 | +0.12 | +1.2 | 78 | 1301/188/745 |
| ny_opening_drive | 2R/cond | 2234 | 32% | -14,769 | -5.54 | -33 | 15,048 | 0.63 | -15,094 | +0.10 | +1.1 | 58 | 1282/385/567 |
| ny_opening_drive | time-exit/cond | 2234 | 31% | -15,007 | -5.63 | -33 | 15,313 | 0.63 | -15,054 | +0.08 | +0.8 | 101 | 1307/0/927 |
| ny_opening_drive | 3R/no-filter | 2491 | 30% | -17,658 | -6.62 | -33 | 17,932 | 0.61 | -24,602 | +0.12 | +1.2 | 69 | 1486/213/792 |
| ny_opening_drive | 2R/no-filter | 2491 | 32% | -18,077 | -6.78 | -33 | 18,227 | 0.60 | -25,615 | +0.11 | +1.2 | 53 | 1461/427/603 |
| ny_opening_drive | time-exit/no-filter | 2491 | 30% | -18,400 | -6.90 | -33 | 18,548 | 0.60 | -25,701 | +0.09 | +0.8 | 89 | 1493/0/998 |

Net $ per year for the top 5:

| Plan / rule | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| london_asia_break time-exit/trend+cond | -352 | -533 | -1,258 | -593 | -194 | -668 | -279 | 238 | -771 | -922 | -172 |
| london_asia_break time-exit/trend | -470 | -405 | -1,236 | -344 | -194 | -591 | -388 | 162 | -850 | -981 | -258 |
| london_asia_break 3R/trend+cond | -307 | -777 | -1,346 | -666 | -209 | -721 | -616 | 93 | -973 | -661 | -108 |
| london_asia_break 3R/trend | -425 | -706 | -1,336 | -519 | -209 | -715 | -583 | 16 | -1,052 | -720 | -94 |
| london_asia_break 2R/trend+cond | -306 | -861 | -1,030 | -746 | -495 | -573 | -601 | -334 | -655 | -564 | -254 |

## First check on 2025 (rules picked on 2014-2024, positive at 2x)

| Plan | Rule | Trades | Win % | Net $ | $/day | Worst day $ | Max DD $ | Net $ at 2x |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| (none: no rule was profitable at 2x on 2014-2024) | | | | | | | | |
