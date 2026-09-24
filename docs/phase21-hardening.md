# Phase 2.1 hardening

Phase 2.1 changes historical data boundaries only. No features, indicators,
strategies, ML, backtesting, brokers, or trading have been added. Live-mode rejection
is unchanged. Real Groww authentication/API behavior remains **UNVERIFIED**.

## Multi-year calendar

The isolated NSE calendar now models dependency-backed schedules from **2020-01-01
through 2026-12-31**, the supported range inspected for the pinned
`pandas-market-calendars==5.4.0` NSE data. No new hand-written annual holiday lists
were introduced. Package schedules exclude weekends and their supplied holidays;
source-linked exceptional-session overrides remain supported.

The package does not guarantee authoritative historical completeness. Its own
[documentation](https://pandas-market-calendars.readthedocs.io/en/latest/) explains
that calendar data is shipped with the package, not retrieved live. We therefore
make coverage and authority separate concepts:

| Requested dates | Default behavior | Authority metadata |
| --- | --- | --- |
| 2026, existing Phase 2 policy | Existing behavior preserved | REVIEWED_POLICY |
| 2020–2025 | Clear CalendarError / audited FAILED ingestion | UNKNOWN |
| 2020–2025 with explicit research opt-in | Dependency schedules used, warning persisted | Still UNKNOWN |
| Before 2020 or after 2026 | Always rejected | UNSUPPORTED |
| Explicit `unknown` interval in policy | Always rejected, even with opt-in | UNSUPPORTED |

`REVIEWED_POLICY` identifies the existing reviewed overlay, not a claim that every
possible historical interruption has been independently verified. A cross-year
request containing any unreviewed date has UNKNOWN authority. Unknown intervals
are not silently interpreted as holidays or open days.

Explicit research usage:

```python
calendar = NSECalendar(allow_unverified_history=True)
metadata = calendar.provenance(start, end)
```

CLI equivalent: `--allow-unverified-calendar`. This acceptance is recorded in the
calendar version and dataset manifest. Successful imports using unknown-authority
history receive `CALENDAR_UNVERIFIED` and `COMPLETED_WITH_WARNINGS`.

Calendar bounds and the installed dependency version must match the supported
provider registry. Editing YAML to extend into 2027 cannot manufacture coverage;
a future package/coverage update requires inspection and review. The policy allows
closures, special-session open/close times, and explicit unknown intervals. Calendar
identity includes provider/version, full policy SHA-256, and research opt-in state.
Asia/Kolkata interpretation and UTC storage remain unchanged.

Tests span all seven years, normal days, weekends, supplied holidays, a fixture
closure/special session, year boundaries, unknown intervals, dependency mismatch,
and out-of-range rejection. No authoritative 2020–2025 verification is claimed.

## Opening timestamps and completion

Every `Bar` declares `timestamp_convention="open"`. Its timestamp labels the left
edge of a half-open interval. A regular 5-minute candle stamped 09:15 IST covers:

```text
09:15 <= market time < 09:20
UTC: 03:45 <= market time < 03:50
```

It becomes visible at 09:20, never at 09:19:59. The calendar provides the
session-aware closing instant, persisted as `market_bars.available_at`. Ingestion
accepts only aligned, completed slots. Range, count, latest and available-range
queries all enforce `available_at <= request.end`.

CSV files are defined to use opening timestamps and require explicit offsets.
They may include `timestamp_convention`; any value other than `open` is rejected.
`RawCandle` documents the same provider contract, and normalization rejects a
non-opening convention rather than silently shifting a label. Calendar gap checks
use these same opening slots. Incorrectly labeled input cannot be detected from
OHLC values alone: providers/operators must truthfully declare their convention.

## Groww semantics contract

The existing mock scenarios retain their assertions; their setup now supplies
explicit `GrowwSemantics`. The old two-flag constructor is deliberately insufficient
for data import, because it left some assumptions implicit.

Required fields:

- `timestamp_meaning: open`
- `timezone: Asia/Kolkata`
- one explicit `adjustment_type`
- typed `interval_mapping`
- exchange/segment-qualified `instrument_mapping`
- acknowledgement `UNVERIFIED_PROVIDER_SEMANTICS_ACCEPTED`

Missing, contradictory, or unsupported mappings fail before network access with
`ProviderSemanticsError`. Only explicitly mapped symbols and intervals may be
requested. Unknown timestamp formats are rejected; numeric values cannot fall
through to automatic epoch interpretation. Returned interval metadata, when present,
must match the request. The adapter owns a validated configuration snapshot.

The [current Groww documentation](https://groww.in/trade-api/docs/python-sdk/backtesting)
provides interval labels and instrument identifier structure; it does not establish
our real authenticated timestamp/adjustment verification. Configuration is an
operator assertion, not verification. Each Groww import records the mappings,
adapter version and UNVERIFIED status; successful imports carry a quality warning.
Only the existing historical-candles GET transport is used.

`config/groww_semantics.example.yaml` is an example assertion, not an automatically
loaded or verified profile. It contains no credentials. For an eventual authorized
historical import, select a reviewed file with `--groww-semantics PATH`, as well as
the existing adjustment and opening-timestamp confirmation flags. Access tokens
remain environment-only. No real Groww request was made during this pass.

## Adjustment isolation

`HistoryRequest.adjustment_type` is always resolved to one enum value; omission
explicitly resolves to RAW. It is never a wildcard. All four query methods filter
that value and the required source. Database candle identity continues to include
adjustment policy. A mixed-adjustment CSV row is rejected rather than relabeled.

PostgreSQL tests store RAW, SPLIT_ADJUSTED and FULLY_ADJUSTED candles with identical
instrument/timeframe/opening identities and different prices, then verify that each
query returns only its selected policy. No adjustment transformations are performed.

## Lightweight dataset identity

Each new run now has a canonical manifest containing:

- provider/source and provider semantics;
- exchange, segment and sorted instrument symbols;
- timeframe, normalized UTC requested range and adjustment policy;
- opening/half-open/completion conventions;
- calendar provider/version, coverage, authority and opt-in state.

`dataset_key` is SHA-256 over the canonical manifest. Reordering symbols or mapping
keys does not change it. Changed selection or semantics changes the key.
`run_key` additionally includes the unique ingestion UUID. An identical rerun has
the same dataset key but a different run key.

These are **selection/semantics identities, not hashes of candle contents or frozen
query snapshots**. Corrections and vendor revisions remain observable through
separate runs, conflict reports, and the existing per-candle ingestion provenance.
No dataset-versioning platform has been added.

The manifest is committed with the initial ingestion run as a
`system_events` row of type `historical_dataset_identity`. It therefore survives
subsequent candle-write rollback. Both keys appear in the ingestion report.

```python
identity = HistoryQuery(engine).get_dataset_identity(report.run_id)
print(identity.dataset_key, identity.run_key)
print(identity.manifest["calendar"])
```

Pre-2.1 runs have no identity event; lookup returns `None`. No invented retrospective
semantics or migration backfill is applied. Existing tables already support the
manifest, so **no schema migration was required**.

## Verification actually run

- Full PostgreSQL pytest suite: **146 passed**, no skipped tests.
- Original 102 scenarios retained; 44 hardening cases added.
- Ruff: all checks passed.
- Black check: 45 Python files unchanged.
- Strict mypy: no issues in 27 source files.
- Alembic upgrade/current: **0002 (head)**.
- Alembic check: **no schema drift**.
- Existing migration downgrade/re-upgrade tests passed in disposable schemas.
- One pre-existing Starlette/AnyIO deprecation warning remains.

Commands (activate `.venv`, export the development database URL first):

```sh
export PYTHONPATH="$PWD/src"
TEST_DATABASE_URL="$DATABASE_URL" pytest -q
ruff check .
black --check --workers 1 .
mypy
alembic current
alembic check
```

Limitations remain explicit: historical calendar authority before 2026 is UNKNOWN,
2027+ is unsupported, real Groww behavior is UNVERIFIED, and metadata identities do
not freeze candle contents. Existing row limits, CSV-only ingestion, and crash-recovery
limitations remain unchanged. No credentials were added, and no trading was enabled.

Recommended commit: `fix: harden historical calendar and dataset semantics`

Stopped at Phase 2.1. Phase 3 has not begun.
