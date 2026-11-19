# XAUUSD trade anatomy: where do the losses come from? (2014-2024)

Every trade of four step-2b rules, split into the price move before costs and each cost. MFE/MAE = furthest the mid price went in our favour / against us between entry and exit; R = distance from entry to the stop. Full per-trade logs (entry/exit time, prices, costs) are in `docs/trade-logs/*.csv`.

## Money: before and after costs ($3,000 account, $30 risk per trade)

| | london_asia_break<br>time-exit/no-filter | london_asia_break<br>time-exit/trend | ny_opening_drive<br>time-exit/no-filter | ny_opening_drive<br>2R/trend+cond |
| --- | ---: | ---: | ---: | ---: |
| Trades | 2,052 | 1,048 | 2,546 | 1,148 |
| Gross result before costs $ | 3,864 | 1,871 | -623 | 622 |
| Recorded spread $ | 5,824 | 2,952 | 9,175 | 3,786 |
| Extra spread + slippage $ | 6,303 | 3,229 | 10,138 | 4,236 |
| Commission $ | 1,261 | 646 | 2,028 | 847 |
| Net result $ | -9,525 | -4,956 | -21,965 | -8,248 |
| Win rate before costs | 30% | 30% | 30% | 34% |
| Win rate after costs | 29% | 28% | 27% | 32% |
| Avg gross move per trade $/oz | +0.22 | +0.02 | +0.02 | +0.06 |
| Avg total cost per trade $/oz | 0.86 | 0.86 | 0.85 | 0.85 |
| Avg risk (entry to stop) $/oz | 3.95 | 3.94 | 3.10 | 3.10 |

## Entry quality: did price go our way after we got in?

| | london_asia_break<br>time-exit/no-filter | london_asia_break<br>time-exit/trend | ny_opening_drive<br>time-exit/no-filter | ny_opening_drive<br>2R/trend+cond |
| --- | ---: | ---: | ---: | ---: |
| Avg mid move 5 min after entry $/oz | -0.01 | -0.02 | -0.04 | -0.03 |
| Trades in profit after 5 min | 44% | 47% | 44% | 44% |
| Avg mid move 15 min after entry $/oz | +0.01 | -0.04 | -0.07 | -0.06 |
| Trades in profit after 15 min | 47% | 47% | 44% | 45% |
| Losers never more than 0.25R in profit | 29% | 29% | 32% | 32% |

## Exit quality: did we give profits back?

| | london_asia_break<br>time-exit/no-filter | london_asia_break<br>time-exit/trend | ny_opening_drive<br>time-exit/no-filter | ny_opening_drive<br>2R/trend+cond |
| --- | ---: | ---: | ---: | ---: |
| Avg best point reached (MFE) R | 1.60 | 1.61 | 1.46 | 1.17 |
| Avg worst point reached (MAE) R | 0.85 | 0.86 | 0.86 | 0.83 |
| Trades that reached +0.5R | 66% | 66% | 62% | 64% |
| Trades that reached +1R | 48% | 49% | 45% | 45% |
| Trades that reached +2R | 27% | 28% | 25% | 25% |
| Losers that had been +1R in profit | 29% | 31% | 27% | 22% |

## By exit type (avg gross move $/oz, avg net $)

| Rule | Exit | Trades | Avg gross $/oz | Avg net $ |
| --- | --- | ---: | ---: | ---: |
| london_asia_break time-exit/no-filter | stop | 1342 | -3.51 | -28.49 |
| london_asia_break time-exit/no-filter | time_exit | 710 | +7.27 | +40.44 |
| london_asia_break time-exit/trend | stop | 695 | -3.60 | -28.49 |
| london_asia_break time-exit/trend | time_exit | 353 | +7.13 | +42.05 |
| ny_opening_drive time-exit/no-filter | stop | 1668 | -2.58 | -29.23 |
| ny_opening_drive time-exit/no-filter | time_exit | 878 | +4.95 | +30.52 |
| ny_opening_drive 2R/trend+cond | stop | 701 | -2.76 | -29.10 |
| ny_opening_drive 2R/trend+cond | target | 213 | +7.37 | +50.03 |
| ny_opening_drive 2R/trend+cond | time_exit | 234 | +1.86 | +6.37 |
