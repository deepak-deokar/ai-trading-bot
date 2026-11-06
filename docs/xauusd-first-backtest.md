# XAUUSD G2C4C2 — first historical baseline backtest

This is an in-sample, unoptimized research run over the 49 previously approved
HistData source days in February–April 2024. Three months is insufficient
evidence for production use. These results are not proof of profitability.

Backtest: `xauusd-first-historical-v1`; strategy: `xauusd-trend-momentum-v1`;
features: `xauusd-baseline-features-v1`. Source dates: 2024-02-01
through 2024-04-30; 13524 persisted bars/features.

**No trades executed under the frozen configuration.** The flat balance
provides no executed-trade profitability evidence. Tick-grid incompatibility
and unaffordable minimum risk account for all non-boundary signals.

## Frozen research assumptions

Starting balance: $500; risk fraction: 0.01
(1%, research-only, no live default). Realized balance carries between months.
TEST_FIXTURE contract: 10 ounces/volume unit; minimum
0.25, maximum 2, step 0.25,
tick 0.01. Fixed round-trip commission: $1.25.
These are synthetic values, not verified broker or MT5 specifications.
The existing 0.01 entry grid is retained even where feed prices have finer
precision; off-grid entries are rejected, not rounded or tuned to increase trades.

Strategy thresholds are unchanged: BUY EMA12>EMA26, difference>0, momentum3>0,
RSI55–70; SELL mirrored trend/momentum and RSI30–45. Both require spread<=0.75
and relative spread<=0.0003. Structure is exactly 12 continuous bars; target 2R.
Config was written before observing performance. No parameter alternatives tested.

## Execution and selection policy

At each bar opening, a pending prior-bar signal is finalized using ASK for
LONG or BID for SHORT. G2C4C1 validates the original structure and aligns levels;
G2C4B5 performs entry sizing, central lifecycle entry and entry-bar monitoring.
G2C4B4 monitors subsequent completed bars unchanged. Stop/target evaluation
precedes any forced boundary close. Strategy decisions are evaluated only at
completion, after those exits; a new signal may be attempted after an exit
at that same completion, but may not enter until the next bar opens.

An open position blocks another signal. At a predeclared approved day/gap
boundary, remaining positions close at that bar's BID close (LONG) or ASK
close (SHORT), timestamped at completion, as CLOSED_END_OF_RESEARCH_DAY.
This label includes pre-gap research-segment closures. It is a modeled
last-observed close, not an exact tick timestamp or a broker market-close claim.
Signals at that boundary are rejected; no pending plan or position crosses
it. Boundary times come from the frozen dated gap policy, not a peek at the
next bar's prices. Unexpected missing bars abort the run. No bars are filled.

Approved-day selection itself is retrospective coverage filtering. These
results are conditional on the previously approved subset, not all calendar
days or a live availability guarantee. Indicators use persisted per-day/gap
resets. HistData is a research feed, not the future MT5 broker schedule/feed.
No slippage, liquidity limits, swap, financing, margin or leverage is modeled.

## Overall results

| Metric | Value |
| --- | ---: |
| starting_balance | 500.00 |
| ending_balance | 500.00 |
| signals_generated | 4084 |
| trade_plans_attempted | 4084 |
| trades_opened | 0 |
| trades_closed | 0 |
| rejected_plans | 4084 |
| ignored_signals | 0 |
| no_valid_volume | 7 |
| long_trades | 0 |
| short_trades | 0 |
| wins | 0 |
| losses | 0 |
| breakeven | 0 |
| win_rate_percent | — |
| gross_profit | 0.00 |
| gross_loss | 0.00 |
| gross_trading_pnl | 0.00 |
| commissions | 0.00 |
| net_pnl | 0.00 |
| return_percent | 0.00 |
| average_win | — |
| average_loss | — |
| payoff_ratio | — |
| expectancy | — |
| profit_factor | — |
| max_drawdown_usd | 0.00 |
| max_drawdown_percent | 0.00 |
| largest_win | — |
| largest_loss | — |
| gap_risk_breaches | 0 |

Rejections (all generated BUY/SELL signals are reconciled):

- `ENTRY_NOT_TICK_ALIGNED`: 4047
- `MINIMUM_EXCEEDS_BUDGET`: 7
- `NO_ENTRY_ACROSS_RESEARCH_BOUNDARY`: 30
- `SIGNAL_IGNORED_POSITION_OPEN`: 0

Exit reasons:

- `CLOSED_END_OF_RESEARCH_DAY`: 0
- `CLOSED_STOP`: 0
- `CLOSED_STOP_AMBIGUOUS`: 0
- `CLOSED_TARGET`: 0

## Monthly results (no balance reset)

| Month | Start | End | Trades | Wins | Losses | Net USD | Win % | DD USD | DD % | LONG | SHORT |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-02 | 500.00 | 500.00 | 0 | 0 | 0 | 0.00 | — | 0.00 | 0.00 | 0 | 0 |
| 2024-03 | 500.00 | 500.00 | 0 | 0 | 0 | 0.00 | — | 0.00 | 0.00 | 0 | 0 |
| 2024-04 | 500.00 | 500.00 | 0 | 0 | 0 | 0.00 | — | 0.00 | 0.00 | 0 | 0 |

## Definitions, causality and reproducibility

Wins/losses and gross profit/gross loss are sums of positive/absolute negative
**net trade P&L after commission**. Gross trading P&L separately reports the
before-commission sum. Average loss is a positive magnitude; largest loss is
signed. Profit factor and payoff ratio are null when their denominators are
zero; no infinity is fabricated. Expectancy is net P&L per closed trade.
Drawdown is realized balance below its running peak, including initial balance.
Monthly drawdown starts at that month's opening balance; overall drawdown
retains the full-period peak. Percentages/ratios use fixed 50-digit Decimal
reporting precision; balances and monetary sums use exact adaptive precision.
No Sharpe or annualized performance is reported.

Every BUY/SELL has a record: closed trade, rejection, or ignored-open signal.
NO_TRADE decisions also have timestamp/action/content-hash audit entries.
Trade records retain signal reasons, structural source identities, fills,
risk budget, projected stop risk, costs, realized balance and breach/ambiguity.
No gap-through loss is clipped to budget; nonpositive equity blocks new sizing.

Two exact runs matched full records, decisions, metrics and content identity:
`8e0c6cfc45a26b28df143208503828a599382834f7777b3ec851ff9ba71cb210`.
The generation timestamp is outside that mathematical identity. Approved
feature manifests were checked, persisted bar/feature pairs matched, policy
eligibility was rechecked, and database transactions were read-only.
Machine-readable inputs/provenance, per-signal records, decision audit and
monthly/overall metrics are in `xauusd-first-backtest.json`.

Reproduce with the development database URL provided securely:

```sh
PYTHONPATH=src .venv/bin/python scripts/backtest_xauusd_first.py
```

This baseline is sensitive to the synthetic contract, commission, tick
compatibility, approved-date selection and OHLC fill assumptions. The small
sample and rejections limit generalization. No thresholds were changed after
seeing results. No G2C4C3, trailing stops or ML work was performed.

## Verification actually run

- Full `pytest -q`: **912 passed**, no skips; one existing Starlette/AnyIO
  deprecation warning. Includes 13 new offline end-to-end/metrics scenarios and
  all existing strategy, planner, execution, sizing, protection, simulator and
  NSE/backtester regressions.
- Ruff passed; Black check passed (168 files); mypy passed (92 source files).
- Alembic current: **0008 (head)**; Alembic check: no new upgrade operations.
- Two final read-only historical runs matched exactly. Saved JSON result content
  independently hashes to the recorded report identity.
- The synthetic end-to-end test changes future bars/features after a closed
  trade and asserts identical earlier decisions, fills, P&L and realized balance.
  Synthetic tests cover nonzero trades and gaps; the actual frozen historical
  configuration opened zero trades and therefore supplies no executed-trade
  profitability evidence.
- Git status, working diff, staged diff and whitespace reviewed: six new files,
  no existing modifications, no staging or commit. No migrations, dependencies,
  broker operations or permanent trade ledger were added.

Recommended commit: `feat: run frozen XAUUSD historical baseline with full signal audit`.
Stopped at G2C4C2. No thresholds were optimized and G2C4C3 has not begun.
