# XAUUSD G2B1 — Dukascopy pilot INCOMPLETE

The mandatory price-scaling gate was not satisfied. No historical quotes were
retrieved or normalized. This is a blocked investigation, not an implemented or
verified provider adapter. No PostgreSQL ingestion, schema/dependency change,
strategy/backtester change, MT5 activity or G2B2 work occurred.

## Evidence and decision

Reviewed the provider's [Historical Price Data guide](https://www.dukascopy.com/wiki/en/development/data-export/).
It describes LZMA-compressed records with timestamp, ask, bid and volume fields,
and explicitly requires confirming commodity point values. Its XAUUSD entry is
commented-out illustrative code, not an authoritative scale declaration. The
same page discusses daily S3 objects, so its day-relative timestamp description
cannot safely be assumed to describe legacy hourly HTTP objects.

Also inspected the provider's [historical export page](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
and public [export widget](https://widgets.dukascopy.com/en/historical-data-export),
including the resolved main bundle and historical-export component. Those inspected
resources did not establish an XAUUSD binary price divisor. Widget code refers to
an instrument metadata service; a verified response and a documented relationship
between instrument precision and binary scaling have not been obtained. No
price-magnitude heuristic, Forex fallback or third-party decoder assertion was
accepted as verification.

Potential access methods remain provider CSV export or legacy hourly BI5 HTTPS
objects; the documented requester-pays S3 route was not used. No AWS credentials,
billing authorization or third-party package were requested. Public documentation
and widget resources were retrieved only to investigate semantics.

## Pilot provenance / unavailable results

| Field | Result |
| --- | --- |
| Provider | Dukascopy |
| Canonical symbol | XAUUSD |
| Candidate provider identifier | XAUUSD for legacy feed, kept conceptually separate; no adapter mapping activated |
| Proposed pilot | 2026-10-29 00:00 UTC to 2026-10-30 00:00 UTC, one completed weekday |
| Historical range actually requested | None; stopped at scaling gate |
| Historical retrieval timestamp | Not applicable; no quote retrieval |
| Raw / valid / invalid counts | Not measured; no observations fetched, not evidence of an empty trading day |
| First / last normalized quote | Unavailable |
| Spread min / median / max | Unavailable |
| Price scaling | UNVERIFIED; no divisor selected |
| Timestamp semantics | Documentation describes UTC offsets; selected endpoint semantics not verified |
| Volumes | Documented ask/bid volume fields; XAUUSD sample availability and units unverified |
| Normalization rules | None activated; future boundary must use aware UTC and Decimal and reject invalid/crossed quotes |
| Five-minute aggregation | Deferred; no quote sample or separate bid/ask candle implementation |

Dukascopy would be a research feed, not necessarily the future MT5 broker feed.
Feed completeness, exact scaling, timestamp offsets, volume units and equivalence
to future broker quotes remain unverified. No profitability inference is made.

## Implementation boundary

Existing candle providers are unsuitable as a shortcut for bid/ask tick ingestion;
a future isolated quote provider should reuse MarketQuote validation and common
UTC handling without changing generic domain types. No decoder or guessed scale
was added. Accordingly no offline adapter tests or verified-scaling fixture can
honestly be claimed. The next authorized attempt needs authoritative instrument
encoding evidence or provider-exported decimal quotes with an unambiguous schema,
then a bounded one-day retrieval and synthetic offline decoder tests.

## Verification actually run

- pytest: **649 passed**, one existing Starlette/AnyIO warning; NSE regressions pass.
- Ruff: passed.
- Black: passed, 116 files unchanged.
- mypy: passed, 73 source files.
- Alembic current: **0006 (head)**; check: no schema drift.
- Git status/diff reviewed; whitespace check clean. Only this report is new and
  untracked. No source files modified, dependencies added or commit created.

Recommended commit: `docs: record blocked Dukascopy XAUUSD scaling verification`.
