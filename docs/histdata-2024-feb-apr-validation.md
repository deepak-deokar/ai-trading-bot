# XAUUSD G2C1 — February–April 2024 archive validation

## Outcome and scope

Downloaded only February, March and April 2024 XAU/USD Generic ASCII Tick archives
through HistData's normal free monthly form. All **10,100,418 rows** parsed using
the existing parser, with **zero invalid rows**. Analysis covers every calendar
date: **64 weekdays**, plus 26 weekend dates for boundary observations.

The daily gap is **not stable across the whole period**. Under the unchanged
fixed UTC−05:00 source interpretation, normal Monday–Thursday gaps are:

- February: 22:00–22:55 UTC (16 exact matches).
- March 4–7: 22:00–22:55 UTC (4 exact matches).
- March 11–27: 21:00–21:55 UTC (11 exact matches).
- April: 22:00–22:55 UTC (18 exact matches).

These are inclusive five-minute opening labels: 22:00–22:55 covers [22:00,23:00).
They are observations, not an accepted broker schedule. The April reversal is
unexplained; it must not be hidden by applying a DST correction to source stamps.
No strategy-readiness conclusion follows from successful parsing.

No database was accessed, no bars persisted, and January data and acceptance
policies remain unchanged. No strategies, backtester, MT5, risk, ML, dependency,
source-code or migration changes. G2C2 has not begun.

## Archive provenance

Archives reside in `/tmp`, outside Git. Canonical symbol is `XAUUSD`, provider is
`HISTDATA`, provider symbol is `XAU/USD`. Names are
`HISTDATA_COM_ASCII_XAUUSD_T_YYYYMM.zip`; each CSV member is
`DAT_ASCII_XAUUSD_T_YYYYMM.csv`. The JSON records download-page URLs, file sizes,
completion timestamps and analysis timestamp.

| Month | Bytes | SHA-256 |
| --- | ---: | --- |
| 2024-02 | 14,776,927 | `fedd441ffc428d7b8556f5328c3017fdc87b7088a0419dcd688c968ad9ceb2eb` |
| 2024-03 | 19,536,873 | `27719c29ee4aed7a36678a9050db035fa0330f66862a01f0cd8ccbbdc6e75457` |
| 2024-04 | 37,530,829 | `e7f0a460fc2b20fdc9c06fc247802a811fec43dad7255c592f17f8365754e207` |

## Method and descriptive rules

A temporary analysis script streamed each archive once through existing
`trading_bot.data.providers.histdata.parse_tick` (`histdata-ticks-v1`). Prices
remain Decimal, unscaled, with the existing positive/non-crossed quote checks.
No second parser was created. Source timestamps remain **fixed UTC−05:00 without
DST**, as specified by [HistData](https://www.histdata.com/f-a-q/data-files-detailed-specification/).
Every internal timestamp is aware UTC; America/New_York is not used.

Each source day spans [05:00 UTC, next 05:00 UTC), with 288 possible five-minute
bins. Count distinct UTC openings obtained by flooring valid tick timestamps;
compute the complement and group consecutive missing openings. Count raw and
invalid rows, and retain exact valid first/last timestamp extrema. Dates without
rows remain explicit. Nothing is interpolated, filled, rounded into a new price,
or written as OHLC. First/last timestamps and bin occupancy do not prove that all
intermediate ticks are present. Duplicate removal is not performed; tick counts
are source-row counts. No duplicate audit or independent price-feed comparison
is claimed in this checkpoint.

Discover exact missing-set frequencies separately for each month, separately for
Monday–Thursday and Friday; no January expected gap is supplied. The descriptive
normal-candidate rule is zero invalid rows plus exactly one 12-bin gap whose exact
signature occurs on **at least three Monday–Thursday dates in that month**. This
is a conservative analysis criterion, not a universal definition of normality.
It finds two supported signatures in March rather than choosing one modal time.

Friday labels describe a contiguous missing tail beginning at a discovered daily
gap start. Both March Friday signatures have only two examples each; they remain
limited descriptive observations, not accepted schedules. Their shape is also
observed in February/April for the 22:00 tail, and in March weekday gaps for the
21:00 start. Recurrence alone does not authorize research usability or ingestion.

Holiday labels are restricted to explicitly cited dates below. Other unmatched
weekday patterns remain UNEXPLAINED_GAP. Weekend observations are reported
separately and are not normal research candidates. Pattern discovery is descriptive
and retrospective, not a causal or leakage-safe training-data selection procedure.

## Monthly quality totals

Total ticks include weekend source dates. Weekday counts and the four classification
columns partition all Monday–Friday dates, including the no-data holiday.

| Month | Total ticks | Invalid | Weekdays | Normal candidates | Friday boundary | Holiday-associated | Unexplained weekday |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| February | 2,114,915 | 0 | 21 | 16 | 4 | 1 | 0 |
| March | 2,749,880 | 0 | 21 | 15 | 4 | 1 | 1 |
| April | 5,235,623 | 0 | 22 | 18 | 4 | 0 | 0 |

Weekday-only tick totals are respectively 2,040,059; 2,611,319; and 5,029,721.
There are **49 normal research-day candidates**, subject to later explicit policy
and validation, not 49 authorized persistence dates. Every normal candidate has
276 observed bins and 12 missing bins. Complete per-date counts, exact first/last
ticks and missing ranges are in [the JSON evidence](histdata-2024-feb-apr-validation.json).

## Friday and weekend findings

| Source Fridays | Count | Observed / missing bins | Missing openings (UTC) |
| --- | ---: | --- | --- |
| Feb 2, 9, 16, 23 | 4 | 204 / 84 | 22:00–next 04:55 |
| Mar 1, 8 | 2 | 204 / 84 | 22:00–next 04:55 |
| Mar 15, 22 | 2 | 192 / 96 | 21:00–next 04:55 |
| Mar 29 | 1 | 0 / 288 | 05:00–next 04:55 |
| Apr 5, 12, 19, 26 | 4 | 204 / 84 | 22:00–next 04:55 |

All 13 Saturdays have zero observations. Ordinary February and April Sundays
first appear in the 23:00 UTC bin. March 3 first appears at 23:00:01.232 UTC;
March 10, 17 and 24 first appear at 22:00:03.296, 22:00:01.259 and 22:00:01.120 UTC.
March 31 returns to 23:00:00.448 UTC. This is an observed feed boundary, not proof
of any venue's opening/closing schedule.

Additional weekend anomalies must not be hidden in the weekday totals:

- February 18: 70 observed bins, not the other February Sundays' 72. Extra missing
  openings at **23:15 and 23:20 UTC** remain unexplained; a nearby holiday is not
  sufficient evidence to explain isolated missing bins.
- March 31: 60 observed bins. Besides the later 23:00 first-observed bin, **April 1
  00:00–00:55 UTC** is absent within the March 31 source day. This 12-bin hole is
  unexplained. It is not assigned to the April archive or April 1 source day.

These partial days remain excluded from normal research candidates. No exception
is silently added to a schedule.

## Holiday context and weekday anomalies

**February 19:** 246 observed / 42 missing bins; absence 19:30–22:55 UTC,
including 30 extra bins at 19:30–21:55 relative to February's normal gap.
The [OPM 2024 calendar](https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/#url=2024)
identifies February 19 as Washington's Birthday. Classify descriptively as
HOLIDAY_ASSOCIATED_PATTERN: association only, not proven cause or usability.

**March 29:** no ticks, all 288 bins missing. The
[NYSE/ICE 2024 calendar](https://ir.theice.com/press/news-details/2021/NYSE-Group-Announces-2022-2023-and-2024-Holiday-and-Early-Closings-Calendar/default.aspx)
identifies March 29 as Good Friday. HOLIDAY_ASSOCIATED_PATTERN records this
coincidence, not a HistData closure guarantee. It is never a research candidate.

**March 28:** last tick **2024-03-28T20:58:59.311Z**, 192 observed / 96 missing
bins, absent 21:00–March 29 04:55 UTC. The extra 84 bins at 22:00–next 04:55
extend into the holiday's UTC date. Holiday adjacency is plausible context, but
this Thursday remains **UNEXPLAINED_GAP** without a provider schedule; it is not
promoted to a normal or usable day. There are no other unmatched weekday patterns
under the explicit rules above. April has no observed weekday anomaly under those
rules; this does not assert that April contains no external holidays.

The reviewed [HistData FAQ](https://www.histdata.com/f-a-q/) and format specification
do not provide an authoritative date-specific XAU/USD holiday schedule. No CME or
NYSE trading hours are substituted for HistData hours. Gaps may reflect closures,
feed conventions, or data loss; the archive alone cannot distinguish all causes.

## March DST comparison and April reversal

The [U.S. Naval Observatory's 2024 table](https://aa.usno.navy.mil/calculated/daylightsaving?submit=Get+Data&year=2024)
places the U.S. DST start on **March 10**. This date is external comparison context
only; it never changes timestamp normalization.

- Before: March 4, 5, 6, 7 all miss exactly **22:00–22:55 UTC**.
- After: March 11–14, 18–21 and 25–27 all miss exactly **21:00–21:55 UTC**.
- March 28 is a separate extended-gap exception; March 29 has no data.
- April 1 onward: all 18 Monday–Thursday dates return to **22:00–22:55 UTC**.

Thus January's gap persists in February and early March, shifts one hour earlier
for the observed middle/late-March normal days, then returns in April. The temporal
association with U.S. DST does not explain the entire sequence. In particular, the
April reversal is not explained by the U.S. March transition. No second timezone,
European DST rule or undocumented provider offset is invented to resolve it.
The source clock's real-world accuracy remains unverified against an independent
reference even though the documented fixed-offset parsing rule is preserved.

## Research policy and verification

Prefer only normal full research-day candidates, with a future explicitly scoped
pattern policy and separate quality checks. Holiday/Friday/weekend partial days
and unexplained gaps are excluded by default. Pattern explanation is not research
usability, and a candidate label is not strategy-readiness or persistence approval.
No existing AcceptedGapPattern was modified. No PostgreSQL expansion occurred.

Actually run:

- Download and complete local parser/coverage scan of the three authorized archives.
- Offline HistData regression tests: `pytest -q tests/unit/test_histdata.py`:
  **15 passed**.
- Evidence consistency checks: weekday classification totals, per-day 288-bin
  accounting, missing-range reconstruction, counts and archive SHA-256 agreement.
- `git status`, `git diff`, `git diff --cached`, and whitespace checks.

Only this Markdown report and its compact JSON are new. No project source or
configuration changed, so the full pytest/Ruff/Black/mypy/Alembic suite was not
rerun or claimed. Existing NSE behavior was not changed; no new full NSE regression
result is claimed. Nothing staged or committed; raw archives remain outside Git.

Recommended commit: `docs: validate February-April HistData XAUUSD coverage`.

Stopped at G2C1. No G2C2 work or three-month bar persistence.
