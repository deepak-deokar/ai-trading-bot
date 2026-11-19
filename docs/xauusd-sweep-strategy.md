# YouTube 'daily zone + liquidity sweep' gold strategy, backtested

Source: *Gold Trading Strategy That Every Trader Should Know!* (The Trading School). Previous day's upper wick = supply (sells only), lower wick = demand (buys only), mother candle if inside day. On 15-minute candles: a candle sweeps the previous candle's high/low inside the zone and closes back; enter when a later candle closes beyond the sweep candle's other end; stop beyond the sweep extreme; fixed R target; closed by 16:45 New York. Exact rules and assumptions: `src/trading_bot/backtesting/sweep_strategy.py`.

$3,000 account, $30 risk (1%) per trade, expensive costs (recorded bid/ask + $0.20 extra spread, $0.10 slippage per fill, $8/lot); 2x doubles them. Development 2014-2024; 2025 only for variants positive at 2x; 2026 not loaded.

## 2014-2024

| Variant | Trades | Per day | Win % | Net $ | $/day | Worst day $ | Max DD $ | PF | Net $ at 2x | Edge before costs $/oz | t | In profit after 15 min |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2R/close-stop | 8,193 | 2.89 | 36% | -82,336 | -29.06 | -319 | 82,404 | 0.58 | -101,894 | -0.06 | -1.2 | 48% |
| 2R/touch-stop | 9,202 | 3.25 | 28% | -83,332 | -29.41 | -230 | 83,350 | 0.54 | -106,805 | +0.04 | +0.9 | 48% |
| 3R/close-stop | 7,572 | 2.67 | 31% | -75,231 | -26.56 | -319 | 75,314 | 0.62 | -94,705 | -0.04 | -0.7 | 47% |
| 3R/touch-stop | 8,649 | 3.05 | 24% | -77,609 | -27.39 | -230 | 77,609 | 0.57 | -103,091 | +0.09 | +1.6 | 48% |

Exits (stop / target / end of day), losses worse than 1.5R, median hold:

- 2R/close-stop: 4,427 / 2,060 / 1,706; 1147 trades lost more than $45; median hold 165 min
- 2R/touch-stop: 5,908 / 1,736 / 1,558; 9 trades lost more than $45; median hold 108 min
- 3R/close-stop: 4,390 / 1,346 / 1,836; 1179 trades lost more than $45; median hold 195 min
- 3R/touch-stop: 5,855 / 1,100 / 1,694; 11 trades lost more than $45; median hold 122 min

Net $ per year:

| Variant | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2R/close-stop | -7,808 | -8,249 | -8,194 | -8,962 | -9,106 | -8,611 | -5,613 | -7,637 | -5,565 | -4,746 | -7,844 |
| 2R/touch-stop | -8,914 | -8,165 | -8,027 | -10,124 | -9,755 | -9,661 | -6,016 | -7,049 | -5,383 | -4,446 | -5,792 |
| 3R/close-stop | -6,986 | -7,914 | -7,146 | -8,282 | -6,685 | -8,347 | -4,781 | -7,459 | -4,816 | -5,458 | -7,357 |
| 3R/touch-stop | -8,219 | -8,089 | -7,049 | -9,733 | -8,399 | -8,706 | -5,068 | -7,508 | -4,589 | -5,010 | -5,237 |

## 2025 check (variants positive at 2x on 2014-2024)

| Variant | Trades | Win % | Net $ | $/day | Worst day $ | Max DD $ | Net $ at 2x |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| (none: no variant was profitable at 2x on 2014-2024) | | | | | | | |
