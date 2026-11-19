# XAUUSD 30-minute session windows (step 2)

$3,000 account, $30 risk (1%) per trade, at most one trade per window per day, everything closed by the window's end. Expensive costs: recorded bid/ask + $0.20 extra spread, $0.10 slippage per fill, $8/lot commission; '2x' doubles all three. Development 2014-2024; 2025 shown only for rules picked on development data; 2026 not loaded.

## 1. How much gold moves in each window (2014-2024 medians)

| Window | Days | 30-min range $ | Open→close move $ | Entry spread $ | Round-trip cost $/oz | Range ÷ cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Tokyo 09:00 | 2443 | 1.47 | 0.60 | 0.35 | 0.83 | 1.8 |
| London 08:00 | 2823 | 2.50 | 1.04 | 0.35 | 0.83 | 3.0 |
| New York 08:30 | 2719 | 2.75 | 1.12 | 0.35 | 0.83 | 3.3 |
| New York 09:30 | 2732 | 4.25 | 1.70 | 0.35 | 0.83 | 5.1 |
| London 15:00 | 2723 | 3.89 | 1.51 | 0.35 | 0.83 | 4.7 |

Range ÷ cost by year:

| Window | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tokyo 09:00 | 1.4 | 1.5 | 2.0 | 1.3 | 1.2 | 1.3 | 2.4 | 1.7 | 1.9 | 2.1 | 2.1 | 3.7 |
| London 08:00 | 1.9 | 2.2 | 2.5 | 1.9 | 2.0 | 2.6 | 4.5 | 3.8 | 3.8 | 3.8 | 4.7 | 7.2 |
| New York 08:30 | 2.4 | 2.7 | 2.7 | 2.1 | 2.1 | 2.8 | 5.0 | 4.3 | 4.7 | 4.1 | 5.4 | 7.0 |
| New York 09:30 | 3.4 | 4.1 | 4.2 | 3.3 | 3.0 | 3.9 | 6.9 | 7.1 | 7.1 | 7.0 | 8.2 | 9.7 |
| London 15:00 | 3.0 | 4.2 | 4.2 | 2.8 | 3.0 | 4.0 | 6.8 | 6.0 | 6.2 | 5.8 | 7.8 | 9.7 |

## 2. Edge before any costs (mid price, time exit, all days, 2014-2024)

Average gain per ounce per trade if there were no spread and no costs. |t| above ~2 suggests a real but small effect.

| Window | Breakout $/oz | t | Momentum $/oz | t | Round-trip cost $/oz |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tokyo 09:00 | -0.01 | -0.5 | -0.02 | -1.4 | 0.83 |
| London 08:00 | +0.04 | +1.0 | +0.04 | +1.6 | 0.83 |
| New York 08:30 | -0.08 | -1.5 | +0.04 | +1.2 | 0.83 |
| New York 09:30 | +0.05 | +0.7 | +0.10 | +1.9 | 0.83 |
| London 15:00 | -0.06 | -0.9 | +0.01 | +0.2 | 0.83 |

## 3. Rule grid on 2014-2024 (0 of 60 rules profitable after expensive costs)

Top 15 by net profit:

| Window | Rule | Trades | Win % | Net $ | $/window-day | Worst day $ | Max DD $ | PF | Net $ at 2x |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| asia_open | orb/1R/filter | 652 | 16% | -8,265 | -3.38 | -34 | 8,265 | 0.11 | -3,694 |
| asia_open | orb/time-exit/filter | 652 | 16% | -8,295 | -3.40 | -34 | 8,295 | 0.12 | -3,717 |
| asia_open | orb/2R/filter | 652 | 16% | -8,301 | -3.40 | -34 | 8,301 | 0.11 | -3,737 |
| london_fix | orb/time-exit/filter | 1420 | 27% | -10,122 | -3.72 | -31 | 10,299 | 0.35 | -11,620 |
| london_fix | orb/2R/filter | 1420 | 27% | -10,126 | -3.72 | -31 | 10,357 | 0.35 | -11,590 |
| london_fix | orb/1R/filter | 1420 | 28% | -10,133 | -3.72 | -31 | 10,297 | 0.34 | -11,612 |
| london_fix | orb/time-exit/all-days | 1564 | 27% | -11,409 | -4.19 | -31 | 11,540 | 0.34 | -15,312 |
| london_fix | orb/2R/all-days | 1564 | 27% | -11,417 | -4.19 | -31 | 11,564 | 0.34 | -15,279 |
| london_fix | orb/1R/all-days | 1564 | 28% | -11,505 | -4.22 | -31 | 11,635 | 0.33 | -15,376 |
| ny_open | orb/1R/filter | 1730 | 32% | -11,838 | -4.33 | -32 | 11,838 | 0.41 | -12,576 |
| ny_open | orb/2R/filter | 1730 | 30% | -12,165 | -4.45 | -32 | 12,165 | 0.41 | -12,950 |
| ny_open | orb/time-exit/filter | 1730 | 30% | -12,331 | -4.51 | -32 | 12,331 | 0.40 | -12,999 |
| ny_open | orb/1R/all-days | 1939 | 32% | -13,939 | -5.10 | -32 | 13,979 | 0.40 | -19,236 |
| ny_open | orb/2R/all-days | 1939 | 30% | -13,959 | -5.11 | -32 | 14,008 | 0.41 | -19,414 |
| ny_open | orb/time-exit/all-days | 1939 | 30% | -14,133 | -5.17 | -32 | 14,182 | 0.40 | -19,474 |

Net $ per year for the top 5:

| Window / rule | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| asia_open orb/1R/filter | -354 | -599 | -747 | -755 | -407 | -756 | -1,072 | -1,022 | -1,023 | -739 | -792 |
| asia_open orb/time-exit/filter | -368 | -593 | -727 | -755 | -418 | -756 | -1,117 | -1,037 | -1,020 | -706 | -799 |
| asia_open orb/2R/filter | -368 | -593 | -762 | -755 | -418 | -756 | -1,117 | -1,037 | -991 | -706 | -799 |
| london_fix orb/time-exit/filter | -926 | -974 | -1,030 | -1,338 | -1,693 | -1,428 | -393 | -755 | -547 | -451 | -587 |
| london_fix orb/2R/filter | -855 | -980 | -1,015 | -1,283 | -1,726 | -1,452 | -467 | -761 | -558 | -451 | -578 |

## 4. First check on 2025 (rules picked on 2014-2024, positive at 2x)

| Window | Rule | Trades | Win % | Net $ | $/window-day | Worst day $ | Max DD $ | Net $ at 2x |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| (none: no rule was profitable at 2x on 2014-2024) | | | | | | | | |

Incomplete windows skipped (feed holes, holidays): asia_open 392, london_open 13, us_data 113, ny_open 97, london_fix 110.
