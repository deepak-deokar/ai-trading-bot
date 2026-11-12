# G2C4E2A — unseen May–July 2024 data-quality audit

**Data validation only.** February–April remains DEVELOPMENT / IN-SAMPLE.
May–July is the FIRST UNSEEN VALIDATION PERIOD: data quality inspected, strategy
outcomes not inspected. August–October is LOCKED HOLDOUT and was not downloaded,
parsed or evaluated. E1 and previous reports remain unchanged. No strategy signal
counts, markouts, benchmarks, trade outcomes or profitability were computed on
these archives. No database persistence, policy activation, migration or dependency
change occurred. Full regression tests use their existing fixtures; they never
receive these validation archives.

## Sources and unchanged semantics

Only the three authorized Generic ASCII tick archives were retrieved via the
normal HistData free monthly forms and their `/get.php` endpoint. Raw files and
download provenance are outside Git in `/tmp/histdata-validation-2024`.
The JSON records exact source URLs, retrieval timestamps, filenames, checksums and
sizes. Existing February–April archives were not overwritten or re-downloaded.

| Month | File | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| 2024-05 | HISTDATA_COM_ASCII_XAUUSD_T_202405.zip | 35,612,441 | `ec9128f89afb2091912310ef55a1cd6006475f27817707a0d2c08983fd74b5aa` |
| 2024-06 | HISTDATA_COM_ASCII_XAUUSD_T_202406.zip | 32,432,426 | `a94e12301134b02899f8402d6f990fb65d2e2a837daf243cb2a642625cb8a980` |
| 2024-07 | HISTDATA_COM_ASCII_XAUUSD_T_202407.zip | 39,238,820 | `cec29b35b592b3ca9810b84e0af81ea6e84af78d1d16f22e2ee2eb4bddb7c810` |

The existing `parse_tick` and `five_minute_view` are unchanged. HistData's
[format specification](https://www.histdata.com/f-a-q/data-files-detailed-specification/)
defines timestamp,bid,ask,volume with millisecond timestamps and EST without daylight
saving adjustments. Parsing attaches **fixed UTC−05:00**, then converts to aware
UTC. No America/New_York/DST reinterpretation, scaling, multiplier or clock repair.
Each source day is [05:00 UTC, next 05:00 UTC), giving 288 theoretical bins.
A source day can include a next-calendar-date UTC tail; this does not authorize
reading another source month or holdout archive.

Valid ticks are aggregated by the existing function into separate BID and ASK
OHLC, with opening-time five-minute labels. No midpoint OHLC, missing-bin filling,
interpolation or persistence. Only per-day bar content hashes are retained in the
report, not a new full bar dataset. All ticks contribute; duplicate timestamps and
identical observations are counted separately and retained with stable source
order. Invalid/crossed observations are rejected and counted, never repaired.

## Monthly coverage and integrity

| Month | Raw / valid ticks | Invalid | Crossed | Duplicate timestamps / exact observations | Regressions | Proposed days |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-05 | 5,040,823 / 5,040,823 | 0 | 0 | 0 / 0 | 0 | 17 |
| 2024-06 | 4,666,550 / 4,666,550 | 0 | 0 | 0 / 0 | 0 | 15 |
| 2024-07 | 5,682,739 / 5,682,739 | 0 | 0 | 0 / 0 | 0 | 18 |

| Month | Source decimal places (price count) | Effective places (price count) | Aligned 0.001 | Aligned 0.01 | Finer than 0.001 |
| --- | --- | --- | ---: | ---: | ---: |
| 2024-05 | {'6': 10081646} | {'3': 10079086, '2': 151, '0': 2345, '1': 64} | 10,081,646 | 2,560 | 0 |
| 2024-06 | {'6': 9333100} | {'3': 9328934, '0': 3860, '2': 137, '1': 169} | 9,333,100 | 4,166 | 0 |
| 2024-07 | {'6': 11365478} | {'3': 11360123, '0': 4531, '2': 489, '1': 335} | 11,365,478 | 5,355 | 0 |

Prices cross the financial boundary as Decimal. Alignment counts count BID and ASK
separately (two prices per valid tick); formatted trailing zeros are not additional
effective precision. This describes source-price precision only, never a verified
MT5 contract tick size. Volume field values/counts are recorded per day in JSON;
source `0` is not interpreted as meaningful global gold volume.

## Independent monthly pattern discovery

The pre-existing audit's conservative descriptive criterion is retained: discover
exact missing sets separately per month; a proposed normal pattern needs at least
three non-holiday Monday–Thursday matches of a single contiguous 12-bin absence,
with valid observations and no invalid/out-of-range or reversed-time records.
The **UTC clock is not supplied**. This criterion may fail to recognize other
legitimate patterns; unmatched days stay excluded. It does not establish closure
causality. HistData coverage patterns are not broker execution schedules.

### 2024-05

Classifications: `{'NORMAL_WEEKDAY_CANDIDATE': 17, 'FRIDAY': 5, 'SATURDAY': 4, 'SUNDAY': 4, 'HOLIDAY_ASSOCIATED': 1}`.

Observed daily missing openings: **22:00–22:55 UTC**, inclusive five-minute labels. Exact match dates: 2024-05-01, 2024-05-02, 2024-05-06, 2024-05-07, 2024-05-08, 2024-05-09, 2024-05-13, 2024-05-14, 2024-05-15, 2024-05-16, 2024-05-20, 2024-05-21, 2024-05-22, 2024-05-23, 2024-05-28, 2024-05-29, 2024-05-30.

- 2024-05-27: HOLIDAY_ASSOCIATED; 246 observed / 42 missing; 30 extra missing bins versus the reference pattern. Context: Memorial Day.

### 2024-06

Classifications: `{'SATURDAY': 5, 'SUNDAY': 5, 'NORMAL_WEEKDAY_CANDIDATE': 15, 'FRIDAY': 4, 'HOLIDAY_ASSOCIATED': 1}`.

Observed daily missing openings: **22:00–22:55 UTC**, inclusive five-minute labels. Exact match dates: 2024-06-03, 2024-06-04, 2024-06-05, 2024-06-06, 2024-06-10, 2024-06-11, 2024-06-12, 2024-06-13, 2024-06-17, 2024-06-18, 2024-06-20, 2024-06-24, 2024-06-25, 2024-06-26, 2024-06-27.

- 2024-06-19: HOLIDAY_ASSOCIATED; 246 observed / 42 missing; 30 extra missing bins versus the reference pattern. Context: Juneteenth National Independence Day.

### 2024-07

Classifications: `{'NORMAL_WEEKDAY_CANDIDATE': 18, 'HOLIDAY_ASSOCIATED': 1, 'FRIDAY': 4, 'SATURDAY': 4, 'SUNDAY': 4}`.

Observed daily missing openings: **22:00–22:55 UTC**, inclusive five-minute labels. Exact match dates: 2024-07-01, 2024-07-02, 2024-07-03, 2024-07-08, 2024-07-09, 2024-07-10, 2024-07-11, 2024-07-15, 2024-07-16, 2024-07-17, 2024-07-18, 2024-07-22, 2024-07-23, 2024-07-24, 2024-07-25, 2024-07-29, 2024-07-30, 2024-07-31.

- 2024-07-04: HOLIDAY_ASSOCIATED; 246 observed / 42 missing; 30 extra missing bins versus the reference pattern. Context: Independence Day.


## Holiday and weekend context

[OPM's 2024 calendar](https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/#url=2024)
identifies May 27 (Memorial Day), June 19 (Juneteenth), and July 4 (Independence Day).
These dates are excluded even if their coverage looks ordinary. A holiday label
records temporal association only; it does not prove why a gap occurred. This is
not an exhaustive worldwide holiday calendar. Other abnormal days remain unexplained.
No CME, NYSE or other venue hours are substituted for HistData XAU/USD hours; an
authoritative date-specific HistData schedule has not been established.

Fridays, Saturdays and Sundays remain excluded. Their exact first/last ticks and
missing sets are retained below/in JSON rather than extending the normal daily
gap to authorize partial days. Zero-data status is a separate flag, including on
weekend/holiday dates. Pattern explanation does not confer research usability.

Across all three months, all 13 Fridays have exactly 204 observed / 84 missing
bins: missing openings 22:00 through next 04:55 UTC. All 13 Saturdays have no
observations (288 missing). All 13 Sundays have 72 observed / 216 missing bins:
missing openings 05:00–22:55 UTC, observations begin in the 23:00 bin.
No exceptions to those per-weekday coverage signatures were found in these archives.
All remain excluded from normal research candidates.

May 27, June 19 and July 4 each have 246 observed / 42 missing bins. Their missing
openings are 19:30–22:55 UTC: the usual 12-bin pattern plus **30 additional bins at
19:30–21:55 UTC**. These are holiday-associated coverage exceptions, not proven
holiday closure causes. No other unexplained coverage anomalies were found under
the stated five-minute criterion. This does not establish tick-level completeness.

## Proposed validation policy — not activated

Each proposed segment is bound to its month/archive SHA-256, audit version,
`histdata-ticks-v1`, `bid-ask-utc-5minute-v1`, HISTDATA, XAUUSD / XAU/USD,
fixed UTC−05:00 and five-minute opening labels. The exact allowed source-date
list is mandatory in addition to segment bounds. No acceptance outside those
observed dates, no universal UTC window, and no extension of the development YAML.
A later authorized persistence step must independently verify provenance, valid
observations and **exact missing-set equality**. Fewer missing bins also fail;
additional unexplained gaps cannot be learned into acceptance.

| Segment bounds | Missing UTC openings | Explicit candidate dates | Archive binding |
| --- | --- | ---: | --- |
| 2024-05-01–2024-05-30 | 22:00–22:55 | 17 | `ec9128f89afb2091912310ef55a1cd6006475f27817707a0d2c08983fd74b5aa` |
| 2024-06-03–2024-06-27 | 22:00–22:55 | 15 | `a94e12301134b02899f8402d6f990fb65d2e2a837daf243cb2a642625cb8a980` |
| 2024-07-01–2024-07-31 | 22:00–22:55 | 18 | `cec29b35b592b3ca9810b84e0af81ea6e84af78d1d16f22e2ee2eb4bddb7c810` |

**50 proposed days**; none approved or persisted by this checkpoint. JSON contains the explicit date allowlists and exact missing sets.

## Every source-calendar date

Each row expects 288 bins. `Unexpected` means additional missing openings relative
to the nearest independently observed monthly signature (minimum symmetric
set difference, deterministic tie-break); it is a descriptive reference, not an
activated schedule. JSON also reports expected-pattern bins that were present,
out-of-range openings, all missing UTC timestamps, and no-data/tick-presence flags.
No-pattern months would treat every missing bin as unexplained.
Times below are exact UTC tick observations, not inferred session endpoints.

| Date | Valid ticks | Observed | Missing | Unexpected | First UTC tick | Last UTC tick | Classification |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| 2024-05-01 | 225,512 | 276 | 12 | 0 | 2024-05-01T05:00:00.077000+00:00 | 2024-05-02T04:59:59.476000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-02 | 218,255 | 276 | 12 | 0 | 2024-05-02T05:00:00.129000+00:00 | 2024-05-03T04:59:56.333000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-03 | 179,421 | 204 | 84 | 72 | 2024-05-03T05:00:00.109000+00:00 | 2024-05-03T21:59:58.987000+00:00 | FRIDAY |
| 2024-05-04 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-05-05 | 44,327 | 72 | 216 | 204 | 2024-05-05T23:00:01.119000+00:00 | 2024-05-06T04:59:59.548000+00:00 | SUNDAY |
| 2024-05-06 | 176,170 | 276 | 12 | 0 | 2024-05-06T05:00:00.101000+00:00 | 2024-05-07T04:59:58.502000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-07 | 165,793 | 276 | 12 | 0 | 2024-05-07T05:00:00.157000+00:00 | 2024-05-08T04:59:58.806000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-08 | 138,187 | 276 | 12 | 0 | 2024-05-08T05:00:05.083000+00:00 | 2024-05-09T04:59:55.572000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-09 | 197,487 | 276 | 12 | 0 | 2024-05-09T05:00:00.336000+00:00 | 2024-05-10T04:59:59.586000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-10 | 188,089 | 204 | 84 | 72 | 2024-05-10T05:00:00.190000+00:00 | 2024-05-10T21:59:59.104000+00:00 | FRIDAY |
| 2024-05-11 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-05-12 | 34,278 | 72 | 216 | 204 | 2024-05-12T23:00:01.144000+00:00 | 2024-05-13T04:59:48.083000+00:00 | SUNDAY |
| 2024-05-13 | 174,035 | 276 | 12 | 0 | 2024-05-13T05:00:00.080000+00:00 | 2024-05-14T04:59:56.729000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-14 | 224,337 | 276 | 12 | 0 | 2024-05-14T05:00:00.096000+00:00 | 2024-05-15T04:59:59.447000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-15 | 274,046 | 276 | 12 | 0 | 2024-05-15T05:00:01.457000+00:00 | 2024-05-16T04:59:58.784000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-16 | 210,176 | 276 | 12 | 0 | 2024-05-16T05:00:00.445000+00:00 | 2024-05-17T04:59:59.957000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-17 | 183,442 | 204 | 84 | 72 | 2024-05-17T05:00:00.058000+00:00 | 2024-05-17T21:59:59.782000+00:00 | FRIDAY |
| 2024-05-18 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-05-19 | 52,907 | 72 | 216 | 204 | 2024-05-19T23:00:02.985000+00:00 | 2024-05-20T04:59:58.032000+00:00 | SUNDAY |
| 2024-05-20 | 291,371 | 276 | 12 | 0 | 2024-05-20T05:00:00.041000+00:00 | 2024-05-21T04:59:59.836000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-21 | 238,040 | 276 | 12 | 0 | 2024-05-21T05:00:00.140000+00:00 | 2024-05-22T04:59:59.935000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-22 | 273,515 | 276 | 12 | 0 | 2024-05-22T05:00:00.499000+00:00 | 2024-05-23T04:59:57.962000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-23 | 300,133 | 276 | 12 | 0 | 2024-05-23T05:00:00.171000+00:00 | 2024-05-24T04:59:56.942000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-24 | 165,433 | 204 | 84 | 72 | 2024-05-24T05:00:00.104000+00:00 | 2024-05-24T21:59:58.255000+00:00 | FRIDAY |
| 2024-05-25 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-05-26 | 32,205 | 72 | 216 | 204 | 2024-05-26T23:00:01.264000+00:00 | 2024-05-27T04:59:54.337000+00:00 | SUNDAY |
| 2024-05-27 | 158,268 | 246 | 42 | 30 | 2024-05-27T05:00:01.317000+00:00 | 2024-05-28T04:59:59.553000+00:00 | HOLIDAY_ASSOCIATED |
| 2024-05-28 | 217,267 | 276 | 12 | 0 | 2024-05-28T05:00:00.107000+00:00 | 2024-05-29T04:59:59.264000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-29 | 218,501 | 276 | 12 | 0 | 2024-05-29T05:00:00.066000+00:00 | 2024-05-30T04:59:57.704000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-30 | 248,228 | 276 | 12 | 0 | 2024-05-30T05:00:00.113000+00:00 | 2024-05-31T04:59:59.631000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-05-31 | 211,400 | 204 | 84 | 72 | 2024-05-31T05:00:00.285000+00:00 | 2024-05-31T21:59:58.145000+00:00 | FRIDAY |
| 2024-06-01 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-06-02 | 40,325 | 72 | 216 | 204 | 2024-06-02T23:00:01.677000+00:00 | 2024-06-03T04:59:57.554000+00:00 | SUNDAY |
| 2024-06-03 | 246,299 | 276 | 12 | 0 | 2024-06-03T05:00:00.064000+00:00 | 2024-06-04T04:59:59.775000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-04 | 262,948 | 276 | 12 | 0 | 2024-06-04T05:00:00.880000+00:00 | 2024-06-05T04:59:59.525000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-05 | 236,673 | 276 | 12 | 0 | 2024-06-05T05:00:00.079000+00:00 | 2024-06-06T04:59:59.257000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-06 | 231,967 | 276 | 12 | 0 | 2024-06-06T05:00:00.060000+00:00 | 2024-06-07T04:59:59.987000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-07 | 253,350 | 204 | 84 | 72 | 2024-06-07T05:00:00.089000+00:00 | 2024-06-07T21:59:58.139000+00:00 | FRIDAY |
| 2024-06-08 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-06-09 | 32,215 | 72 | 216 | 204 | 2024-06-09T23:00:01.600000+00:00 | 2024-06-10T04:59:59.521000+00:00 | SUNDAY |
| 2024-06-10 | 202,419 | 276 | 12 | 0 | 2024-06-10T05:00:00.099000+00:00 | 2024-06-11T04:59:59.813000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-11 | 222,087 | 276 | 12 | 0 | 2024-06-11T05:00:00.065000+00:00 | 2024-06-12T04:59:59.823000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-12 | 266,700 | 276 | 12 | 0 | 2024-06-12T05:00:00.125000+00:00 | 2024-06-13T04:59:59.976000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-13 | 247,956 | 276 | 12 | 0 | 2024-06-13T05:00:00.127000+00:00 | 2024-06-14T04:59:59.063000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-14 | 207,219 | 204 | 84 | 72 | 2024-06-14T05:00:00.069000+00:00 | 2024-06-14T21:59:58.928000+00:00 | FRIDAY |
| 2024-06-15 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-06-16 | 41,232 | 72 | 216 | 204 | 2024-06-16T23:00:00.628000+00:00 | 2024-06-17T04:59:59.898000+00:00 | SUNDAY |
| 2024-06-17 | 204,051 | 276 | 12 | 0 | 2024-06-17T05:00:00.049000+00:00 | 2024-06-18T04:59:59.856000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-18 | 195,999 | 276 | 12 | 0 | 2024-06-18T05:00:00.007000+00:00 | 2024-06-19T04:59:45.847000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-19 | 136,130 | 246 | 42 | 30 | 2024-06-19T05:00:00.246000+00:00 | 2024-06-20T04:59:56.939000+00:00 | HOLIDAY_ASSOCIATED |
| 2024-06-20 | 221,050 | 276 | 12 | 0 | 2024-06-20T05:00:00.100000+00:00 | 2024-06-21T04:59:59.440000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-21 | 207,480 | 204 | 84 | 72 | 2024-06-21T05:00:00.094000+00:00 | 2024-06-21T21:59:58.085000+00:00 | FRIDAY |
| 2024-06-22 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-06-23 | 45,225 | 72 | 216 | 204 | 2024-06-23T23:00:01.576000+00:00 | 2024-06-24T04:59:59.891000+00:00 | SUNDAY |
| 2024-06-24 | 218,176 | 276 | 12 | 0 | 2024-06-24T05:00:00.193000+00:00 | 2024-06-25T04:59:59.842000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-25 | 241,545 | 276 | 12 | 0 | 2024-06-25T05:00:00.144000+00:00 | 2024-06-26T04:59:59.880000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-26 | 246,694 | 276 | 12 | 0 | 2024-06-26T05:00:00.081000+00:00 | 2024-06-27T04:59:58.045000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-27 | 236,918 | 276 | 12 | 0 | 2024-06-27T05:00:00.254000+00:00 | 2024-06-28T04:59:59.627000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-06-28 | 190,413 | 204 | 84 | 72 | 2024-06-28T05:00:00.129000+00:00 | 2024-06-28T21:59:58.463000+00:00 | FRIDAY |
| 2024-06-29 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-06-30 | 31,479 | 72 | 216 | 204 | 2024-06-30T23:00:01.484000+00:00 | 2024-07-01T04:59:59.159000+00:00 | SUNDAY |
| 2024-07-01 | 216,358 | 276 | 12 | 0 | 2024-07-01T05:00:00.063000+00:00 | 2024-07-02T04:59:59.962000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-02 | 212,108 | 276 | 12 | 0 | 2024-07-02T05:00:00.264000+00:00 | 2024-07-03T04:59:59.262000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-03 | 224,029 | 276 | 12 | 0 | 2024-07-03T05:00:00.117000+00:00 | 2024-07-04T04:59:55.868000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-04 | 135,835 | 246 | 42 | 30 | 2024-07-04T05:00:00.537000+00:00 | 2024-07-05T04:59:59.945000+00:00 | HOLIDAY_ASSOCIATED |
| 2024-07-05 | 209,277 | 204 | 84 | 72 | 2024-07-05T05:00:00.247000+00:00 | 2024-07-05T21:59:58.253000+00:00 | FRIDAY |
| 2024-07-06 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-07-07 | 42,321 | 72 | 216 | 204 | 2024-07-07T23:00:01.233000+00:00 | 2024-07-08T04:59:57.620000+00:00 | SUNDAY |
| 2024-07-08 | 235,086 | 276 | 12 | 0 | 2024-07-08T05:00:00.131000+00:00 | 2024-07-09T04:59:59.690000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-09 | 223,935 | 276 | 12 | 0 | 2024-07-09T05:00:00.244000+00:00 | 2024-07-10T04:59:59.643000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-10 | 193,877 | 276 | 12 | 0 | 2024-07-10T05:00:00.095000+00:00 | 2024-07-11T04:59:59.707000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-11 | 282,979 | 276 | 12 | 0 | 2024-07-11T05:00:00.060000+00:00 | 2024-07-12T04:59:44.055000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-12 | 195,557 | 204 | 84 | 72 | 2024-07-12T05:00:01.201000+00:00 | 2024-07-12T21:59:59.938000+00:00 | FRIDAY |
| 2024-07-13 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-07-14 | 32,302 | 72 | 216 | 204 | 2024-07-14T23:00:01.293000+00:00 | 2024-07-15T04:59:58.986000+00:00 | SUNDAY |
| 2024-07-15 | 240,123 | 276 | 12 | 0 | 2024-07-15T05:00:00.143000+00:00 | 2024-07-16T04:59:58.359000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-16 | 266,490 | 276 | 12 | 0 | 2024-07-16T05:00:00.117000+00:00 | 2024-07-17T04:59:56.574000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-17 | 303,235 | 276 | 12 | 0 | 2024-07-17T05:00:00.188000+00:00 | 2024-07-18T04:59:57.799000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-18 | 283,089 | 276 | 12 | 0 | 2024-07-18T05:00:00.464000+00:00 | 2024-07-19T04:59:59.034000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-19 | 216,252 | 204 | 84 | 72 | 2024-07-19T05:00:00.088000+00:00 | 2024-07-19T21:59:59.097000+00:00 | FRIDAY |
| 2024-07-20 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-07-21 | 46,708 | 72 | 216 | 204 | 2024-07-21T23:00:00.372000+00:00 | 2024-07-22T04:59:59.285000+00:00 | SUNDAY |
| 2024-07-22 | 238,964 | 276 | 12 | 0 | 2024-07-22T05:00:00.090000+00:00 | 2024-07-23T04:59:58.244000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-23 | 247,569 | 276 | 12 | 0 | 2024-07-23T05:00:00.304000+00:00 | 2024-07-24T04:59:59.510000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-24 | 297,785 | 276 | 12 | 0 | 2024-07-24T05:00:00.063000+00:00 | 2024-07-25T04:59:58.453000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-25 | 311,982 | 276 | 12 | 0 | 2024-07-25T05:00:00.164000+00:00 | 2024-07-26T04:59:58.956000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-26 | 194,364 | 204 | 84 | 72 | 2024-07-26T05:00:00.062000+00:00 | 2024-07-26T21:59:59.948000+00:00 | FRIDAY |
| 2024-07-27 | 0 | 0 | 288 | 276 | — | — | SATURDAY |
| 2024-07-28 | 54,838 | 72 | 216 | 204 | 2024-07-28T23:00:01.380000+00:00 | 2024-07-29T04:59:59.842000+00:00 | SUNDAY |
| 2024-07-29 | 235,378 | 276 | 12 | 0 | 2024-07-29T05:00:00.246000+00:00 | 2024-07-30T04:59:59.898000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-30 | 253,366 | 276 | 12 | 0 | 2024-07-30T05:00:00.049000+00:00 | 2024-07-31T04:59:59.956000+00:00 | NORMAL_WEEKDAY_CANDIDATE |
| 2024-07-31 | 288,932 | 276 | 12 | 0 | 2024-07-31T05:00:00.058000+00:00 | 2024-08-01T04:59:59.603000+00:00 | NORMAL_WEEKDAY_CANDIDATE |

## Verification and limits

The offline audit can be reproduced with:

```sh
PYTHONPATH=src .venv/bin/python scripts/audit_histdata_validation.py \
  /tmp/histdata-validation-2024
```

The directory must include the three archives and their download-provenance JSON
sidecars. No network or database access exists in the audit runner. Normal pytest
uses only synthetic fixtures, not these downloaded archives.

Coverage at five-minute resolution does not prove tick-level completeness or feed
authority. Price alignment is not broker contract verification. Holiday causality,
source clock accuracy against an independent reference, and execution suitability
remain unverified. This is proposed data selection based on coverage only, not a
strategy-performance result. E1 remains frozen; no follow-on experiment began.

### Checks actually run

- Complete scan: **15,390,112 raw/valid ticks**, zero invalid/crossed quotes,
  duplicate timestamps, identical duplicate observations or timestamp reversals.
- All **30,780,224** BID/ASK price values align exactly to 0.001; none are finer.
  All are formatted to six decimal places. Only 12,081 align to 0.01.
  All source volume fields are `0`; no meaningful global volume is inferred.
- Per-day counts, all 92 date rows, 288-bin accounting, proposal exact equality,
  exclusions, archive hashes and canonical report hash verified.
- Focused parser/new audit tests: **22 passed**. Full suite: **978 passed**,
  including existing coverage/policy/NSE tests; one existing Starlette warning.
- Ruff passed; Black passed (183 files); mypy passed (96 source files).
- Alembic current: **0008 (head)**; Alembic check: **no schema drift**.
- Git status, working/staged diffs and whitespace checks reviewed. No files staged
  or committed. Raw archives remain outside Git. Existing tracked source/config
  and earlier reports are byte-identical except the intended experiment-log append.

Created: this Markdown/JSON pair, `scripts/audit_histdata_validation.py`, and
`tests/unit/test_histdata_validation_audit.py`. Modified only the experiment log.
The two pre-existing untracked $3,000 sensitivity reports are untouched.

Recommended commit: `feat: audit unseen May-July HistData validation coverage`.

Stopped at G2C4E2A. No validation-day approval/persistence or strategy evaluation.
