# XAUUSD G2C3B — baseline causal features

Feature set: **xauusd-baseline-features-v1**. Pure API:
`calculate_xauusd(approved_batch)` in `features/xauusd.py`. It accepts the G2C3A
ApprovedResearchInputs batch, not raw ticks or ambiguous single-price candles.
Use `approved_research_inputs` to construct that batch from policy-bound data.
The engine does not itself authenticate database provenance or make excluded days
eligible. It revalidates typed inputs, completion cutoffs, ordering and predecessor
metadata. No raw parsing, database calls, labels or strategy logic.

## Numeric and architecture decision

The existing NSE feature engine explicitly uses NumPy float64 arrays, NaN during
warmup and float output maps. Its FeatureRow contract is unsuitable for exact
Decimal bid/ask inputs. This bounded engine lives alongside it, reuses DomainModel
and FeatureError, and follows its return, EMA-seeding and RSI conventions without
changing NSE code or wrapping XAUUSD in a fabricated midpoint OHLC candle.

Prices and derived values stay Decimal. Calculations run in a fresh local Decimal
context: precision 50, ROUND_HALF_EVEN, independent of caller settings. Endpoint
midpoints, side differences and spreads remain exact within QuoteBar precision.
Nonterminating ratios and recurrences are deterministically rounded to this
50-significant-digit convention; they are not claimed as exact rational arithmetic.
No float conversion is used. Output values are an immutable tuple of named typed
values with unavailable reasons; the complete original G2C3A input is retained.
Output also identifies dataset, policy key, canonical symbol, opening timestamp,
completion time, feature-set version and sequence reset reason.

## Feature definitions

All lookbacks count consecutive completed bars within the current sequence.
Let C be exact analytical midpoint close.

| Features | Definition/basis | First available observation |
| --- | --- | --- |
| mid_close | (bid_close + ask_close) / 2 | 1 |
| return_1, return_3, return_12 | C[t] / C[t-p] - 1 | p+1 |
| momentum_3, momentum_12 | C[t] - C[t-p] | p+1 |
| ema_12, ema_26 | seed with p-close arithmetic mean; alpha=2/(p+1), then alpha*C+(1-alpha)*previous EMA | p |
| ema_difference | ema_12 - ema_26, price units | 26 |
| rsi_14 | first 14 close changes seed mean positive/negative changes; Wilder update (13*previous+current)/14; 100*gains/(gains+losses) | 15 |
| bid_range, ask_range | respective side high minus low | 1 |
| bid_body, ask_body | respective side close minus open | 1 |
| spread_open, spread_close | ask minus bid at paired open/close observations | 1 |
| spread_change | spread_close - spread_open within this bar | 1 |
| relative_spread | spread_close / mid_close | 1 |
| tick_count | original observed tick count (Decimal in feature values; original integer retained in input) | 1 |

RSI is 50 when both smoothed gains/losses are zero, 100 for gains without losses,
and 0 for losses without gains. All midpoint closes are strictly positive by input
validation, so close-ratio denominators cannot be zero. No future return targets,
normalization or future-aware scaling. Analytical midpoint does not become an
execution fill: BUY/ASK and SELL/BID semantics remain unchanged.

Side-specific ATR and close-return volatility are **deferred** to keep this set
small. No midpoint high/low/ATR, exact intrabar spread extrema, volume indicators
or fabricated midpoint range. HistData tick count measures observed activity, not
global gold volume. The raw provider volume field is not consumed.

## Warmup, gaps and causality

Insufficient-history values are None with WARMUP, or GAP_WARMUP after a reset.
No early seed fabrication, backward fill, centered window or future normalization.
Every row uses its current completed bar and earlier bars only; availability is
T+5 minutes for opening label T. The batch cutoff is enforced again by the engine.

Every engine invocation starts fresh at DATASET_BOUNDARY. Time differences other
than five minutes trigger DISCONTINUITY and clear lag, EMA and RSI history. An
explicit unknown predecessor inside a batch also resets state. Inconsistent
predecessor metadata is rejected. The engine compares actual timestamps, so it
cannot compress a one-hour provider gap into one five-minute step. After a reset,
normal observation-based warmup applies again. No synthetic rows are emitted.

For V1, submit each approved source-day dataset separately. There is no state
carryover across calls, even if two dataset endpoints appear contiguous. Missing
or unapproved days therefore cannot silently bridge rolling history. Approval is
retrospective dataset selection as documented in G2C3A; per-row feature causality
does not establish that full-day eligibility was known live at each bar close.

## Tests and demonstration

Offline tests check exact side/spread/midpoint values, lag horizons, seed/warmup
boundaries, flat/falling/rising RSI, deterministic Decimal context, time-gap and
dataset resets, cutoff/order rejection and strong no-lookahead behavior. The latter
mutates all prices after K dramatically and verifies every output row through K
is identical; calculating the prefix alone also gives identical prefix rows.

The bounded demonstration reads only the already approved February 20, 2024 dataset
from PostgreSQL, adapts it through G2C3A, computes features in memory and records
aggregate evidence in `xauusd-baseline-feature-demo.json`. No feature rows are
persisted. No other research days or full-month feature datasets are generated.

Measured demo: **276 input bars, 276 output rows**, one dataset-start reset and
one discontinuity reset; 50 rows have at least one unavailable feature. Per-feature
unavailable counts: return_1=2; return_3/momentum_3=6 each;
return_12/momentum_12=24 each; ema_12=22; ema_26/ema_difference=50 each; rsi_14=28.
There are 106 WARMUP cells and 106 GAP_WARMUP cells. All exact current-bar features
are available immediately. Feature rows persisted: **zero**.

Verification actually run: full `pytest -q` **747 passed**, no skips, one existing
Starlette/AnyIO deprecation warning. Existing NSE feature/backtester and XAUUSD
regressions passed. Ruff passed; Black check passed (138 files unchanged); mypy
passed (81 source files). Alembic current **0007 (head)**; no schema drift.
Git status, working/staged diffs and whitespace checked. Four new files, no
existing files modified, nothing staged or committed. No dependency or migration
changes. Recommended commit: `feat: add causal XAUUSD baseline feature engine`.

Limitations: one versioned baseline, per-call/day resets, 50-digit rounded ratios,
retrospective eligibility selection, and no statistical/strategy performance claims.
Stopped at G2C3B; no full feature persistence or G2C3C work.
