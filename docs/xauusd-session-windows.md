# XAUUSD 30-minute session windows (step 2)

$3,000 account, $30 risk (1%) per trade, at most one trade per window per day, everything closed by the window's end. Expensive costs: recorded bid/ask + $0.20 extra spread, $0.10 slippage per fill, $8/lot commission; '2x' doubles all three. Development 2014-2024; 2025 shown only for rules picked on development data; 2026 not loaded.

## 1. How much gold moves in each window (2014-2024 medians)

| Window | Days | 30-min range $ | Open→close move $ | Entry spread $ | Round-trip cost $/oz | Range ÷ cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Tokyo 09:00 | 2700 | 1.81 | 0.75 | 0.35 | 0.83 | 2.2 |
| London 08:00 | 2822 | 2.64 | 1.09 | 0.35 | 0.83 | 3.2 |
| New York 08:30 | 2735 | 4.08 | 1.62 | 0.39 | 0.87 | 4.7 |
| New York 09:30 | 2724 | 4.40 | 1.69 | 0.35 | 0.83 | 5.3 |
| London 15:00 | 2728 | 4.08 | 1.58 | 0.35 | 0.83 | 4.9 |

Range ÷ cost by year:

| Window | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tokyo 09:00 | 1.5 | 1.8 | 2.7 | 1.6 | 1.5 | 1.8 | 3.3 | 2.5 | 2.8 | 2.2 | 2.7 | 6.0 |
| London 08:00 | 2.1 | 2.5 | 2.9 | 1.9 | 2.2 | 2.8 | 4.8 | 4.0 | 4.5 | 3.8 | 4.6 | 6.9 |
| New York 08:30 | 3.4 | 4.1 | 4.0 | 2.9 | 2.8 | 3.7 | 6.3 | 6.6 | 6.5 | 6.2 | 7.6 | 7.3 |
| New York 09:30 | 3.1 | 4.0 | 4.3 | 3.2 | 3.0 | 4.0 | 8.1 | 7.5 | 7.7 | 7.3 | 9.3 | 12.3 |
| London 15:00 | 3.2 | 3.9 | 4.2 | 3.0 | 2.9 | 4.0 | 7.9 | 6.4 | 7.1 | 6.3 | 8.4 | 10.4 |

## 2. Edge before any costs (mid price, time exit, all days, 2014-2024)

Average gain per ounce per trade if there were no spread and no costs. |t| above ~2 suggests a real but small effect.

| Window | Breakout $/oz | t | Momentum $/oz | t | Round-trip cost $/oz |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tokyo 09:00 | -0.01 | -0.2 | -0.02 | -0.8 | 0.83 |
| London 08:00 | -0.10 | -2.6 | -0.01 | -0.3 | 0.83 |
| New York 08:30 | -0.07 | -1.0 | +0.03 | +0.6 | 0.87 |
| New York 09:30 | +0.04 | +0.6 | +0.10 | +1.8 | 0.83 |
| London 15:00 | +0.10 | +1.3 | -0.04 | -0.9 | 0.83 |

## 3. Rule grid on 2014-2024 (0 of 60 rules profitable after expensive costs)

Top 15 by net profit:

| Window | Rule | Trades | Win % | Net $ | $/window-day | Worst day $ | Max DD $ | PF | Net $ at 2x |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| london_fix | orb/time-exit/filter | 1498 | 31% | -8,940 | -3.28 | -31 | 9,117 | 0.43 | -10,663 |
| london_fix | orb/2R/filter | 1498 | 31% | -8,948 | -3.28 | -31 | 9,180 | 0.43 | -10,667 |
| london_fix | orb/1R/filter | 1498 | 32% | -9,157 | -3.36 | -31 | 9,321 | 0.41 | -10,754 |
| ny_open | orb/time-exit/filter | 1519 | 31% | -9,874 | -3.62 | -31 | 9,874 | 0.42 | -11,936 |
| ny_open | orb/2R/filter | 1519 | 31% | -9,949 | -3.65 | -31 | 9,949 | 0.42 | -11,924 |
| london_fix | orb/2R/all-days | 1622 | 30% | -10,260 | -3.76 | -32 | 10,407 | 0.41 | -14,398 |
| ny_open | orb/1R/filter | 1519 | 32% | -10,268 | -3.77 | -31 | 10,268 | 0.40 | -12,145 |
| london_fix | orb/time-exit/all-days | 1622 | 30% | -10,284 | -3.77 | -32 | 10,414 | 0.41 | -14,455 |
| london_fix | orb/1R/all-days | 1622 | 31% | -10,450 | -3.83 | -32 | 10,580 | 0.39 | -14,470 |
| asia_open | orb/time-exit/filter | 952 | 18% | -11,345 | -4.20 | -34 | 11,345 | 0.19 | -4,676 |
| asia_open | orb/2R/filter | 952 | 18% | -11,468 | -4.25 | -34 | 11,468 | 0.18 | -4,702 |
| asia_open | orb/1R/filter | 952 | 19% | -11,620 | -4.30 | -34 | 11,620 | 0.16 | -4,745 |
| ny_open | orb/time-exit/all-days | 1683 | 30% | -11,825 | -4.34 | -32 | 11,874 | 0.40 | -16,190 |
| ny_open | orb/2R/all-days | 1683 | 30% | -11,954 | -4.39 | -32 | 12,003 | 0.39 | -16,250 |
| ny_open | orb/1R/all-days | 1683 | 31% | -12,264 | -4.50 | -32 | 12,305 | 0.37 | -16,519 |

Net $ per year for the top 5:

| Window / rule | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| london_fix orb/time-exit/filter | -875 | -801 | -1,027 | -1,152 | -1,559 | -1,315 | -281 | -599 | -646 | -227 | -458 |
| london_fix orb/2R/filter | -820 | -836 | -980 | -1,155 | -1,555 | -1,331 | -317 | -601 | -670 | -246 | -438 |
| london_fix orb/1R/filter | -939 | -883 | -1,002 | -1,149 | -1,532 | -1,230 | -445 | -673 | -715 | -290 | -299 |
| ny_open orb/time-exit/filter | -827 | -572 | -1,095 | -1,555 | -1,460 | -1,035 | -904 | -313 | -891 | -215 | -1,008 |
| ny_open orb/2R/filter | -790 | -518 | -1,130 | -1,624 | -1,452 | -1,081 | -906 | -387 | -912 | -245 | -902 |

## 4. First check on 2025 (rules picked on 2014-2024, positive at 2x)

| Window | Rule | Trades | Win % | Net $ | $/window-day | Worst day $ | Max DD $ | Net $ at 2x |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| (none: no rule was profitable at 2x on 2014-2024) | | | | | | | | |

Incomplete windows skipped (feed holes, holidays): asia_open 136, london_open 13, us_data 93, ny_open 108, london_fix 101.
