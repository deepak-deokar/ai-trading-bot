# XAUUSD same-day session breakouts held for hours (step 2b)

$3,000 account, $30 risk (1%) per trade, at most one trade per plan per day, always closed the same day. Expensive costs: recorded bid/ask + $0.20 extra spread, $0.10 slippage per fill, $8/lot commission; '2x' doubles all three. Stop at the middle of the reference range. Development 2014-2024; 2025 shown only for rules positive at 2x on development; 2026 not loaded.

## Plans

| Plan | Rules | Days | Median range $ | Round-trip cost $/oz | Skipped days |
| --- | --- | ---: | ---: | ---: | ---: |
| london_asia_break | Asian range (00:00-07:00 London) broken 07:00-10:00, out by 16:00 London | 2702 | 6.49 | 0.83 | 138 |
| ny_opening_drive | NY first 30 min (09:30-10:00) broken 10:00-12:00, out by 14:00 New York | 2690 | 4.27 | 0.83 | 147 |

## All 24 rules on 2014-2024 (0 profitable after expensive costs)

'Edge $/oz' is the average mid-price gain per trade with no spread and no costs (|t| above ~2 suggests a real effect).

| Plan | Rule | Trades | Win % | Net $ | $/day | Worst day $ | Max DD $ | PF | Net $ at 2x | Edge $/oz | t | Hold min | Stop/target/time |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| london_asia_break | time-exit/trend | 1048 | 29% | -4,956 | -1.83 | -85 | 5,480 | 0.76 | -7,954 | +0.03 | +0.1 | 314 | 695/0/353 |
| london_asia_break | 3R/trend | 1048 | 30% | -5,096 | -1.89 | -85 | 5,478 | 0.74 | -7,943 | -0.00 | -0.0 | 273 | 682/133/233 |
| london_asia_break | 3R/trend+cond | 1002 | 30% | -5,151 | -1.91 | -85 | 5,521 | 0.73 | -7,337 | -0.04 | -0.2 | 278 | 655/123/224 |
| london_asia_break | time-exit/trend+cond | 1002 | 28% | -5,158 | -1.91 | -85 | 5,668 | 0.74 | -7,273 | +0.01 | +0.1 | 312 | 667/0/335 |
| london_asia_break | 2R/trend+cond | 1002 | 32% | -5,996 | -2.22 | -85 | 6,195 | 0.68 | -8,045 | -0.10 | -0.6 | 241 | 641/211/150 |
| london_asia_break | 2R/trend | 1048 | 32% | -6,204 | -2.30 | -85 | 6,416 | 0.68 | -8,856 | -0.09 | -0.5 | 237 | 668/222/158 |
| ny_opening_drive | 2R/trend+cond | 1148 | 32% | -8,248 | -3.07 | -33 | 8,509 | 0.61 | -8,545 | +0.05 | +0.4 | 47 | 701/213/234 |
| ny_opening_drive | 3R/trend+cond | 1148 | 30% | -8,485 | -3.15 | -33 | 8,785 | 0.61 | -8,281 | +0.06 | +0.4 | 58 | 716/105/327 |
| ny_opening_drive | time-exit/trend+cond | 1148 | 29% | -8,984 | -3.34 | -33 | 9,148 | 0.59 | -9,006 | -0.01 | -0.1 | 68 | 726/0/422 |
| london_asia_break | time-exit/no-filter | 2052 | 29% | -9,524 | -3.52 | -85 | 10,196 | 0.76 | -15,154 | +0.28 | +1.7 | 324 | 1342/0/710 |
| london_asia_break | time-exit/cond | 1948 | 29% | -10,235 | -3.79 | -85 | 10,860 | 0.73 | -13,957 | +0.22 | +1.3 | 322 | 1279/0/669 |
| london_asia_break | 3R/no-filter | 2052 | 30% | -10,454 | -3.87 | -85 | 10,824 | 0.73 | -15,549 | +0.16 | +1.1 | 282 | 1322/251/479 |
| ny_opening_drive | 2R/trend | 1322 | 30% | -10,522 | -3.91 | -33 | 10,663 | 0.58 | -14,862 | +0.07 | +0.6 | 42 | 821/238/263 |
| london_asia_break | 3R/cond | 1948 | 30% | -10,534 | -3.90 | -85 | 10,907 | 0.72 | -14,103 | +0.12 | +0.8 | 287 | 1261/229/458 |
| ny_opening_drive | 3R/trend | 1322 | 28% | -11,324 | -4.21 | -33 | 11,522 | 0.56 | -14,749 | +0.07 | +0.5 | 54 | 845/114/363 |
| london_asia_break | 2R/cond | 1948 | 32% | -11,684 | -4.32 | -85 | 11,981 | 0.68 | -15,431 | +0.06 | +0.4 | 244 | 1230/411/307 |
| ny_opening_drive | time-exit/trend | 1322 | 27% | -12,067 | -4.49 | -33 | 12,169 | 0.54 | -15,622 | -0.03 | -0.2 | 62 | 858/0/464 |
| london_asia_break | 2R/no-filter | 2052 | 32% | -12,180 | -4.51 | -85 | 12,465 | 0.68 | -17,289 | +0.07 | +0.6 | 240 | 1291/436/325 |
| ny_opening_drive | 3R/cond | 2184 | 29% | -15,308 | -5.69 | -33 | 15,718 | 0.63 | -14,679 | +0.09 | +0.9 | 54 | 1378/218/588 |
| ny_opening_drive | time-exit/cond | 2184 | 28% | -16,001 | -5.95 | -33 | 16,499 | 0.62 | -15,842 | +0.06 | +0.5 | 65 | 1395/0/789 |
| ny_opening_drive | 2R/cond | 2184 | 31% | -16,054 | -5.97 | -33 | 16,350 | 0.61 | -15,544 | +0.05 | +0.6 | 44 | 1351/413/420 |
| ny_opening_drive | 3R/no-filter | 2546 | 28% | -21,183 | -7.87 | -33 | 21,298 | 0.58 | -28,017 | +0.06 | +0.6 | 49 | 1647/239/660 |
| ny_opening_drive | 2R/no-filter | 2546 | 30% | -21,308 | -7.92 | -33 | 21,377 | 0.56 | -28,782 | +0.03 | +0.3 | 41 | 1608/459/479 |
| ny_opening_drive | time-exit/no-filter | 2546 | 27% | -21,964 | -8.17 | -33 | 22,058 | 0.57 | -29,035 | +0.00 | +0.0 | 57 | 1668/0/878 |

Net $ per year for the top 5:

| Plan / rule | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| london_asia_break time-exit/trend | -373 | -663 | -789 | -329 | -260 | -469 | -26 | -88 | -866 | -934 | -159 |
| london_asia_break 3R/trend | -418 | -596 | -757 | -351 | -235 | -501 | -241 | -148 | -815 | -714 | -320 |
| london_asia_break 3R/trend+cond | -347 | -696 | -803 | -465 | -205 | -571 | -282 | -102 | -765 | -654 | -260 |
| london_asia_break time-exit/trend+cond | -302 | -801 | -846 | -535 | -230 | -648 | 36 | -41 | -816 | -875 | -100 |
| london_asia_break 2R/trend+cond | -397 | -933 | -629 | -592 | -455 | -662 | -315 | -572 | -575 | -483 | -382 |

## First check on 2025 (rules picked on 2014-2024, positive at 2x)

| Plan | Rule | Trades | Win % | Net $ | $/day | Worst day $ | Max DD $ | Net $ at 2x |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| (none: no rule was profitable at 2x on 2014-2024) | | | | | | | | |
