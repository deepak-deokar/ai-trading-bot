# Phase 5B-2 — historical data gate

**PHASE 5B-2 BLOCKED — INSUFFICIENT HISTORICAL DATA**

**INSUFFICIENT HISTORICAL DATA FOR PHASE 5B-2**

No broad historical performance evaluation was run. The read-only PostgreSQL audit
found only sparse verification fixtures, not meaningful real historical coverage.
No strategy rule, parameter, execution assumption or source data was changed.
Phase 5C has not begun. Nothing was staged or committed.

## Actual data coverage

The local development PostgreSQL database has only one schema containing
`market_bars`: `public`, migration **0004**. Counts are 2 instruments, **9 bars**,
8 ingestion audits, **0 feature sets**, 0 feature values and 0 backtest runs.
There are **0 historical_dataset_identity events**. No dataset keys can be recovered
from these legacy imports; none have been invented retrospectively.

| Symbol | First–last observed date (IST) | Observed dates | Complete sessions | Bars | Source / adjustment |
| --- | --- | ---: | ---: | ---: | --- |
| RELIANCE | 2026-01-05–2026-01-05 | 1 | 0 | 3 | local / RAW |
| TCS | 2026-01-05–2026-01-12 | 5 | 0 | 6 | local / RAW |
| INFY | None | 0 | 0 | 0 | None |
| HDFCBANK | None | 0 | 0 | 0 | None |
| ICICIBANK | None | 0 | 0 | 0 | None |

All stored bars are NSE CASH, 5-minute opening labels. RELIANCE has openings at
09:15, 09:20 and 09:25 IST on January 5, last available at 09:30. TCS has sparse
openings between January 5 at 09:15 and January 12 at 09:15, last available at 09:20
January 12. Observed dates are not complete sessions or evidence of continuous
coverage across the date range. A regular full session requires 75 five-minute bars.

These source=local data match the synthetic ingestion scenarios documented in
[Phase 2 verification](phase2-verification.md); that document explicitly excludes
them from research use. Later Phase 4/5 demonstrations used disposable schemas,
which are absent from this database. No fixture was substituted for historical data.

Legacy calendar version on the ingestion audits:
`pmc-5.4.0:nse-cash-2026-review-20260923:62d22fb4a2019f30`.
Persisted calendar-authority manifests are absent. The report conservatively records
**UNKNOWN** authority for these legacy rows; a version label is not retrospective
verification. Symbols without data have NOT_APPLICABLE authority. No UNKNOWN warning
was silently promoted to verified coverage.

Run-level quality findings include RELIANCE duplicates, missing bars/symbol, rejected
conflicting/invalid candles and large gaps; TCS includes out-of-order input and missing
bars. These describe ingestion attempts, including rejected attempts, and do not mean
all rejected rows were stored. The current whole-session coverage is insufficient
regardless of those findings. The [JSON artifact](phase5b2-evaluation.json) retains
all relevant run IDs, calendar versions, per-symbol warnings and coverage details.

## Frozen research configuration

Strategy: `baseline_trend_momentum_v1`, version `1`, identity:
`2ecdbba029f57187692ec7a44762970ace21a2d12ee2b385e84d43f04cca6006`.

Unchanged defaults: quantity 10, RSI 55–70, minimum volume ratio 1.0, entry window
09:30–14:45 Asia/Kolkata, stop 1.5× entry ATR and target 2.0× entry ATR. Long-only,
no pyramiding. The JSON records SHA-256 fingerprints of the strategy implementation,
strategy config and existing cost profile. Their bytes match Git HEAD.

Planned assumptions, **not executed research runs**:

- ₹2,00,000 per independent symbol account; 1× cash, no leverage.
- Existing Groww NSE intraday research cost profile, unchanged version
  `2026-09-24-research-1`, with its source/rounding/fixed-rate warnings retained.
- Baseline slippage 5 bps; requested fixed sensitivity set 0/5/10 bps remains unrun.
- Participation 10%, CONSERVATIVE ambiguity, FAIL_RUN gaps, FORCE_FLATTEN with the
  existing 10-minute cutoff and STRICT_NEXT_OPEN_SETTLE_ON_COMPLETE_V1 timing.
- UTC storage, IST sessions, source/adjustment isolation and causal availability.

No performance claim is possible. Per-symbol trade/winner/loser counts, win rate,
gross/net P&L, charges, slippage, profit factor, expectancy, drawdown, turnover,
holding period, exit categories, monthly/quarterly stability, concentration and
sensitivity results are **NOT EVALUATED**. They are JSON null, not fabricated zero
returns or zero trades. There is no aggregate or shared-portfolio result.

The evaluation/aggregation/sensitivity layer and its prospective tests were deferred
at the explicit data gate. No new executable evaluation layer was introduced merely
to run fixtures as research. Existing causality tests were run unchanged, including
future-candle/feature mutation and earlier event/order/fill/equity isolation.

A later sensitivity implementation must distinguish frozen-decision replay from
closed-loop strategy reruns: changing fill prices also changes this strategy's
fill-based protective levels, so rerunning callbacks cannot simply be described as
using identical decisions. Neither kind of analysis was attempted here.

## Data required next

Acquire real, legally usable historical **5-minute NSE CASH OHLCV** for RELIANCE,
TCS, INFY, HDFCBANK and ICICIBANK. A concrete initial acquisition window is
**2026-01-01 through 2026-06-30**, all calendar-supported sessions. This is a fixed
prospective window, not observed coverage or a guarantee of statistical sufficiency.
It permits descriptive monthly and quarterly analysis without requiring unsupported
future calendars. Do not select months based on returns.

The next ingestion needs:

1. Vendor/source provenance, exchange-qualified instrument mapping, explicit timestamp
   meaning/timezone and adjustment semantics. Confirm 5-minute **opening** labels;
   do not guess whether vendor labels indicate close. Keep one source and explicit
   adjustment policy per run; RAW is a possible initial policy, not permission to
   silently relabel adjusted data. Record corporate-action limitations.
2. Complete session OHLCV with real whole-share volume. Required local CSV fields are
   `symbol,timestamp,open,high,low,close,volume`; timestamps need explicit offsets.
   Split imports into the existing pipeline's bounded request ranges. Include the
   first regular 09:15 opening through 15:25 opening, complete at 15:30, subject to
   the existing calendar's special-session schedules.
3. A clean research database/schema to avoid mixing these synthetic source=local
   rows with real local CSV imports. Do not overwrite verification fixtures silently.
   Retain the vendor files/provenance and ingest through the existing pipeline.
4. New dataset identity events, ingestion run IDs, calendar provider/version/authority,
   quality reports and one explicit adjustment policy. Check completeness against
   calendar slots; do not fill missing bars with invented prices. UNKNOWN authority
   must remain visible and requires the existing explicit research opt-in where used.
5. Feature generation with existing canonical `baseline_v1`, persisted feature-set
   identity and normal warm-up nulls. Rerun the coverage gate before any performance
   evaluation. Full-session bars and valid feature provenance are prerequisites.

No provider purchase, download, broker authentication or Groww connection was made.
Groww remains UNVERIFIED. The acquisition above is the missing external prerequisite.

## Verification actually run

| Check | Result |
| --- | --- |
| `pytest -q` with PostgreSQL | **356 passed**, no skips, 13.94 seconds |
| `ruff check .` | All checks passed |
| `black --check .` | 93 Python files unchanged |
| `mypy` | No issues in 62 source files |
| `alembic current` | **0004 (head)** |
| `alembic check` | No new upgrade operations detected |
| Existing migration tests | Passed |
| Strategy/config/cost-profile freeze | Byte-identical to Git HEAD |
| `git diff --check` | Passed |

One pre-existing Starlette/AnyIO deprecation warning remains. Tests use disposable
schemas; no historical evaluation was run as a side effect. There is no new migration
or functionality change. No new aggregation/grouping tests were claimed: those would
belong to the evaluation layer deferred by the failed data gate.

## Repository hygiene and stop point

Only two new documentation artifacts:

```text
docs/phase5b2-evaluation.md
docs/phase5b2-evaluation.json
```

The working tree was clean before this check. Both artifacts are small, unstaged and
uncommitted; cached diff is empty. No `.env`, credentials, temporary datasets, cache,
build artifacts, source edits or migrations are included. The audit helper and local
connection setup remain outside the repository. No unfinished executable placeholders
were added.

Recommended commit:
`docs: record blocked baseline evaluation and historical data requirements`

Stop: Phase 5B-2 is blocked by insufficient historical data. Phase 5C has not begun.
