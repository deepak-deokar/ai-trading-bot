# XAUUSD G2C4C3C — corrected frozen $500 historical backtest

Backtest version: `xauusd-first-historical-v1`. Strategy: `xauusd-trend-momentum-v1`.
Features: `xauusd-baseline-features-v1`. Identity: `c094daca28e51845621a767724d1eaf124031825ba56ef3d30cfa54540f9a211`.

The original $500, 1% risk, 12 continuous completed bars and 2R configuration
is unchanged. Synthetic contract: 10 ounces/unit, volume min 0.25/max 2/step
0.25, tick 0.01; fixed round-trip commission $1.25. All 49 approved February–
April 2024 days and 13,524 bars/features match frozen provenance hashes.

Only G2C4C3B changes execution semantics: observed entry/exit BID/ASK remains
exact, including off-grid boundary/gap prices. Generated stops/targets obey
the original contract grid. No strategy or parameter optimization occurred.

One position at a time; signals while open are ignored, never queued. Signals
use completed bars and enter no earlier than the next eligible opening.
LONG enters ASK/exits BID; SHORT enters BID/exits ASK. Ambiguous bars use
STOP_FIRST_CONSERVATIVE. Gap losses are not clipped to the risk budget.
Open positions close at the last observed executable close at approved
day/pre-gap segment boundaries; no position crosses a boundary. Realized
balance carries between months and supplies subsequent sizing equity.

## Overall results

| Metric | Value |
| --- | ---: |
| starting_balance | 500 |
| ending_balance | 418.345000000000 |
| signals_generated | 4084 |
| trade_plans_attempted | 3909 |
| trades_opened | 44 |
| trades_closed | 44 |
| rejected_plans | 3865 |
| ignored_signals | 175 |
| no_valid_volume | 3835 |
| long_trades | 22 |
| short_trades | 22 |
| wins | 9 |
| losses | 35 |
| breakeven | 0 |
| win_rate_percent | 20.454545454545454545454545454545454545454545454545 |
| gross_profit | 30.792500000000 |
| gross_loss | 112.447500000000 |
| gross_trading_pnl | -26.655000000000 |
| commissions | 55.00 |
| net_pnl | -81.655000000000 |
| return_percent | -16.331000000000 |
| average_win | 3.4213888888888888888888888888888888888888888888889 |
| average_loss | 3.2127857142857142857142857142857142857142857142857 |
| payoff_ratio | 1.0649290656627413780752005256774148923818769746870 |
| expectancy | -1.8557954545454545454545454545454545454545454545455 |
| profit_factor | 0.27383890259899064007648013517419240089819693634807 |
| max_drawdown_usd | 81.655000000000 |
| max_drawdown_percent | 16.331000000000 |
| largest_win | 4.712500000000 |
| largest_loss | -4.912500000000 |
| gap_risk_breaches | 0 |
| BUY signals | 2140 |
| SELL signals | 1944 |
| observed-market grid rejections | 0 |
| generated-level alignment rejections | 0 |

Rejections by reason:

- `MINIMUM_EXCEEDS_BUDGET`: 3835
- `NO_ENTRY_ACROSS_RESEARCH_BOUNDARY`: 30

Exit reasons:

- `CLOSED_END_OF_RESEARCH_DAY`: 15
- `CLOSED_STOP`: 22
- `CLOSED_STOP_AMBIGUOUS`: 0
- `CLOSED_TARGET`: 7

## Monthly results

| Month | Start | End | Trades | Wins | Losses | Net USD | Win % | Max DD USD | Max DD % | LONG | SHORT |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-02 | 500 | 434.362500000000 | 38 | 8 | 30 | -65.637500000000 | 21.052631578947368421052631578947368421052631578947 | 67.120000000000 | 13.424000000000 | 20 | 18 |
| 2024-03 | 434.362500000000 | 418.345000000000 | 6 | 1 | 5 | -16.017500000000 | 16.666666666666666666666666666666666666666666666667 | 16.167500000000 | 3.7208365697189378901642645493512844854866085555651 | 2 | 4 |
| 2024-04 | 418.345000000000 | 418.345000000000 | 0 | 0 | 0 | 0 | N/A | 0 | 0 | 0 | 0 |

## Comparison and verification

| Run | Plans attempted | Observed-grid rejections | Opened | Closed |
| --- | ---: | ---: | ---: | ---: |
| Frozen pre-fix | 4084 | 4047 | 0 | 0 |
| Corrected | 3909 | 0 | 44 | 44 |

This difference is a validation-semantics correction, not optimization. Every
directional signal is reconciled as rejected, opened/closed, or ignored while open.
Two full runs matched all records, decisions, metrics and content identity.
Generation timestamp is outside mathematical identity. The retained offline
end-to-end future-mutation regression verifies signal, entry, exit, P&L and
balance through a closed trade are unchanged by later data mutations.

Gross profit/loss are sums of positive/absolute negative net trade P&L after
commission; gross_trading_pnl separately reports before-commission P&L. Average
loss is a magnitude, largest loss is signed. Drawdown uses realized balance,
including initial balance; monthly peaks start at the month's opening balance.
Ratios are deterministic Decimal calculations, not annualized. No Sharpe is used.

Three months is insufficient production evidence. Contract specifications remain
synthetic, approved-day selection is retrospective, and OHLC fills are simulation.
No slippage, liquidity, swap, margin or leverage is modeled. No tuning follows
these results. Original $500 reports and $3,000 sensitivity files remain unchanged.

Reproduce with DATABASE_URL provided securely:

```sh
PYTHONPATH=src .venv/bin/python scripts/backtest_xauusd_corrected.py
```

## Verification actually run

- Full `pytest -q`: **925 passed**, including the existing end-to-end future-mutation
  causality test and NSE/backtester regressions. One existing Starlette/AnyIO warning.
- `ruff check .`: passed; `black --check .`: passed (169 files).
- `mypy`: passed (92 source files).
- `alembic current`: **0008 (head)**; `alembic check`: no schema drift.
- Exact entry-side prices and the realized balance chain were independently checked
  from the corrected report. All entered trades have grid-valid generated levels.
- Frozen $500 report/configuration and both $3,000 report SHA-256 hashes are unchanged.
- Git status, working diff and staged diff reviewed. No commit or migration.

The corrected run lost **$81.655 (16.331%)**. No parameters were changed in response.
Zero rejections occurred for insufficient structure, invalid entry-relative stops,
generated-level alignment, or observed-market alignment. All 3,865 rejections are
explicitly accounted for above. April has no closed trades, so its win rate is N/A.
