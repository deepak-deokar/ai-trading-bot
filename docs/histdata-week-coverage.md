# XAUUSD G2B2B — bounded coverage audit

Only source dates January 15–19, 2024 are analyzed from the existing checksum-
verified January archive. No data was downloaded. The CSV is streamed once per
selected day; other date rows are skipped. Each source day is fixed UTC−05:00,
so its research range is 05:00 UTC through 05:00 UTC the following date, with
288 theoretical five-minute bins. This is a research-day definition, not an
assertion that all 288 bins should be broker-tradable.

The existing parser, separate-side aggregation and quote-bar repository are reused
unchanged. Only observed bars are imported. January 16 uses the same dataset
identity as G2B2A, so it remains idempotent. Other dates receive separate keys.
Run manifests retain archive checksum, source/provider identities, processing
versions, date/range and missing openings. No migration is needed.

## Derived API and explicit acceptance

`daily_coverage(dataset, bars, accepted_pattern=None)` returns expected/observed
counts, every missing opening, unexpected gaps, longest consecutive missing run
(in five-minute bins), first/last observed bar, valid tick count, classification
and research usability. It never creates or changes bars. `coverage_for_run`
loads the existing run manifest and queries only its dataset key. The pure API
expects bars from that stated dataset; the service supplies that isolation.

Without an accepted pattern, every missing opening is unexpected. An explicit
`AcceptedGapPattern` is scoped to provider, provider symbol, canonical symbol,
archive checksum, source timezone, processing versions, interval, daily UTC start
clock and allowed dates. Accepted indices remain missing in the report. Only an
exact missing-set match can be research-usable; missing fewer accepted bins is
also reported as a pattern mismatch, not silently reclassified.

Classifications:

- `COMPLETE_UNDER_OBSERVED_PROVIDER_PATTERN`: observed bars exist, the missing set
  exactly matches explicit acceptance (or is empty when no gaps are accepted).
- `INCOMPLETE_UNEXPECTED_GAPS`: missing openings outside the accepted set.
- `INCOMPLETE_PATTERN_MISMATCH`: no unexpected missing bins, but the exact pattern
  does not match.
- `NO_DATA`: no observed bars; always unusable.

`recurring_pattern` compares distinct dates from the same provenance family and
reports `RECURRING_PROVIDER_GAP_PATTERN` only after at least two exact matches.
Detection alone does not authorize usability. The demonstration script explicitly
accepts only indices 204–215 (22:00–22:55 UTC) for these five dates, and activates
that bounded policy only when repeated observations support it. Extra gaps are
never learned into the policy. The report includes both unaccepted and explicitly
accepted classifications, plus the complete accepted policy.

Spread min/median/max are computed from valid ticks for the bounded source days
and attached to their dataset reports; median tick spread cannot be reconstructed
from OHLC bars alone. Completeness itself is derived from persisted bars and
provenance and is not stored in new database tables.

## Interpretation limits

HistData coverage pattern **does not equal** the future MT5 broker schedule.
This week may contain holiday-related or week-ending closures; the audit does not
assert those explanations or turn them into permissions. No observed gap is
filled. Research usability here addresses five-minute coverage under the stated
policy only, not feed authority, full tick completeness, profitability, strategy
readiness, or execution safety. Coverage reports are recomputed snapshots, not a
new immutable dataset versioning platform.

No strategy, backtester, MT5, trading/risk logic or large-scale ingestion changes
were made. The existing monthly ZIP is not committed. Run the bounded offline
reproduction with DATABASE_URL already provided securely:

```sh
PYTHONPATH=src .venv/bin/python scripts/audit_histdata_week.py \
  /tmp/HISTDATA_COM_ASCII_XAUUSD_T_202401.zip
```

## Observed bounded-week results

Each day has 288 expected bins. Longest runs are measured in five-minute bins.
Times below are UTC opening labels; end dates extending into the next UTC day
reflect the fixed-EST research boundary, not DST.

| Source date | Observed | Missing | Longest run | Ticks | Spread min / median / max | Usable |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 2024-01-15 | 246 | 42 | 42 | 84,831 | 0.100000 / 0.327000 / 1.822000 | No |
| 2024-01-16 | 276 | 12 | 12 | 177,064 | 0.001000 / 0.327000 / 1.804000 | Yes |
| 2024-01-17 | 276 | 12 | 12 | 159,858 | 0.100000 / 0.330000 / 1.950000 | Yes |
| 2024-01-18 | 276 | 12 | 12 | 130,884 | 0.125000 / 0.327000 / 4.026000 | Yes |
| 2024-01-19 | 204 | 84 | 84 | 99,908 | 0.100000 / 0.330000 / 0.872000 | No |

All source days had zero rejected ticks. First observed bar is 05:00 UTC on each
listed date. Last observed bars are 04:55 UTC on the following date for January
15–18, and 21:55 UTC on January 19.

The 22:00–22:55 missing openings occur on all five dates, but are the **entire**
missing set only on January 16, 17 and 18. These three independent dates support
`RECURRING_PROVIDER_GAP_PATTERN`. January 15 and 19 differ:

- January 15: 30 additional openings, 19:30–21:55 UTC. Combined missing run is
  19:30–22:55, 42 bins (210 minutes).
- January 19: 72 additional openings, 23:00 UTC through January 20 04:55 UTC.
  Combined missing run is 22:00–04:55, 84 bins (420 minutes).

The additional intervals remain unexplained by the accepted policy. They are
not newly accepted holiday or weekend schedule exceptions. January 15/19 are
`INCOMPLETE_UNEXPECTED_GAPS`. January 16–18 are
`COMPLETE_UNDER_OBSERVED_PROVIDER_PATTERN`. **3 of 5 days** qualify under this
bounded research policy. Without acceptance, all five are incomplete.

Actual persistence inserted 246 + 276 + 276 + 204 = **1,002 new bars**.
January 16 reused **276 existing bars**, inserting zero. The five datasets now
contain **1,278 observed bars**, leaving **162 missing bins** out of 1,440 possible
bins. No missing rows were synthesized. Per-day run UUIDs, keys, complete missing
lists, provenance and tick statistics are in `histdata-week-coverage.json`.

## Verification actually run

- `pytest -q`: **683 passed**, no skips; one existing Starlette/AnyIO warning.
  Includes all prior 677 cases and six new offline coverage cases; NSE regressions
  and existing 276 + 12 behavior remain passing.
- `ruff check .`: passed.
- `black --check .`: passed, 129 files unchanged.
- `mypy`: passed, 77 source files.
- `alembic current`: **0007 (head)**; `alembic check`: no schema drift.
- Git status, working diff, staged diff and whitespace checks reviewed. Six new
  files only; no existing files modified, no migration, no commit. The full raw
  archive remains outside Git and no dependencies were added.

Recommended commit: `feat: audit bounded HistData quote bar coverage`.
