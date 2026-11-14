# XAUUSD G2C4G3 — taxonomy v2 correction

`xauusd-market-state-taxonomy-v2` uses the new
`xauusd-market-state-features-v2` attribute `volatility_ratio_12_36`.
The core remains volatility36 × efficiency12 (at most nine core states), with
expansion/compression as a separate attribute, not 27 trading regimes.

The reference is exactly 1: <1 COMPRESSED, =1 NEUTRAL, >1 EXPANDED.
There is no tolerance band or outcome-derived threshold. Missing/zero-denominator
ratios remain unavailable; they do not suppress an otherwise valid core label.
Missing core inputs remain UNCLASSIFIED_WARMUP.

## Frozen core preservation

The pooled nearest-rank methodology is unchanged: exact probabilities 0.333333
and 0.666667; sorted[ceil(n*p)-1]. The development calibration is recomputed and
compared against G2. Threshold equality still belongs to the lower bucket at each
boundary. All thresholds and every individual core classification match G2 exactly.

- `volatility_low`: `0.70772125992621078662459452035253405481804084608722`
- `volatility_high`: `1.1983084785966187971510743249379515934834203015313`
- `efficiency_low`: `0.15451438336656223298205639418968954713756764454571`
- `efficiency_high`: `0.34332645184453819226281303294138766717529844717709`

Core counts (unchanged):

| State | Count |
| --- | ---: |
| UNCLASSIFIED_WARMUP | 3528 |
| NORMAL_VOL_MIXED | 1094 |
| NORMAL_VOL_DIRECTIONAL | 1051 |
| NORMAL_VOL_CHOPPY | 1188 |
| HIGH_VOL_DIRECTIONAL | 1280 |
| HIGH_VOL_MIXED | 1069 |
| HIGH_VOL_CHOPPY | 982 |
| LOW_VOL_CHOPPY | 1126 |
| LOW_VOL_MIXED | 1121 |
| LOW_VOL_DIRECTIONAL | 1085 |

## Corrected attribute distribution

Percentages use rows with a valid ratio in each group. JSON also includes percentages
of all rows. Unavailable rows are retained and never filled. Research sessions use
the existing labels at bar completion, exactly as in G2; these are not execution
permissions. Source months follow approved source-day identity.

| Group | Valid | Unavailable | COMPRESSED count / % | NEUTRAL count / % | EXPANDED count / % |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall | 9996 | 3528 | 6208 / 62.1048% | 0 / 0.0000% | 3788 / 37.8952% |
| 2024-02 | 3264 | 1152 | 2095 / 64.1850% | 0 / 0.0000% | 1169 / 35.8150% |
| 2024-03 | 3060 | 1080 | 1946 / 63.5948% | 0 / 0.0000% | 1114 / 36.4052% |
| 2024-04 | 3672 | 1296 | 2167 / 59.0142% | 0 / 0.0000% | 1505 / 40.9858% |
| ASIA | 1896 | 2808 | 1110 / 58.5443% | 0 / 0.0000% | 786 / 41.4557% |
| LONDON | 2891 | 49 | 1699 / 58.7686% | 0 / 0.0000% | 1192 / 41.2314% |
| LONDON_NEW_YORK_OVERLAP | 1764 | 0 | 554 / 31.4059% | 0 / 0.0000% | 1210 / 68.5941% |
| NEW_YORK | 2940 | 0 | 2397 / 81.5306% | 0 / 0.0000% | 543 / 18.4694% |
| OFF_SESSION | 505 | 671 | 448 / 88.7129% | 0 / 0.0000% | 57 / 11.2871% |

Expansion is now possible under the formula and observed in this development sample.
No particular balance of categories was required. Exact equality is evaluated without
any tolerance, and its observed frequency is reported without changing the reference.
The historical nested-range measure and its G2 findings remain preserved as v1.
This is a change in what the additional attribute measures, not a retrospective
reinterpretation of the old v1 labels.

## Provenance and checks

The scope remains 49 approved development days and 13,524 bars. All regenerated G1
feature hashes and source bar hashes match. The v2 calculation preserves every v1
row exactly. Both full generations/recharacterizations match, including content hashes;
five completed prefixes per day also match. The runner stops on unexpected changes
to core labels/counts or thresholds.

No May–July data or strategy outcomes were inspected. August–October remains locked.
No signals, profitability, P&L or markouts were examined. No threshold tuning,
strategies, database writes, migrations or dependencies were introduced.

Frozen config: `config/xauusd_market_state_taxonomy_v2.yaml`.
Reproduce with `PYTHONPATH=src .venv/bin/python scripts/report_xauusd_market_state_v2.py`
and DATABASE_URL supplied securely. JSON reports link exact G1/G2 report hashes,
engine/session hashes and per-dataset v1/v2 content identities. The development
identity links the existing G1 manifests and approved data; v2 reports and config
provide distinct feature/taxonomy identities.

## Limitations

Absolute price variability thresholds remain February–April development calibration,
not future stability guarantees or historical live-known thresholds. No May–July
compatibility check was needed. A zero denominator is explicitly unavailable; very
small positive denominators are not capped. Decimal divisions/square roots use the
existing fixed precision rather than claiming infinite precision. None of these
labels is a trading recommendation or a broker schedule.

Recommended commit: `fix: version market-state expansion ratio and taxonomy`

Taxonomy report hash: `5fa8c8f1f914d94cb592c3be122e1440934030e5264a1edd4d83e0035f71e86b`.
Feature report hash: `c1a4e095598233ce849a62107284ce1a97b69d656d92db1d65c8cfb6bc42e8ad`.

## Verification actually run

- Final `pytest -q`: **1027 passed**, one existing Starlette/AnyIO deprecation warning.
  Includes eight new offline cases and existing XAUUSD/NSE regressions.
- `ruff check .`: passed.
- `black --check .`: passed, 199 files unchanged.
- Strict `mypy`: passed, 100 source files.
- `alembic current`: **0008 (head)**; `alembic check`: no schema drift.
- Two complete report generations match; v1 hashes and G2 core labels match.
- Git status, working/staged diffs and whitespace checks reviewed. Eight new
  checkpoint files, no tracked modifications or staged changes. The two old
  untracked $3,000 sensitivity reports are untouched. No commit was made.

Stopped at G3. No strategy or profitability analysis was introduced.
