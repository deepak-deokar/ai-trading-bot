# XAUUSD G2C3A — research price and feature-input semantics

`data/research_input.py` adds a pure adapter and immutable `ResearchFeatureInput`,
reusing QuoteBar validation. No stored bars, NSE candles, execution backtester or
strategies are changed. No indicator calculation, feature persistence, migration,
MT5 integration or G2C3B work is included.

## Prices and supported information

Inputs retain canonical XAUUSD, the UTC opening timestamp, five-minute interval,
eight separate bid/ask OHLC Decimal values and tick count. Financial floats and
naive timestamps are rejected. Explicit analytical bases are BID, ASK and
MID_CLOSE_ANALYTICAL_ONLY, selected through `analytical_close(basis)` without a
default. No ambiguous single OHLC candle is constructed.

Exact derived properties:

- `spread_open = ask_open - bid_open`
- `spread_close = ask_close - bid_close`
- `mid_close = (bid_close + ask_close) / 2`

The existing exact MarketQuote arithmetic is reused, including protection against
rounding under a caller's low Decimal context precision. These endpoint values
are justified by the existing aggregation's paired first/last observed tick quotes.
They are not claims about prices exactly at a bin boundary with no observation.
Properties are calculated on access; model serialization preserves source fields
and gap metadata without duplicating the derived price properties.

There are no midpoint high/low properties. Independently aggregated side extrema
need not occur at the same tick, so averaging bid_high and ask_high does not
recover the maximum midpoint. The same limitation applies to lows. Exact intrabar
spread minimum and maximum are explicitly unavailable (`exact_spread_min` and
`exact_spread_max` are fixed to None). Neither differences of side highs/lows nor
endpoint spreads establish the full spread range. No approximate range is invented.

## Completion and causality

A bar labeled T describes [T, T+5 minutes). `available_at` is T+5 minutes.
`completed_input(row, as_of=...)` rejects an incomplete bar; the UTC cutoff must
be explicit and timezone-aware. The mathematical adapter accepts either an existing
QuoteBar or a loaded SQLAlchemy BidAskBar and revalidates source values. It has no
network, query, write or execution operation and does not itself confer policy
approval. Direct model construction describes a bar; callers must use the completed
adapter or approved pipeline to enforce availability.

`approved_research_inputs(dataset, rows, policy, as_of=...)` requires a full
source-day collection and returns only bars completed by the cutoff. Later bars
are not incorporated into the returned bar's mathematical values. Strict ordering
is required; duplicate/reversed openings are rejected rather than silently sorted.
No incomplete next bar is exposed at an intermediate cutoff.

There is an important distinction: source-day eligibility is **retrospective data
selection**, using the full day's coverage. It is not a claim that eligibility was
known at each bar close in live trading. The mathematical input is causal once the
approved dataset has been selected. Future training/evaluation must account for
selection bias; this module does not implement a live policy estimator.

## Gaps and provenance

Each input exposes `previous_observed_timestamp`, `elapsed_since_previous` and
`discontinuity`. Adjacent ordinary bars have five minutes elapsed and False;
a jump from 21:55 to 23:00 is 65 minutes and True. Missing openings are never
created or filled. The first input has no known predecessor and both elapsed and
discontinuity are None, not an implied contiguous boundary. The approved API resets
this predecessor at each source-day dataset boundary. Future multi-day feature
code must explicitly manage those boundaries and decide whether to reset windows,
use elapsed time or reject discontinuities; no indicator-window behavior is chosen.

The approved API requires the dataset already carry the selected policy version
and content key, then re-evaluates G2C2A through the existing policy service. It
rejects excluded/holiday/unexplained, no-data, wrong-provenance and wrong-gap days.
ORM rows must carry the matching dataset key/provider/provider symbol. Domain-only
QuoteBars have no embedded provenance: the caller must supply a trustworthy dataset
manifest paired with those bars, as in the existing repository API. An old usable
flag alone is insufficient. A typed output batch records dataset identity, policy
identity and UTC cutoff. No policy dates or source timezone rules are changed.

## Analysis is not execution

Analytical price basis is not an execution price. Future BUY semantics consume ASK;
SELL semantics consume BID, regardless of opening or closing direction. Midpoint
close is analytical only and is never routed into an execution helper here. A
completed-bar close also does not guarantee an available future fill at that price.
Existing quote-side execution semantics remain unchanged and covered by tests.

## Verification

Focused offline tests cover Decimal precision/enforcement, UTC and availability,
source preservation, unsupported extrema, contiguous/gapped observations, no filling,
policy/provenance rejection, loaded ORM conversion and unchanged BUY/SELL semantics.
No live internet or real research archive is required by these tests.

Actually run: full `pytest -q` **742 passed** (15 new cases), no skips; one existing
Starlette/AnyIO warning. Existing NSE/backtester regressions passed. Ruff passed;
Black check passed (136 files unchanged); strict mypy passed (80 source files).
Alembic current is **0007 (head)**; Alembic check reports no schema drift.
Git status, working diff, staged diff and whitespace checked: three new files,
no existing files modified, nothing staged or committed. No dependency changes.

Recommended commit: `feat: define causal XAUUSD research input semantics`.
