# XAUUSD G2C4C4 — corrected frozen $3,000 sensitivity

Backtest `xauusd-first-historical-v1`. Mathematical identity:
`e50dd1a9c00c88ecb6e0e3fdd77c78a708456ac73e2d8417e873c6acf863c876`.

Only starting balance changed, from $500 to $3,000. Initial 1% risk budget is $30.
Subsequent sizing uses updated realized balance; balance carries between months.
Strategy xauusd-trend-momentum-v1 and features xauusd-baseline-features-v1 remain
unchanged, with 12 continuous completed bars and a 2R target. Synthetic contract:
10 ounces/unit, minimum 0.25, maximum 2, volume step 0.25, tick 0.01. Commission
is $1.25 round trip. All 49 approved February–April days and 13,524 bars/features
match the corrected $500 provenance. No strategy, stop/target, policy or execution
parameter changed. No old partial $3,000 report was used as configuration.

Observed market BID/ASK prices remain exact under G2C4C3B; generated stops/targets
remain grid-constrained. Entries follow completed signals at eligible next openings.
One position at a time; ignored signals are never queued. Boundary exits use the
last executable observation; ambiguous stop/target bars use stop first. Gap-through
losses are not clipped to planned risk. No historical bars or features were written.

## Overall results

| Metric | Value |
| --- | ---: |
| starting_balance | 3000 |
| ending_balance | 1911.280000000000 |
| signals_generated | 4084 |
| trade_plans_attempted | 633 |
| trades_opened | 309 |
| trades_closed | 309 |
| rejected_plans | 324 |
| ignored_signals | 3451 |
| no_valid_volume | 294 |
| long_trades | 159 |
| short_trades | 150 |
| wins | 101 |
| losses | 208 |
| breakeven | 0 |
| win_rate_percent | 32.686084142394822006472491909385113268608414239482 |
| gross_profit | 2394.832500000000 |
| gross_loss | 3483.552500000000 |
| gross_trading_pnl | -702.470000000000 |
| commissions | 386.25 |
| net_pnl | -1088.720000000000 |
| return_percent | -36.290666666666666666666666666666666666666666666667 |
| average_win | 23.711212871287128712871287128712871287128712871287 |
| average_loss | 16.747848557692307692307692307692307692307692307692 |
| payoff_ratio | 1.4157766467500411640924681694254004289364871857760 |
| expectancy | -3.5233656957928802588996763754045307443365695792880 |
| profit_factor | 0.68746846789304883448720810149983386212781348924697 |
| max_drawdown_usd | 1260.102500000000 |
| max_drawdown_percent | 40.926138388924209170769097108040276488790479275926 |
| largest_win | 53.0000000000 |
| largest_loss | -28.812500000000 |
| gap_risk_breaches | 0 |
| BUY | 2140 |
| SELL | 1944 |
| observed-market grid rejections | 0 |
| generated-level grid rejections | 0 |

Rejections by reason:

- `NO_ENTRY_ACROSS_RESEARCH_BOUNDARY`: 30
- `MINIMUM_EXCEEDS_BUDGET`: 294

Exit reasons:

- `CLOSED_STOP`: 160
- `CLOSED_TARGET`: 57
- `CLOSED_STOP_AMBIGUOUS`: 1
- `CLOSED_END_OF_RESEARCH_DAY`: 91

## Monthly results

| Month | Start | End | Trades | Wins | Losses | Breakeven | Net USD | Win % | DD USD | DD % | LONG | SHORT |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-02 | 3000 | 2626.032500000000 | 86 | 26 | 60 | 0 | -373.967500000000 | 30.232558139534883720930232558139534883720930232558 | 532.992500000000 | 17.310754335666095858433062382113484471661360504780 | 49 | 37 |
| 2024-03 | 2626.032500000000 | 2032.342500000000 | 99 | 26 | 73 | 0 | -593.690000000000 | 26.262626262626262626262626262626262626262626262626 | 605.552500000000 | 23.015664878403828136728942302393155571265409751639 | 53 | 46 |
| 2024-04 | 2032.342500000000 | 1911.280000000000 | 124 | 49 | 75 | 0 | -121.062500000000 | 39.516129032258064516129032258064516129032258064516 | 286.055000000000 | 13.589827641905630617790699884081105220150884594189 | 57 | 67 |

## Direct corrected-run comparison

| Metric | $500 | $3,000 |
| --- | ---: | ---: |
| trade_plans_attempted | 3909 | 633 |
| trades_opened | 44 | 309 |
| trades_closed | 44 | 309 |
| no_valid_volume | 3835 | 294 |
| ignored_signals | 175 | 3451 |
| wins | 9 | 101 |
| losses | 35 | 208 |
| win_rate_percent | 20.454545454545454545454545454545454545454545454545 | 32.686084142394822006472491909385113268608414239482 |
| net_pnl | -81.655000000000 | -1088.720000000000 |
| ending_balance | 418.345000000000 | 1911.280000000000 |
| expectancy | -1.8557954545454545454545454545454545454545454545455 | -3.5233656957928802588996763754045307443365695792880 |
| profit_factor | 0.27383890259899064007648013517419240089819693634807 | 0.68746846789304883448720810149983386212781348924697 |
| return_percent | -16.331000000000 | -36.290666666666666666666666666666666666666666666667 |
| max_drawdown_usd | 81.655000000000 | 1260.102500000000 |
| max_drawdown_percent | 16.331000000000 | 40.926138388924209170769097108040276488790479275926 |

The executable trade subset changes with sizing eligibility and position-open
signal blocking. Differences in win rate or expectancy do not isolate an account-size
effect on strategy quality. Neither run was optimized after results were observed.

Gross profit/loss sum positive/absolute negative **net** trade P&L after commission.
Before-commission P&L is reported separately as gross_trading_pnl. Average loss is
a positive magnitude; largest loss is signed. Drawdown uses realized balance, not
intratrade equity. Monthly drawdown begins at that month’s opening balance. No
annualization or Sharpe is computed.

## Determinism, causality and limitations

Two full runs matched complete records, fills, volumes, decisions, metrics and
content identity. Generation timestamp is outside mathematical identity. Independent
report checks verified exact entry sides, one-position chronology, signal accounting,
the realized balance chain and subsequent 1% risk budgets. All opened trades closed.
The existing end-to-end future-mutation regression is retained in the full suite.

Three months is insufficient for production conclusions. The contract is synthetic,
approved-day selection retrospective, and OHLC execution simulated. No slippage,
liquidity, swap, margin or leverage is modeled. Old partial $3,000 reports are not
performance evidence and remain untouched/untracked; corrected $500 reports remain
unchanged. No strategy tuning or next iteration is included.

Reproduction: use scripts/backtest_xauusd_corrected.py’s read-only loading and
two-run flow with a validated in-memory starting_balance=Decimal("3000") override
after checking the frozen $500 configuration; route outputs to these separate files.
The repository runner and configuration were not edited. The JSON retains full
configuration, source evidence, component hashes and all per-signal records.

## Verification actually run

- `pytest -q`: **925 passed**, including end-to-end future-mutation causality and
  NSE/backtester regressions; one existing Starlette/AnyIO deprecation warning.
- `ruff check .`: passed; `black --check .`: passed (169 files).
- `mypy`: passed (92 source files).
- `alembic current`: **0008 (head)**; `alembic check`: no schema drift.
- Protected report/configuration SHA-256 hashes remain unchanged. No repository
  source/configuration changes, database writes by the research run, or migration.
- Git status, working diff and staged diff inspected; nothing staged or committed.

This diagnostic lost **$1,088.72**, returning **−36.290666…%**. Maximum realized
balance drawdown was **$1,260.1025 (40.926138…%)**. Results were recorded without
changing any parameters. All 324 rejections are explicit: 294 minimum-volume risk
rejections and 30 research-boundary rejections; all other rejection counts are zero.
