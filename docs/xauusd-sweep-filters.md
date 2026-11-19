# Sweep strategy: intraday trend filter and moving stop

All versions use the video's rules with a 2R target and the stop counted on 15-minute candle close. Trend filter: sell only below the 20-hour moving average of hourly closes, buy only above. Moving stop: once 1R in profit, a normal (touch) stop trails 1R behind the best price. $3,000 account, $30 risk per trade, expensive costs; 2x doubles them. Rules fixed before running. Development 2014-2024; 2025 only for versions profitable at 2x; 2026 not loaded.

## 2014-2024

| Version | Trades | Win % | Avg win $ | Avg loss $ | Net $/trade | Net $ | PF | Net $ at 2x | Edge before costs $/oz | t | Green days |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1. As in the video | 8,193 | 36% | 39.12 | -37.26 | -10.05 | -82,336 | 0.58 | -101,894 | -0.062 | -1.2 | 38% |
| 2. + trend filter | 2,327 | 37% | 37.98 | -33.70 | -7.36 | -17,132 | 0.66 | -24,951 | +0.057 | +0.5 | 41% |
| 3. + moving stop | 9,062 | 41% | 24.14 | -34.19 | -9.99 | -90,528 | 0.50 | -113,462 | -0.023 | -0.6 | 35% |
| 4. Both | 2,449 | 42% | 25.65 | -30.82 | -7.12 | -17,426 | 0.60 | -25,116 | +0.084 | +0.9 | 43% |

Exits (stop / moving stop / target / end of day):

- 1. As in the video: 4,427 / 0 / 2,060 / 1,706; 52% of trades were 1R in profit at some point
- 2. + trend filter: 1,143 / 0 / 585 / 599; 49% of trades were 1R in profit at some point
- 3. + moving stop: 4,102 / 2,206 / 1,290 / 1,464; 52% of trades were 1R in profit at some point
- 4. Both: 1,021 / 524 / 391 / 513; 50% of trades were 1R in profit at some point

Net $ per year:

| Version | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1. As in the video | -7,808 | -8,249 | -8,194 | -8,962 | -9,106 | -8,611 | -5,613 | -7,637 | -5,565 | -4,746 | -7,844 |
| 2. + trend filter | -2,349 | -1,754 | -2,173 | -1,608 | -2,545 | -1,983 | -339 | -1,620 | -361 | -830 | -1,569 |
| 3. + moving stop | -9,192 | -9,321 | -8,817 | -10,394 | -10,370 | -10,095 | -6,331 | -8,111 | -5,359 | -5,220 | -7,317 |
| 4. Both | -2,766 | -1,867 | -1,984 | -1,853 | -2,252 | -1,711 | -938 | -1,620 | -499 | -673 | -1,262 |

## 2025 check (versions profitable at 2x on 2014-2024)

| Version | Trades | Win % | Net $ | Net $ at 2x |
| --- | ---: | ---: | ---: | ---: |
| (none: no version was profitable at 2x on 2014-2024) | | | | |
