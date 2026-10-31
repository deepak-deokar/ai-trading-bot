# XAUUSD G2B2C — January gap reconciliation

## Scope and reproducibility

Read-only analysis of the existing January 2024 archive: **23 weekdays**, plus
8 weekend source dates to check Friday-to-Sunday continuity. No downloads,
database access, stored-bar changes, gap filling, dependencies or migrations.
Only this document and its compact JSON evidence are added; no project code changed.

Archive: `HISTDATA_COM_ASCII_XAUUSD_T_202401.zip`, member
`DAT_ASCII_XAUUSD_T_202401.csv`. SHA-256 verified before analysis:
`5b73733b7e1fcc5f10943602d83e54396338f7e106a2f80f03605eabf37a8990`.
Canonical symbol remains XAUUSD; provider HISTDATA identifies it as XAU/USD.

A temporary, non-repository analysis script streamed the CSV once using existing
`histdata.parse_tick` (Decimal validation unchanged). For each source date it
counted ticks, first/last UTC timestamps, and distinct five-minute opening bins.
Missing bins are the complement of those observed openings within the 288-bin
source day. Consecutive missing openings are grouped without creating price bars.
All **3,062,220 ticks** parsed successfully; zero invalid rows. This analysis
measures bin occupancy, not completeness of every tick within an occupied bin.

Source days are fixed UTC−05:00, with UTC bounds **[05:00, next 05:00)**, consistent
with [HistData's format specification](https://www.histdata.com/f-a-q/data-files-detailed-specification/).
Normalization uses the existing `histdata-ticks-v1` parser. Opening-bin membership
matches `bid-ask-utc-5minute-v1`; no bid/ask OHLC is rewritten here. Missing ranges
below include both endpoint opening labels. For example, 22:00–22:55 means the
12 bins covering [22:00, 23:00), not a measured exact tick-outage duration.

[JSON evidence](histdata-gap-reconciliation.json) records every date, exact first/
last tick, counts, missing runs, provenance and descriptive classification.

## Daily closure pattern

All **19 Monday–Thursday dates** contain no observations in the 12 bins
22:00–22:55 UTC. **17/19** have exactly those missing bins and 276 observed bins.
The two exceptions are January 1 and 15, which have additional missing bins.
Excluding these independently documented holiday dates, **17/17 normal candidate
Monday–Thursday days match exactly**, with zero exceptions:

- January 2, 3, 4;
- January 8, 9, 10, 11;
- January 16, 17, 18;
- January 22, 23, 24, 25;
- January 29, 30, 31.

Neutral description: `OBSERVED_DAILY_PROVIDER_CLOSURE_PATTERN`. Repetition supports
an observed feed pattern; it does not establish a universal broker maintenance
schedule or rule out systematic data omission.

## Fridays and weekend boundary

All four available Fridays were inspected. Three match exactly; January 12 is an
exception that must remain unexplained.

| Friday | Observed / missing bins | Exact last tick (UTC) | Missing opening range (UTC) | Classification |
| --- | --- | --- | --- | --- |
| January 5 | 204 / 84 | 2024-01-05T21:59:59.062Z | Jan 5 22:00–Jan 6 04:55 | WEEKEND_BOUNDARY_PATTERN |
| January 12 | 156 / 132 | 2024-01-12T17:59:59.620Z | Jan 12 18:00–Jan 13 04:55 | UNEXPLAINED_GAP |
| January 19 | 204 / 84 | 2024-01-19T21:59:58.647Z | Jan 19 22:00–Jan 20 04:55 | WEEKEND_BOUNDARY_PATTERN |
| January 26 | 204 / 84 | 2024-01-26T21:59:58.987Z | Jan 26 22:00–Jan 27 04:55 | WEEKEND_BOUNDARY_PATTERN |

January 12 has **48 extra missing bins, 18:00–21:55 UTC**, relative to the other
Fridays. Proximity to MLK Day is insufficient to explain this four-hour early end.
Its later 22:00 onward absence matches the observed weekend component, but the
overall day is classified UNEXPLAINED_GAP.

All four Saturdays have zero ticks. On each following Sunday, the first tick is:

| Sunday | First tick (UTC) |
| --- | --- |
| January 7 | 2024-01-07T23:00:02.003Z |
| January 14 | 2024-01-14T23:00:00.337Z |
| January 21 | 2024-01-21T23:00:01.094Z |
| January 28 | 2024-01-28T23:00:01.078Z |

Each Sunday has 72 observed bins (23:00–next 04:55), with none earlier in its source
day. Thus the archive consistently remains empty across the intervening weekend
until Sunday around 23:00 UTC. These observations do not prove actual venue hours.

**January 19 conclusion:** its 72 additional missing bins beyond the daily
12-bin gap are consistent with January 5 and 26, supporting the descriptive
WEEKEND_BOUNDARY_PATTERN label. Its G2B2B research-usability result remains false.

## Mondays and January 15

| Monday | Observed / missing bins | Missing opening range (UTC) | Additional bins beyond daily pattern |
| --- | --- | --- | ---: |
| January 1 | 72 / 216 | 05:00–22:55 | 204 (05:00–21:55) |
| January 8 | 276 / 12 | 22:00–22:55 | 0 |
| January 15 | 246 / 42 | 19:30–22:55 | 30 (19:30–21:55) |
| January 22 | 276 / 12 | 22:00–22:55 | 0 |
| January 29 | 276 / 12 | 22:00–22:55 | 0 |

Ordinary observed Mondays (8, 22, 29) have no extra week-open gap: their first
observations fall in the 05:00 UTC opening bin, after the Sunday reopening.
January 1 first observes a tick at 23:00:00.312 UTC. January 15 has observations
from its 05:00 opening bin, an extended afternoon gap, and returns in the 23:00 bin.
It is different from ordinary Mondays, not an ordinary Monday opening delay.

The [OPM 2024 federal holiday schedule](https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/#url=2024)
identifies January 1 as New Year's Day and January 15 as Martin Luther King Jr.'s
Birthday. This is external calendar context only. The unusual January 15 interval
and documented holiday support **HOLIDAY_ASSOCIATED_PATTERN**, meaning temporal
association, not confirmed causation. January 1 receives the same descriptive
label. Neither date becomes research-usable on this basis.

No authoritative January 2024 HistData XAU/USD holiday/session schedule was found
in the reviewed [HistData FAQ](https://www.histdata.com/f-a-q/) and format
specification. The FAQ disclaims data certification and discusses reporting gaps;
it does not establish the cause of these specific absences. No CME futures hours
were used to define HistData XAUUSD hours. The true cause of the January 15 gap,
and whether any portion represents data loss, remains unverified.

## Deterministic descriptive labels and V1 policy

For this archive only, apply these explicit rules (documentation, not new runtime
classification code or a changed acceptance policy):

1. Monday–Thursday dates with exactly the 12 daily missing bins:
   NORMAL_OBSERVED_PROVIDER_PATTERN (17 dates).
2. Fridays with exactly the 84-bin tail, and the matching observed weekend
   structure: WEEKEND_BOUNDARY_PATTERN (January 5, 19, 26; weekend dates separately
   recorded in JSON). The rule does not absorb extra earlier gaps.
3. The explicitly listed January 1 and 15 patterns, with the cited holiday dates:
   HOLIDAY_ASSOCIATED_PATTERN. No automatic rule labels arbitrary holiday gaps.
4. Any other weekday missing-set pattern: UNEXPLAINED_GAP (January 12).

**Pattern explanation does not imply research usability.** Prefer the 17 normal
full research-day candidates for V1, subject to an explicitly scoped acceptance
of the daily 12-bin pattern and other data-quality checks. Exclude holiday partial
days, Friday partial days and unexplained days by default. Bin coverage does not
establish complete ticks, feed accuracy or strategy readiness. No accepted policy
is broadened by this report; G2B2B's bounded five-day results remain unchanged.
Missing bins remain missing. No interpolation, forward fill or synthetic prices.

## Verification and limits

Executed the local full-archive read-only analysis and checked the weekday counts,
zero invalid rows, exact normal-day sets, Friday exception and original G2B2B
observed/missing counts. Git status, git diff, git diff --cached and whitespace
checks were run. Only two new documentation/evidence files; nothing staged or
committed. No source/configuration changes, so no new tests or full quality-suite
run was required. The prior 683-test result is not claimed as a new run.

Findings are specific to this archive and month. There is no independent tick
reference or authoritative provider schedule proving closure versus data loss.
NSE, strategies, backtester and persistence are untouched. No next phase begun.

Recommended commit: `docs: reconcile January HistData XAUUSD gap patterns`.
