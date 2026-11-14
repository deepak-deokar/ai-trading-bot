# XAUUSD G2C4G3 — corrected market-state features

`xauusd-market-state-features-v2` is an immutable extension of the untouched
`xauusd-market-state-features-v1`. Each v2 row retains the exact typed v1 row as
`baseline`, and delegates existing feature lookups to it. All true range, ATR14,
12/36-change variability, efficiency and historical nested-range features retain
their values and semantics. No historical feature meaning is overwritten.

The only new feature is:

```text
volatility_ratio_12_36 = mid_change_std_12 / mid_change_std_36
```

It is available only when both existing measurements are available and the
36-change standard deviation is positive. Zero denominator returns `None` with
`ZERO_DENOMINATOR`, not zero, one, infinity or a substituted value. Warmup reasons
remain `WARMUP` / `GAP_WARMUP`. No optional true-range intensity was added.

The fixed Decimal context is 50 significant digits with ROUND_HALF_EVEN, matching
G1. Nonterminating division is deterministically rounded Decimal arithmetic; no
binary float calculation or tolerance band is introduced. Both inputs remain the
existing population standard deviations of analytical midpoint-close changes.
Midpoint close remains analytical, not an executable price.

Unlike nested absolute high-low ranges, a short-window standard deviation can be
higher or lower than its longer-window counterpart. Synthetic alternating-change
fixtures verify compression, exact equality and expansion. Historical nested-range
ratios remain available for reproducibility but are not used as expansion inputs.

## Availability and causality

The ratio first becomes available on bar 37 of a continuous segment (36 changes).
Each dataset starts fresh. Provider gaps, absent predecessor markers and fixed
HistData UTC-05:00 source-day boundaries reset all windows through the unchanged
v1 implementation. Source-day boundaries are 05:00 UTC, not broker permissions.
Only bars completed at the supplied cutoff are accepted. Prefix and future-mutation
tests verify no future leakage; caller Decimal precision does not affect output.

The ratio and its availability reason are separate from the core taxonomy. A mature
zero-variance window can still have a valid volatility/efficiency core label while
its expansion/compression attribute remains unavailable. No synthetic replacement
or label is supplied for that attribute.

## Scope and reproduction

Only February–April development data is used. No strategies, signals, P&L or
markouts are evaluated. May–July is unused; August–October remains locked.
The runner reads approved existing bars through the G2 loader, checking frozen G1
bar and feature hashes and exact research-policy eligibility. It performs no database
writes and requires no migration or dependency change.

With DATABASE_URL supplied securely:
`PYTHONPATH=src .venv/bin/python scripts/report_xauusd_market_state_v2.py`.
This generates only the new versioned JSON reports and freezes a separate v2 config.
It refuses to overwrite a different existing v2 config. No per-row payload is stored
in Git. G1/G2 source, reports and configurations remain unchanged.

Limitations: this is a research feature extension, not persistence integration or
an execution model. Pooled thresholds are development calibration. Absolute price
variability may change with gold's price level; that limitation is not corrected here.

## Observed development generation

49 days / 13,524 rows, two identical runs. Availability: `{'WARMUP': 1764, 'AVAILABLE': 9996, 'GAP_WARMUP': 1764}`.
Every underlying v1 feature row is unchanged; all G2 core labels and thresholds match.
Feature report hash: `c1a4e095598233ce849a62107284ce1a97b69d656d92db1d65c8cfb6bc42e8ad`.

## Verification actually run

- Final `pytest -q`: **1027 passed**, one existing Starlette/AnyIO deprecation warning.
  Includes eight new offline cases and existing XAUUSD/NSE regressions.
- `ruff check .`: passed.
- `black --check .`: passed, 199 files unchanged.
- Strict `mypy`: passed, 100 source files.
- `alembic current`: **0008 (head)**; `alembic check`: no schema drift.
- Two complete report generations match; v1 hashes and G2 core labels match.
- Git status, working/staged diffs and whitespace checks reviewed. Eight new
  checkpoint files, no tracked modifications or staged changes. The two old
  untracked $3,000 sensitivity reports are untouched. No commit was made.

Stopped at G3. No strategy or profitability analysis was introduced.
