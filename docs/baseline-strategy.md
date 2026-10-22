# Baseline Trend Momentum — Phase 5B-1

Stable registry name: `baseline_trend_momentum_v1`, version `1`.
This is a fixed reference strategy to validate the feature → strategy → intent →
backtester pipeline. **It is not claimed to be profitable.** No thresholds were
optimized. No ML, broker access or production risk engine is involved.

## Rules and defaults

Entry requires all existing canonical Phase 3 features:
`ema_10`, `ema_20`, `momentum_5`, `rsi_14`, `atr_14`, `volume_ratio`,
`session_progress`. Null, missing, non-finite or unavailable/warm-up entry values
produce no trade. The strategy calculates no indicators itself.

| Parameter | Fixed research default |
| --- | --- |
| quantity | 10 whole shares |
| rsi_min / rsi_max | 55 / 70, inclusive |
| min_volume_ratio | 1.0 |
| entry_start_time | 09:30 Asia/Kolkata |
| last_entry_time | 14:45 Asia/Kolkata |
| stop_atr_multiple | 1.5 |
| target_atr_multiple | 2.0 |

All conditions must hold: EMA10 > EMA20, momentum5 > 0, RSI inside the configured
bounds, volume ratio at least its minimum, ATR > 0 and valid session progress.
The exact current time must be inside the inclusive configured entry window and
before the simulator's exit cutoff. There must be no held position or pending
entry/exit lifecycle. Quantity is fixed configuration, not risk-based sizing.

A qualified signal emits one MARKET BUY. Pending requests/orders prevent duplicate
entries. An unchanged true signal cannot repeatedly re-enter after an exit: a false
signal must re-arm entry, and the previous lifecycle must first finish. This is an
edge/lifecycle guard, not a tuned cooldown. References are deterministic and contain
symbol, lifecycle number, reason and sequence. No shorting or pyramiding is added.

## Actual-fill protection

The strategy freezes ATR at the causal entry decision and records entry feature
values in TradeIntent metadata. It does not treat the signal close as the fill.
After the simulator publishes a position, its actual weighted-average fill basis
and filled quantity determine:

```text
stop   = actual fill basis − entry ATR × stop_atr_multiple
target = actual fill basis + entry ATR × target_atr_multiple
```

Example: actual fill ₹1500, original ATR ₹10 → stop ₹1485 and target ₹1520.
Later ATR values do not change these levels. Metadata records original signal time,
entry reference, ATR, actual fill basis and resulting stop/target. Levels round to
the domain's 10 decimal places, HALF_UP; this is not exchange tick-size modeling.
A nonpositive computed stop fails clearly rather than inventing a protective price.

STOP_MARKET SELL and LIMIT SELL use Phase 4 OCO groups. A positive fill cancels the
sibling, including partial fills. Further entry fills cause protection to be
cancelled/replaced using the new filled quantity and weighted basis, with the same
original ATR. Once an exit starts, pending entry remainder is cancelled. A partially
filled stop retains its existing triggered market-like behavior when its remaining
quantity matches inventory; if quantities differ, a MARKET remainder request avoids
resetting the trigger. Residual target fills can lead to renewed protection for the
remaining inventory. No extra position is opened.

## Reversal, cancellations and session close

While LONG, available EMA10 <= EMA20 requests cancellation of pending entry and
protective orders, then one MARKET SELL for held quantity. A pending reversal exit
suppresses competing exits. A flat lifecycle cancels stale orders and cannot re-enter
in that same evaluation. Unknown pre-existing inventory without the strategy's
causal entry ATR fails closed; the strategy does not invent an ATR basis.

The framework now supplies immutable, symbol-local `OrderSnapshot` values and the
execution cutoff. `CancelIntent` requests cancellation through the simulator; it
cannot mutate accounting or cancel another symbol's/forced orders. The whole output
sequence is validated before any request is applied. Completed/cancelled targets are
safe no-ops. Cancellations produce existing ORDER/CANCELLED transitions and reasons.
No broker command or new risk authority is exposed.

At the execution cutoff the strategy stops issuing requests and leaves Phase 4's
forced liquidation in control. DAY expiry, capital checks, participation limits,
conservative OHLC ambiguity, costs and slippage remain unchanged.

## Timing and important limitations

Signals use only features available at evaluation. Ordinary requests, including
protective exits, retain Phase 4's **strictly later opening** rule and completed-bar
fill publication. For example, a 10:55 signal first qualifies at 11:00; its fill is
published at 11:05; protection requested then first qualifies at 11:10. The period
between entry publication and protection eligibility is therefore unprotected by
these orders. Cancel/replace likewise has a subsequent-bar eligibility delay.
This is explicitly a bar-based simulator, not an instantaneous broker bracket.

OHLC ambiguity, gaps and liquidity are approximations already documented in
[backtesting](backtesting.md). A stop is not a guaranteed execution price. Reference
fees retain Phase 4's review/rounding/source warnings; no current broker-fee or
historical-rate verification was performed in this checkpoint. Groww remains
UNVERIFIED. An incomplete forced exit fails the run rather than retaining inventory.

State resets with each per-symbol/per-run factory instance. There is no cross-symbol
market state; shared account cash still imposes existing capital limits. No warm-up
values are replaced with zero. Missing later entry features do not suppress protection
for an existing position, which uses frozen entry ATR; EMA reversal requires available
EMAs. This avoids abandoning protection during an unavailable-feature interval.

## Configuration and reproducibility

Use `config/strategy_baseline_trend_momentum_v1.yaml`, or the named default:

```sh
python -m trading_bot.backtesting.run \
  --symbol RELIANCE --source local --timeframe 5minute --adjustment RAW \
  --start '2026-01-05T09:15:00+05:30' --end '2026-01-05T15:30:00+05:30' \
  --starting-capital 200000 --feature-set-key '<generated-key>' \
  --strategy-config config/strategy_baseline_trend_momentum_v1.yaml \
  --cost-model groww_nse_intraday_reference_v1 --slippage-bps 5
```

Typed parameters reject invalid quantity, RSI ordering/bounds, negative volume
threshold, nonpositive multipliers and invalid/reversed local-time windows.
Canonical identity includes every validated parameter and implementation/version.
Equivalent decimal spellings normalize identically; changed RSI or ATR multipliers
change identity. JSON intent metadata is additive; older records without it still
load with an empty default. No new schema migration is required. Empty metadata is omitted when serializing legacy intents, preserving their
previous payload and identity inputs. Numerical Phase 4 execution is unchanged.

## One-session mechanics demonstration

```sh
python scripts/demonstrate_phase5b1.py
```

With DATABASE_URL configured and PYTHONPATH=src, this imports the committed synthetic
75-bar RELIANCE session, computes the real Phase 3 baseline features, runs two identical
backtests and checks persistence/determinism in a disposable PostgreSQL schema.
The fixed rising/alternating path completes warm-up; one artificial opening gap
separates the signal close from the actual fill. It demonstrates one entry, protective
stop exit and OCO cancellation. This is fixture construction for mechanics, not a
parameter search or performance selection. No broad backtest was run.

See [verification and actual worked output](phase5b1-verification.md) and the compact
[demonstration evidence](phase5b1-demonstration.json).
**SIMULATED BASELINE TEST OUTPUT — NOT PROFITABILITY EVIDENCE.**
Phase 5B-2 has not begun.
