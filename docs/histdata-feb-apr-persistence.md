# XAUUSD G2C2B — policy-eligible HistData persistence

## Scope and implementation

Only the previously validated February–April 2024 archives are used. No downloads,
features, strategies, backtester, broker, MT5 or risk changes. No G2C3 work.

`data/policy_import.py` provides `evaluate_policy_day` and `import_policy_day`.
Both use existing validated QuoteBars, `daily_coverage` and `evaluate_gap_policy`.
The import calls the existing QuoteBarRepository only for
ELIGIBLE_UNDER_RESEARCH_POLICY. Rejected dates return an audit without writing bars
or database events. Invalid tick/count inputs fail closed. Eligibility is recomputed
at the write boundary; a caller-supplied approval flag cannot bypass it.

`persist_histdata_research.py` is bounded to the three archives pinned by G2C1 and
the G2C2A policy. It checks all archive SHA-256 values and policy/report bindings
before processing, streams through the existing HistData `parse_tick`, and reuses
`five_minute_view` for separate bid and ask OHLC. It evaluates all calendar dates,
including dates with no observations, before opening the database. Invalid source
records abort preflight instead of being repaired or silently omitted.

The policy alone decides day eligibility. The separately computed counts are
checked against 16/15/18 eligible days and 13,524 bars as discrepancy guards, never
used to select or manufacture rows. Each eligible day must have 276 observed bars
and its 12 missing openings preserved. No interpolation, forward fill or synthetic
prices. Source timestamps retain fixed UTC−05:00 without DST; UTC opening labels
and separate bid/ask semantics are unchanged.

## Identity, audit and transactions

QuoteDataset adds optional paired `gap_policy_version` and `gap_policy_key` fields.
Approved identities include both, so changing policy content or version isolates
the dataset. Existing identities/manifests omit absent optional fields, preserving
January's original dataset keys and repeat-import behavior byte-for-byte.
The existing JSON run manifest stores policy identity, provider/symbol, source
archive/checksum/month/date, normalization/aggregation versions and missing openings.
No database table change or migration is needed.

The evidence JSON records all 90 date evaluations: full dataset manifest, dataset
key, typed policy outcome and reason, observed/missing openings, valid raw counts,
and both import results for eligible dates. Excluded results have null imports.
The policy is `histdata-xauusd-research-gap-v1`; its content key is also recorded.

For each eligible date the existing repository is called twice with identical
validated bars. The second call checks stored values and inserts no duplicates;
no second archive download or parse is required. Repository queries then verify
all stored bars equal the original sorted observations. Excluded policy dataset
keys must have zero stored rows before and after the run.

Transactions remain scoped to one source-day import. A conflicting value or failed
audit write rolls back that day's transaction; earlier successful days remain
committed and can be resumed idempotently. No silent replacement. The complete
90-date generated report is written after successful verification; if interrupted,
existing per-day database run manifests survive but this final report may be absent.

All pre-existing bid_ask_bars rows, including January, are snapshotted before import
and compared after import across every stored column (including original run IDs).
This check reads historical rows; it does not rewrite their provenance or bars.

## Reproduction

With the development database URL securely provided and the three archives already
present outside Git:

```sh
PYTHONPATH=src .venv/bin/python scripts/persist_histdata_research.py /tmp
```

This command writes eligible research data and produces the JSON report. Normal
automated tests use synthetic bars and disposable PostgreSQL schemas, never live
internet or the vendor archives. The generic repository remains available for older
research workflows; callers creating policy-approved datasets should use the gated
service rather than bypassing it. Policy provenance is a reproducibility record,
not a cryptographic authorization mechanism.

## Archive checksums

| Month | SHA-256 |
| --- | --- |
| February 2024 | `fedd441ffc428d7b8556f5328c3017fdc87b7088a0419dcd688c968ad9ceb2eb` |
| March 2024 | `27719c29ee4aed7a36678a9050db035fa0330f66862a01f0cd8ccbbdc6e75457` |
| April 2024 | `e7f0a460fc2b20fdc9c06fc247802a811fec43dad7255c592f17f8365754e207` |

## Verification actually run

- `pytest -q`: **727 passed**, no skips, one existing Starlette/AnyIO deprecation
  warning. Includes nine new policy-import cases and all prior NSE/backtester,
  quote-storage, coverage and policy regressions.
- `ruff check .`: passed.
- `black --check .`: passed, 134 files unchanged.
- `mypy`: passed, 79 source files.
- `alembic current`: **0007 (head)**; `alembic check`: no schema drift.
- Conflict test rejects a changed candle and confirms original bars/events remain.
- Forced audit-insert failure test confirms all 276 newly inserted bars roll back,
  with zero events left behind in the disposable test schema.
- January legacy identity compatibility, dataset-policy isolation, chronological
  queries, exact gaps, excluded-date zero writes and idempotency are tested offline.

Known limitations: eligibility is the stated research coverage policy, not a broker
schedule or proof of full tick completeness. Policy/report changes produce new
identities and require review. Atomicity is per day, not the entire three months.
No market/execution or profitability conclusion follows from this import.

## Measured persistence results

The run completed at 2026-10-31T21:51:22.438987Z. Policy content key:
`3ca1de378bb35c6abbacf25652a1b8600ee107e23db6fa2f31e607bcee63a28d`.

| Month | Eligible days | EXCLUDED_DAY_TYPE | NO_DATA | First-pass inserted bars | Second-pass inserted / existing |
| --- | ---: | ---: | ---: | ---: | --- |
| February | 16 | 9 | 4 | 4,416 | 0 / 4,416 |
| March | 15 | 10 | 6 | 4,140 | 0 / 4,140 |
| April | 18 | 8 | 4 | 4,968 | 0 / 4,968 |
| Total | 49 | 27 | 14 | 13,524 | 0 / 13,524 |

Excluded-day composition (categories below partition the excluded source dates):

- February: four Fridays, eight weekend dates, February 19 holiday-associated day.
  Four empty Saturdays return NO_DATA; the other nine return EXCLUDED_DAY_TYPE.
- March: four non-holiday Fridays, ten weekend dates, March 28 unexplained day,
  and March 29 holiday-associated/no-data day. Five Saturdays and March 29 return
  NO_DATA; the remaining ten return EXCLUDED_DAY_TYPE.
- April: four Fridays and eight weekend dates. Four Saturdays return NO_DATA;
  the remaining eight return EXCLUDED_DAY_TYPE.

All 90 dates have an audit result. There were no provenance mismatches or other
eligibility failure statuses in these checksum-verified inputs. February 19,
March 28 and March 29 were not imported. Excluded policy keys have **zero rows**.

Actual stored count **13,524** equals the independently checked expectation
**49 × 276**. The second calls recognized all 13,524 existing bars with zero inserts.
Queries matched all original observed bars in chronological order, including exact
bid/ask values and tick counts; accepted missing bins remained absent.

All **1,278 pre-existing rows** were verified unchanged across every stored column,
preserving January's rows and original run IDs. No January rewrite or deletion.
The machine-readable audit is `docs/histdata-feb-apr-persistence.json`; it includes
both successful run UUIDs for each eligible day and null import results for all
excluded days. Audit totals and exclusions were independently cross-checked from
the saved JSON after the run completed.

Final Git review: one modified existing file (`quote_bar_storage.py`) and five new
files (gated service, bounded import script, tests and two reports). Working and
staged diffs plus whitespace checks reviewed; nothing staged or committed. No new
archive is tracked. No migration or dependency change.

Recommended commit: `feat: persist policy-eligible HistData research days`.

Stopped at G2C2B. No feature generation or G2C3 work.
