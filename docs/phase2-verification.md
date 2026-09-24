# Phase 2 completion verification

Verified 2026-09-23 with Python 3.12.7 and local Docker PostgreSQL 17.6.

| Check actually run | Result |
| --- | --- |
| `TEST_DATABASE_URL=... pytest -q` | **102 passed**, 1 upstream Starlette/AnyIO deprecation warning; no skips |
| `ruff check .` | All checks passed |
| `black --check --workers 1 .` | 41 Python files unchanged |
| `mypy` | No issues in 25 source files |
| `python -m pip check` | No broken requirements |
| `alembic upgrade head` | Successful; working database at `0002` |
| `alembic check` | No new upgrade operations / no schema drift |
| PostgreSQL downgrade → re-upgrade | Passed in disposable-schema tests |
| Legacy instrument migration | Existing SPY remains LEGACY_US / us_equity / USD |
| Concurrent imports | Exactly one insert batch; other import classified as duplicates |
| Write failure after insertion | Candles/instruments rolled back; FAILED run retained |
| Real Uvicorn startup / HTTP smoke test | `/health` and `/ready` both 200; execution disabled; clean shutdown |
| Real Groww API/authentication | **UNVERIFIED**; no external request made |
| Groww adapter mocked verification | Parsing, fixed GET transport, chunk limits, boundary deduplication, failures passed |

All Phase 1 test scenarios still pass. The existing API test now obtains the current
schema revision constant instead of hard-coding `0001`. Pytest resolves `src`
explicitly. This machine marked editable-install `.pth` files hidden, which Python
ignored; `PYTHONPATH=src` supports deterministic local CLI execution without relying
on that file. Deployment wheels are unaffected by editable-install path discovery.

## Actual deterministic demonstration

The demonstration ran against the working PostgreSQL database, separate from the
test schemas. [Captured JSON](phase2-demo.json) includes persistent run UUIDs.
All example prices are synthetic, not real historical exchange observations.

| Scenario | Received | Inserted | Skipped | Rejected | Conflicts | Missing slots |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| First RELIANCE import | 3 | 3 | 0 | 0 | 0 | 0 |
| Identical RELIANCE rerun | 3 | 0 | 3 | 0 | 0 | 0 |
| Conflicting RELIANCE close | 1 | 0 | 0 | 1 | 1 | 2 |
| Impossible RELIANCE OHLC | 1 | 0 | 0 | 1 | 0 | 3 |
| Out-of-order TCS with intraday gap | 2 | 2 | 0 | 0 | 0 | 1 |
| Friday close → Monday open | 2 | 2 | 0 | 0 | 0 | 0 |
| Evening close → next morning | 2 | 2 | 0 | 0 | 0 | 0 |

Missing-slot counts describe each provider response over the requested range.
The one-row conflict/invalid inputs therefore have incomplete response coverage,
even though previous imports already populated the database.

Query output was chronological, UTC, and unchanged after the conflicting import:

```text
2026-01-05T03:45:00+00:00  1501.1000000000
2026-01-05T03:50:00+00:00  1502.1000000000
2026-01-05T03:55:00+00:00  1503.1000000000
```

The local import CLI was also run with `reliance_valid.csv`: it exited successfully,
reported 3 duplicates, and inserted zero new rows. Configuring live mode was tested
and rejected. There were no order calls, broker connections, strategies, or ML work.

## Files and usage

[Created/modified files](phase2-files.md), [schemas and architecture](historical-data.md),
[exact import/query commands](historical-data.md#commands).

The development database retains the synthetic demonstration data and audit runs.
Repeating the demonstration preserves existing rows; its first-import count becomes
zero on subsequent runs. Do not use these synthetic source=local fixtures as research
market observations. No committed credentials or credential-bearing `.env` were created.
The previous generated development credential remains outside the repository.

## Known limitations

- Default calendar coverage is explicitly 2026; per-security sessions and unannounced
  halts are not modeled. Overrides and expanded historical coverage require review.
- Groww opening labels/adjustments and real authentication are unverified; callers
  must explicitly confirm semantics. Daily labels from a vendor may need adaptation.
- No Parquet, corporate-action transformation, retry scheduler, or abandoned-run
  recovery. A crash may leave RUNNING audit rows; reruns are idempotent.
- Up to 100,000 rows/expected slots per run; service writes serialize for correctness.
- Conflict policy preserves the existing/first accepted candle and reports competing
  values; it does not decide which observation is economically correct.
- Quality completeness describes the import response, not a union of earlier imports.

Recommended commit: `feat: add audited NSE historical data ingestion and queries`

Next objective: Phase 3 deterministic, versioned features built only from completed
candles. Phase 3 has not begun.
