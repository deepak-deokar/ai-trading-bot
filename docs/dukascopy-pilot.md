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

## G2B1A — independent scaling comparison: INCOMPLETE

This follow-up attempted access to both raw and official decoded representations
for **2026-10-29 UTC only**. The earlier G2B1 findings above are retained as the
previous checkpoint; unlike that checkpoint, this attempt requested raw objects.
No alternative day, bulk download or production decoder was used.

### Access evidence

| Representation / URL | Observed outcome |
| --- | --- |
| Daily-format candidate: `https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/09/29_ticks.bi5` | HTTP 429; no BI5 bytes obtained |
| Documented S3 daily layout: `https://cfg-public-proper-wallaby.s3.eu-west-1.amazonaws.com/XAUUSD/2026/09/29_ticks.bi5` | Anonymous HTTP 403; no BI5 bytes obtained |
| Same-day legacy diagnostic: `https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/09/29/12h_ticks.bi5` | HTTP 429; no BI5 bytes obtained |
| Official historical-export client bundle on `widgets.dukascopy.com` | HTTP 200; public JavaScript only, not price data |
| Official widget `config.json` | Public configuration identified `https://jetta.dukascopy.com` as its data service |
| `https://jetta.dukascopy.com/instruments/XAU-USD` | HTTP 202 with zero-byte body; no usable instrument metadata or decoded prices |

The metadata request follows the public client's slash-to-hyphen instrument-name
conversion. No metadata response confirmed this identifier. HTTP errors do not
prove that October 29 history is absent. No retries of the rate-limited feed,
authentication, billing setup or access-control workaround were attempted.
The S3 path is based on the provider's documented daily layout, not a successfully
listed or verified object. Requester-pays credentials were not used.

Official comparison route inspected:
[Historical Data Export](https://widgets.dukascopy.com/en/historical-data-export).
The export component calls its official data client separately for BID and ASK
and generates CSV. Its inspected timestamp formatter emits seconds with an offset,
without milliseconds; direct CSV timestamp matching would therefore require care
with multiple ticks per second. No CSV or JForex historical output was obtained,
and the output's actual price precision was not verified.

The [provider guide](https://www.dukascopy.com/wiki/en/development/data-export/)
distinguishes daily millisecond offsets from legacy hourly offsets. Daily UTC
interpretation is documented but **not independently verified for this date**:
there are no matched timestamps. The hourly diagnostic is not treated as daily
format evidence.

### Comparison outcome

- Date: 2026-10-29, requested daily range `[00:00 UTC, 2026-10-30 00:00 UTC)`.
- Raw example bid/ask integers: **unavailable**; no binary records received.
- Official decoded comparison bid/ask: **unavailable**.
- Matched observations: **0** (target at least 50 not reached).
- Exactly consistent: **0 comparisons performed**, not a verified success rate.
- Inconsistent: **not evaluable**; no pairs to compare.
- Candidate or confirmed divisor: **none derived**; no presumed scale tested.
- Timestamp conclusion: **UNVERIFIED**; cannot confirm alignment or day-relative
  offsets against official observations.
- Dukascopy-only range sanity check: **not performed**, no dated quote prices.
- No float-based price comparisons, rounding tolerance or external-provider
  pricing was used. No financial values were fabricated.

The blocking condition is access to two usable representations, not evidence of
an incorrect divisor. A subsequent authorized attempt needs the actual daily BI5
object and official timestamped decoded quotes for the same interval, preserving
sufficient time/price precision for at least 50 exact bid/ask comparisons. No
production assumption is justified until that evidence exists.

### G2B1A changes and checks

Only this report changed. No source files, tests, dependencies, schema or database
contents changed. Temporary public-resource downloads/probe scripts stayed under
`/tmp`; no raw price files or credentials were committed. `git status`, `git diff`
and `git diff --check` were run. The earlier 649-test result belongs to G2B1;
tests/quality tools were not rerun for this documentation-only follow-up, as
permitted by G2B1A. Nothing committed; G2B2 has not begun.

Recommended commit: `docs: record Dukascopy scaling comparison access blockers`.
