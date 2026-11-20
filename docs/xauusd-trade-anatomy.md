# XAUUSD trade anatomy: where do the losses come from? (2014-2024)

Every trade of four step-2b rules, split into the price move before costs and each cost. MFE/MAE = furthest the mid price went in our favour / against us between entry and exit; R = distance from entry to the stop. Full per-trade logs (entry/exit time, prices, costs) are in `docs/trade-logs/*.csv`.

## Money: before and after costs ($3,000 account, $30 risk per trade)

| | london_asia_break<br>time-exit/no-filter | london_asia_break<br>time-exit/trend | ny_opening_drive<br>time-exit/no-filter | ny_opening_drive<br>2R/trend+cond |
| --- | ---: | ---: | ---: | ---: |
| Trades | 2,083 | 1,071 | 2,491 | 1,208 |
| Gross result before costs $ | 2,626 | 1,267 | 1,968 | 122 |
| Recorded spread $ | 5,690 | 2,927 | 8,777 | 3,969 |
| Extra spread + slippage $ | 6,261 | 3,247 | 9,659 | 4,432 |
| Commission $ | 1,252 | 649 | 1,932 | 886 |
| Net result $ | -10,578 | -5,557 | -18,401 | -9,166 |
| Win rate before costs | 28% | 28% | 34% | 36% |
| Win rate after costs | 27% | 26% | 30% | 31% |
| Avg gross move per trade $/oz | +0.14 | -0.10 | +0.10 | -0.01 |
| Avg total cost per trade $/oz | 0.85 | 0.85 | 0.85 | 0.85 |
| Avg risk (entry to stop) $/oz | 4.05 | 3.99 | 3.13 | 3.16 |

## Entry quality: did price go our way after we got in?

| | london_asia_break<br>time-exit/no-filter | london_asia_break<br>time-exit/trend | ny_opening_drive<br>time-exit/no-filter | ny_opening_drive<br>2R/trend+cond |
| --- | ---: | ---: | ---: | ---: |
| Avg mid move 5 min after entry $/oz | +0.01 | -0.01 | +0.02 | -0.02 |
| Trades in profit after 5 min | 45% | 46% | 45% | 45% |
| Avg mid move 15 min after entry $/oz | +0.01 | -0.06 | +0.02 | -0.01 |
| Trades in profit after 15 min | 46% | 46% | 46% | 46% |
| Losers never more than 0.25R in profit | 28% | 28% | 31% | 33% |

## Exit quality: did we give profits back?

| | london_asia_break<br>time-exit/no-filter | london_asia_break<br>time-exit/trend | ny_opening_drive<br>time-exit/no-filter | ny_opening_drive<br>2R/trend+cond |
| --- | ---: | ---: | ---: | ---: |
| Avg best point reached (MFE) R | 1.63 | 1.64 | 1.42 | 1.13 |
| Avg worst point reached (MAE) R | 0.87 | 0.88 | 0.81 | 0.80 |
| Trades that reached +0.5R | 65% | 65% | 64% | 64% |
| Trades that reached +1R | 48% | 48% | 46% | 45% |
| Trades that reached +2R | 28% | 28% | 25% | 23% |
| Losers that had been +1R in profit | 31% | 31% | 26% | 22% |

## By exit type (avg gross move $/oz, avg net $)

| Rule | Exit | Trades | Avg gross $/oz | Avg net $ |
| --- | --- | ---: | ---: | ---: |
| london_asia_break time-exit/no-filter | stop | 1399 | -3.62 | -28.58 |
| london_asia_break time-exit/no-filter | time_exit | 684 | +7.83 | +43.00 |
| london_asia_break time-exit/trend | stop | 733 | -3.69 | -28.50 |
| london_asia_break time-exit/trend | time_exit | 338 | +7.68 | +45.37 |
| ny_opening_drive time-exit/no-filter | stop | 1493 | -2.66 | -29.12 |
| ny_opening_drive time-exit/no-filter | time_exit | 998 | +4.24 | +25.13 |
| ny_opening_drive 2R/trend+cond | stop | 699 | -2.79 | -29.06 |
| ny_opening_drive 2R/trend+cond | target | 187 | +7.32 | +50.15 |
| ny_opening_drive 2R/trend+cond | time_exit | 322 | +1.78 | +5.51 |
