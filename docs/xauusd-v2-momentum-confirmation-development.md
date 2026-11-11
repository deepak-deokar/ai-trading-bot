# G2C4D1 — DEVELOPMENT / IN-SAMPLE experiment

Pre-run hypothesis: V1 has negative expectancy and a high stop-out rate.
Requiring agreement between 3-bar and 12-bar momentum may reduce short-lived
directional entries. Improvement was not assumed; no threshold search occurred.

Candidate: `xauusd-trend-momentum-v2-long-confirmation`. Every V1 condition is retained. BUY additionally
requires momentum_12 > 0; SELL requires momentum_12 < 0. Zero/unavailable
values do not confirm. 'long-confirmation' refers to the longer lookback,
not a LONG-only strategy. Both directions remain enabled.

All other inputs remain frozen: $3,000 balance, 1% risk, 49 approved days,
13,524 bars, baseline-features-v1, 12-bar structural stop, 2R target,
10 ounces/unit, volumes 0.25–2 step 0.25, tick 0.01, $1.25 round-trip fee.
Observed market prices, generated grid levels, one position at a time,
boundary closures and protective execution are unchanged. No raw data writes.

## Signal study (completed before execution)

- v1_NO_TRADE: 9440
- v2_NO_TRADE: 9727
- v1_SELL: 1944
- v2_SELL: 1789
- MOMENTUM_12_NOT_CONFIRMED: 287
- opposite_sign: 286
- v1_BUY: 2140
- v2_BUY: 2008
- zero: 1

## V2 results

| Metric | Value |
| --- | ---: |
| starting_balance | 3000 |
| ending_balance | 2078.340000000000 |
| signals_generated | 3797 |
| trade_plans_attempted | 570 |
| trades_opened | 300 |
| trades_closed | 300 |
| rejected_plans | 270 |
| ignored_signals | 3227 |
| no_valid_volume | 243 |
| long_trades | 156 |
| short_trades | 144 |
| wins | 100 |
| losses | 200 |
| breakeven | 0 |
| win_rate_percent | 33.333333333333333333333333333333333333333333333333 |
| gross_profit | 2450.670000000000 |
| gross_loss | 3372.330000000000 |
| gross_trading_pnl | -546.660000000000 |
| commissions | 375.00 |
| net_pnl | -921.660000000000 |
| return_percent | -30.722000000000 |
| average_win | 24.506700000000 |
| average_loss | 16.861650000000 |
| payoff_ratio | 1.4533986887404257590449333250304685484516639830622 |
| expectancy | -3.072200000000 |
| profit_factor | 0.72669934437021287952246666251523427422583199153108 |
| max_drawdown_usd | 1087.530000000000 |
| max_drawdown_percent | 35.321256232811811102260741628484224013407091825425 |
| largest_win | 53.0000000000 |
| largest_loss | -28.812500000000 |
| gap_risk_breaches | 0 |
| mean net R | -0.1181239978872097659944823778 |
| median net R | -0.5545675869914588784939680765 |

Rejections:

- NO_ENTRY_ACROSS_RESEARCH_BOUNDARY: 27
- MINIMUM_EXCEEDS_BUDGET: 243

Exits:

- CLOSED_STOP: 151
- CLOSED_TARGET: 57
- CLOSED_STOP_AMBIGUOUS: 1
- CLOSED_END_OF_RESEARCH_DAY: 91

## V1 versus V2

| Metric | V1 | V2 |
| --- | ---: | ---: |
| signals_generated | 4084 | 3797 |
| trades_closed | 309 | 300 |
| win_rate_percent | 32.686084142394822006472491909385113268608414239482 | 33.333333333333333333333333333333333333333333333333 |
| expectancy | -3.5233656957928802588996763754045307443365695792880 | -3.072200000000 |
| profit_factor | 0.68746846789304883448720810149983386212781348924697 | 0.72669934437021287952246666251523427422583199153108 |
| net_pnl | -1088.720000000000 | -921.660000000000 |
| max_drawdown_usd | 1260.102500000000 | 1087.530000000000 |
| max_drawdown_percent | 40.926138388924209170769097108040276488790479275926 | 35.321256232811811102260741628484224013407091825425 |
| mean net R | -0.1416067437356247871521236837 | -0.1181239978872097659944823778 |
| stop rate including ambiguous % | 52.10355987055016181229773463 | 50.66666666666666666666666667 |
| target rate % | 18.44660194174757281553398058 | 19 |

R uses saved risk budget, not actual deployed stop loss. Gross profit/loss
sum positive/absolute negative net trade P&L; pre-commission P&L is separate.
All balances carry forward. Monthly metrics and complete signal records are in JSON.

V1 replay reproduced its frozen content identity exactly after strategy routing
was added. V2 ran twice with equal complete results and content identity:
`a876bb8b7e1c24d1e99a9d133e5be3619ee0332b127ee5f199d245e082fd3b9b`.
Generation time is excluded from mathematical identity. Original persisted feature
hashes and signal completion times were checked. Offline future-mutation tests
cover the V2 pipeline, including future momentum_12 changes. No V1 report changed.

This is development data already used for attribution; it is not independent
validation. Reduced trade count alone is not improvement. The contract is synthetic,
day selection retrospective and OHLC fills simulated. No slippage/liquidity model
or broker verification is added. No parameter was changed after seeing results.

Reproduce with DATABASE_URL provided securely:

```sh
PYTHONPATH=src .venv/bin/python scripts/backtest_xauusd_confirmation.py
```

## Assessment and verification

V2 remains negative before commission (−$546.66) and after commission (−$921.66).
Hit rate rises by 0.6472 percentage points; stop rate falls by 1.4369 points;
target rate rises by 0.5534 points. Mean R improves by approximately 0.02348R,
expectancy by $0.45117/trade, and drawdown falls by 5.6049 percentage points.
These are modest in-sample movements in the diagnosed failure modes, not evidence
of a validated edge or success based on fewer trades. There was no retuning.
The additional rule changes the signal population, position blocking and later
balance-dependent sizing; this is not a matched-trade causal decomposition.

- Signal rejections: 286 opposite-sign momentum_12, one zero; zero unavailable.
- Full pytest: **936 passed**, including 11 added candidate/sign/routing/causality
  cases, all existing V1 and NSE/backtester regressions; one existing deprecation warning.
- Ruff passed; Black passed (171 files); strict mypy passed (93 source files).
- Alembic current **0008 (head)**; check: no schema drift. No migration.
- Frozen V1 evaluator/configuration/reports retain their original SHA-256 hashes.
- Both old partial $3,000 files remain untouched and untracked.
- Git status, working diff, staged diff and whitespace reviewed; nothing staged
  or committed. The only existing production changes are explicit V2 routing and
  acceptance of its versioned decision model; execution calculations are unchanged.

Recommended commit: `feat: add frozen XAUUSD momentum confirmation experiment`.
Stopped at G2C4D1. No additional parameter, window or strategy version was tried.
