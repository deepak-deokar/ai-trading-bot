# XAUUSD G2C4G1 — causal market-state features

`xauusd-market-state-features-v1` is a separate immutable, in-memory extension.
It does not change or persist over `xauusd-baseline-features-v1`. No migration,
database writes, strategies, profitability studies, random-entry comparisons,
thresholds or regime labels are introduced.

## Frozen formulas

All formulas use completed five-minute bars, including the current bar, and a
fixed Decimal context: 50 significant digits, ROUND_HALF_EVEN. Square roots and
nonterminating divisions are deterministic rounded Decimal results, not binary floats.
BID and ASK calculations are independent; no midpoint high/low is synthesized.

- For side s, `s_true_range = max(H_t-L_t, abs(H_t-C_(t-1)), abs(L_t-C_(t-1)))`.
  Without a contiguous prior close it is unavailable, rather than substituting H-L.
- `s_atr_14` is the arithmetic mean of the last 14 true ranges (rolling SMA,
  not Wilder smoothing); first available on the 15th bar of a segment.
- Analytical close M is `(bid_close+ask_close)/2`, never an execution price.
  For n=12/36, `mid_change_std_n = sqrt(sum((d_i-mean(d))^2)/n)`,
  where d_i=M_i-M_(i-1) over n consecutive changes. This is population standard
  deviation in quote-price units, not annualized or percentage volatility.
  It requires n+1 bars; constant drift has zero variability under this definition.
- `s_range_n = max(H over last n bars)-min(L over last n bars)` for n=12/36.
  First available on bar n. `s_range_ratio_12_36 = range_12/range_36`.
  An exactly flat 36-bar window returns zero by explicit convention; it is not warmup.
- `mid_efficiency_12 = abs(sum(last 12 changes))/sum(abs(last 12 changes))`.
  Requires 13 bars; a flat path returns zero. Values lie in [0,1].

## Boundaries and availability

Every output carries its typed input, dataset/policy keys, immutable feature version,
reset marker and per-feature availability. It is available only at bar completion.
Inputs must be strictly chronological and completed at the cutoff. Every call resets
state. A missing five-minute opening or absent predecessor resets every window.
The research-day boundary is explicitly HistData fixed UTC-05:00 (05:00 UTC),
not midnight UTC or an MT5 schedule. A contiguous crossing also resets state.
First-row/day warmups use WARMUP; discontinuity warmups use GAP_WARMUP.
No bars are filled, no future values enter calculations, and no state crosses datasets.

## Development verification

Only the approved February–April source manifests were loaded: 49 days,
13,524 rows (16/15/18 days respectively). Existing exact policy approval is rechecked.
The report runner recalculates baseline features and compares every row and all 49
persisted content hashes against the frozen baseline persistence manifest. All match.
Two complete extension generations match, including per-dataset content hashes,
distributions and counts. Five completed prefixes per day also match full generation.
Tests independently mutate future prices and verify that prior outputs stay unchanged.
There are 49 dataset resets and 49 provider-gap resets. Warmup values remain null.

May–July was not accessed; August–October remains locked and unprocessed.
Dataset admission is retrospective approved-day selection, not a claim that full-day
eligibility was known live. Feature mathematics itself is causal.

## Descriptive distributions

All non-null development observations are pooled; units are source quote-price units
except dimensionless ratios/efficiency. Fixed p05/p95 use nearest rank; median averages
the central pair. Display below is rounded to six decimals only; JSON retains Decimal
strings at calculation precision. These measurements select no thresholds.

| Feature | Available | Min | p05 | Median | Mean | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bid_true_range | 13426 | 0.110000 | 0.360000 | 1.120000 | 1.483832 | 3.830000 | 30.010000 |
| ask_true_range | 13426 | 0.065000 | 0.360000 | 1.120000 | 1.484741 | 3.850000 | 30.053000 |
| bid_range_12 | 12446 | 0.490000 | 1.550000 | 4.240000 | 5.639005 | 14.483000 | 40.650000 |
| ask_range_12 | 12446 | 0.580000 | 1.550000 | 4.260000 | 5.637514 | 14.553000 | 40.740000 |
| mid_change_std_12 | 12348 | 0.121971 | 0.284547 | 0.753930 | 0.960507 | 2.350789 | 7.285740 |
| mid_efficiency_12 | 12348 | 0.000000 | 0.023256 | 0.241501 | 0.278530 | 0.662316 | 1.000000 |
| bid_atr_14 | 12152 | 0.272929 | 0.505571 | 1.278464 | 1.541064 | 3.556643 | 8.371929 |
| ask_atr_14 | 12152 | 0.261929 | 0.510500 | 1.279214 | 1.541727 | 3.554286 | 8.438357 |
| bid_range_36 | 10094 | 1.550000 | 3.287000 | 8.480000 | 10.825809 | 26.073000 | 44.060000 |
| bid_range_ratio_12_36 | 10094 | 0.115520 | 0.280194 | 0.557831 | 0.583254 | 0.973382 | 1.000000 |
| ask_range_36 | 10094 | 1.537000 | 3.287000 | 8.520000 | 10.824818 | 26.073000 | 44.170000 |
| ask_range_ratio_12_36 | 10094 | 0.114257 | 0.280000 | 0.558588 | 0.583354 | 0.972603 | 1.000000 |
| mid_change_std_36 | 9996 | 0.201593 | 0.383176 | 0.928436 | 1.109569 | 2.521834 | 5.421996 |

## Reproduction and limitations

Run `PYTHONPATH=src .venv/bin/python scripts/report_xauusd_market_state.py`
with DATABASE_URL supplied securely. It reads existing bars/baseline rows and writes
only the compact JSON report. No raw per-row dataset is committed. Each manifest
retains source archive checksum, dataset/policy identity, processing versions and
bar/baseline/extension hashes. The JSON includes the engine source hash.

This checkpoint generates a versioned extension in memory, not a persisted feature
store integration. The fixed source-day convention is HistData-specific. Findings
say nothing about strategy quality, broker schedules or future feed compatibility.
No experiment parameters were selected from these distributions.

Recommended commit: `feat: add causal XAUUSD market-state feature extension`

## Verification actually run

- Full `pytest -q`: **1009 passed**, one existing Starlette/AnyIO deprecation warning.
  Includes six new offline feature cases and existing XAUUSD/NSE regressions.
- `ruff check .`: passed.
- `black --check .`: passed, 193 files unchanged.
- Strict `mypy`: passed, 98 source files.
- `alembic current`: 0008 (head); `alembic check`: no schema drift.
- `git status`, `git diff`, `git diff --cached`, `git diff --check` reviewed.
  Five new checkpoint files only; no tracked files modified or staged.
  The two old untracked $3,000 sensitivity reports remain untouched.

No commit was made. No next checkpoint was started.
