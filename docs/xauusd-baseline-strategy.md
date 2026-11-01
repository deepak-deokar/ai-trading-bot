# XAUUSD G2C4A — transparent trend/momentum signals

Strategy version: **xauusd-trend-momentum-v1**. Required input feature version:
**xauusd-baseline-features-v1**, unchanged. This is signal research only: no orders,
positions, sizing, stops, targets, fills, monetary accounting or execution simulation.

## Architecture and thesis

Existing NSE strategies consume simulator contexts and return trade/cancel intents.
They assume NSE session and execution behavior, so this signal-only strategy is not
registered with that runtime. It reuses immutable DomainModel and generic Side
(BUY/SELL) while using None for NO_TRADE; action labels are exposed in uppercase.
The pure `evaluate_xauusd(row, as_of=...)` evaluates exactly one typed feature row
and cannot inspect another row. No strategies or execution backtester are modified.

Thesis: require a consistent midpoint-close trend and recent momentum, with RSI
confirmation but without directional extremes, and reject poor quoted spread
conditions. This deliberately simple baseline is not optimized. Thresholds below
were chosen before the full-dataset study and were not adjusted to its distribution
or any profitability result.

## Exact fixed rules

Required features: ema_12, ema_26, ema_difference, momentum_3, rsi_14, spread_close,
relative_spread. All are existing causal G2C3B features. Any absent/None feature or
non-null unavailable marker yields WARMUP_INCOMPLETE and NO_TRADE. Missing values
are never inferred. A row cannot be evaluated before its completion timestamp;
naive cutoff timestamps are rejected. Duplicate feature names and malformed
negative spread/out-of-range RSI values are rejected as invalid inputs.

Both spread conditions must hold (equality passes):

- `spread_close <= Decimal("0.75")`, in XAUUSD quote-price units;
- `relative_spread <= Decimal("0.0003")`, a dimensionless 3-basis-point cap.

These are explicit conservative research filters, not measured broker execution
costs or a universal gold spread rule. Only the paired closing spread is used;
no exact intrabar extrema are invented.

BUY requires all of:

- EMA12 > EMA26 and EMA difference > 0;
- momentum_3 > 0;
- **55 <= RSI14 <= 70**;
- both spread filters pass and all required features are available.

SELL requires all of:

- EMA12 < EMA26 and EMA difference < 0;
- momentum_3 < 0;
- **30 <= RSI14 <= 45**;
- both spread filters pass and all required features are available.

The RSI intervals are symmetric around 50. RSI > 70 blocks a BUY; RSI < 30 blocks
a SELL. This does not create a contrarian signal in the opposite direction.
Momentum equal to zero fails directional confirmation; flat/inconsistent EMA
comparisons do not signal. Every other valid combination returns NO_TRADE.

## Reasons, identity and causality

Deterministic evaluation priority: unavailable features, spread filter, trend,
momentum, RSI extension, RSI confirmation, then directional setup. Thus the study
counts a single primary rejection (the final reason) per NO_TRADE decision, not an
exhaustive diagnosis of every simultaneously failing filter.

Reasons: WARMUP_INCOMPLETE, SPREAD_TOO_WIDE, NO_SETUP, TREND_BULLISH,
TREND_BEARISH, SIGNALS_CONFLICT, MOMENTUM_CONFIRMATION, RSI_TOO_EXTENDED,
RSI_NO_CONFIRMATION, RSI_CONFIRMATION, BUY_SETUP and SELL_SETUP.

An immutable decision records strategy version, XAUUSD symbol, bar opening,
availability/decision time, side/action, ordered reasons, immutable relevant feature
snapshot, source dataset key, feature version and a SHA-256 of the entire canonical
source feature row. It records no execution quantity, order or position identifier.
The signal's availability is T+5 minutes for a bar opening at T, not the wall-clock
time of a later research evaluation. Warmup after day/dataset/provider-gap resets
is respected through existing feature availability markers; this strategy maintains
no cross-row state that could bridge a gap.

The input is a verified feature row, not a provenance authentication token. The
study checks persisted rows against the approved G2C3C content hashes; other callers
must similarly use approved data. This does not turn retrospective full-day dataset
selection into a live eligibility guarantee.

## Price basis and interpretation

EMA/momentum/RSI use exact analytical midpoint closes with the established Decimal
indicator convention. A BUY signal means potential future LONG entry, SELL means
potential future SHORT entry, and NO_TRADE is the default. These are repeated
bar-level setup states, not deduplicated entries or a position-management policy.
A BUY signal does not imply a midpoint fill. Future BUY execution uses ASK and
future SELL execution uses BID. No execution or profitability conclusion is possible
from this checkpoint's counts alone.

## Study and tests

`scripts/study_xauusd_signals.py` reads only the 49 approved February–April feature
datasets recorded by G2C3C, checks source identities and full content hashes, and
requires the recomputed scope to be 13,524 rows. It writes aggregate counts,
percentages, primary rejection reasons and a deterministic decision-content hash
to `docs/xauusd-baseline-signal-study.json`, with no database writes. A preselected
warning is emitted in the evidence if BUY+SELL >=90% of rows; thresholds are not
changed in response. No profit, win rate, Sharpe, drawdown or monetary-return
statistics are calculated.

Offline tests cover bullish/bearish setups, symmetric inclusive RSI boundaries,
conflicting momentum, warmup, both spread caps, directional RSI extremes,
completion/UTC, immutable source identity and absence of execution fields. The
no-lookahead test dramatically modifies all future rows after K and verifies all
earlier decisions remain identical. Repeated evaluation is deterministic.

## Measured signal study

| Month | Rows | BUY | SELL | NO_TRADE | BUY % | SELL % | NO_TRADE % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| February | 4,416 | 714 | 627 | 3,075 | 16.17 | 14.20 | 69.63 |
| March | 4,140 | 707 | 560 | 2,873 | 17.08 | 13.53 | 69.40 |
| April | 4,968 | 719 | 757 | 3,492 | 14.47 | 15.24 | 70.29 |
| Total | 13,524 | 2,140 | 1,944 | 9,440 | 15.82 | 14.37 | 69.80 |

Percentages are rounded independently. The >=90% combined-directional warning did
not trigger; this distribution is reported without judging strategy quality or
changing thresholds. Major primary NO_TRADE reasons sum exactly to 9,440:
SIGNALS_CONFLICT 4,905; WARMUP_INCOMPLETE 2,450; RSI_NO_CONFIRMATION 1,124;
RSI_TOO_EXTENDED 925; SPREAD_TOO_WIDE 36. Monthly reason counts are in the JSON.
The warmup rejection count matches the 2,450 required-history rows in G2C3C.

Decision-content hash:
`70747f730c72c5bb69442ab4055f2acf83cccd2d0f51c86cdcc98218016cbaaf`.
No database writes, orders or positions were produced by the study.

## Verification actually run

- Full `pytest -q`: **766 passed**, no skips; 16 new strategy cases. Existing
  XAUUSD and NSE feature/backtester regressions passed. One pre-existing
  Starlette/AnyIO deprecation warning remains.
- Ruff passed; Black check passed (145 files unchanged); mypy passed (83 source files).
- Alembic current **0008 (head)**; check: no schema drift. No migration needed.
- Focused tests initially caught lowercase enum-value action labels; output labels
  were corrected to BUY/SELL using the existing enum names before the successful
  full suite and study. No threshold was changed.
- Git status, working/staged diffs and whitespace reviewed: five new files, no
  existing files modified, nothing staged or committed. No dependency changes.

Recommended commit: `feat: add transparent XAUUSD trend momentum signals`.

Stopped at G2C4A. No profitability calculation, backtester changes or G2C4B work.
