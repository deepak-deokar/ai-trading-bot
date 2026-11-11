# XAUUSD G2C4C5 — frozen performance attribution

Analysis only. No backtest, alternative parameter run, source change, data write,
or optimization. Primary: corrected $3,000 run; secondary: corrected $500 run.
Saved trade records were reconciled with their frozen metrics. Original persisted
feature rows were read in PostgreSQL read-only transactions, matched to frozen
per-day content hashes, and their signal decision hashes matched to saved trades.
The old aborted $3,000 run was not used. Monetary sums use Decimal; ratios use
50-digit Decimal precision. Tables round display to four decimals; JSON retains
calculated precision. Source report SHA-256 hashes are recorded and unchanged.

## Verified totals and transaction costs

The $3,000 run has 309 trades, 101 wins and 208 losses; ending balance $1,911.28,
maximum realized drawdown $1,260.1025, profit factor 0.687468 and payoff 1.415777.
Before commission −$702.47; commission $386.25; after commission −$1,088.72.
It loses before costs; fees worsen an existing loss. This is not a profitable
pre-cost system destroyed solely by fees. Average commission is exactly $1.25.
Fees equal 15.2924% of positive pre-commission trade P&L, 16.1285% of the saved
gross-profit metric (positive net trade P&L), and 35.4774% of total net loss.
Commission changes seven pre-cost winners into net losers. Pre-cost win rate is
34.9515% (108/309), below its descriptive break-even rate of 40.7145%.
After-cost win rate 32.6861% is below break-even 41.3946% = 1/(1+1.4157766).
These are arithmetic identities of this sample, not proposed thresholds.

The $500 run remains 44 trades, 9 wins, 35 losses, pre-cost −$26.655, fees $55,
net −$81.655 and ending balance $418.345. Both experiments remain unchanged.

## Research R-multiples

R = executed net P&L / saved planned **risk budget**, not projected deployed stop
loss. Gross R uses before-commission P&L divided by that same budget. No exact
−1R stop or +2R target is assumed. Volume floors/caps, fixed fees, boundary exits
and grid alignment matter. Net mean −0.141607R; median −0.583967R; winning mean
+1.048521R; losing mean −0.719505R; extrema −0.998241R and +1.846149R.

Pre-commission R summary

| Group | mean | median | winning_mean | losing_mean | min | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gross_R | -0.0865 | -0.5287 | 1.0351 | -0.6892 | -0.9505 | 1.8952 |

Net R distribution (left-inclusive, right-exclusive; empty outer buckets omitted)

| Group | trades | net | mean_R |
| --- | ---: | ---: | ---: |
| [-0.5,0) | 39 | -224.2600 | -0.2390 |
| [-1,-0.5) | 169 | -3259.2925 | -0.8304 |
| [0,0.5) | 25 | 150.4400 | 0.2668 |
| [0.5,1) | 20 | 339.8025 | 0.7350 |
| [1,1.5) | 23 | 634.3450 | 1.2879 |
| [1.5,2) | 33 | 1270.2450 | 1.6639 |

No observations below −1R or at/above +2R. There are no breakeven trades.

## Exit-type attribution

| Group | trades | wins | losses | net | pre_commission | expectancy | mean_R | median_R | average_holding_minutes | signed_pct_total_loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CLOSED_END_OF_RESEARCH_DAY | 91 | 44 | 47 | 113.4100 | 227.1600 | 1.2463 | 0.0702 | -0.0097 | 238.1319 | -10.4168 |
| CLOSED_STOP | 160 | 0 | 160 | -3100.7175 | -2900.7175 | -19.3795 | -0.8391 | -0.8637 | 99.5000 | 284.8039 |
| CLOSED_STOP_AMBIGUOUS | 1 | 0 | 1 | -22.1900 | -20.9400 | -22.1900 | -0.9161 | -0.9161 | 10 | 2.0382 |
| CLOSED_TARGET | 57 | 57 | 0 | 1920.7775 | 1992.0275 | 33.6979 | 1.4915 | 1.5388 | 137.1053 | -176.4253 |

`expectancy` is average net P&L. Positive signed loss shares add to the loss;
negative shares offset it. Categories reconcile to 100%. Ordinary stops lose
−$3,100.7175 and ambiguous stop −$22.19; targets offset +$1,920.7775 and boundary
exits +$113.41. Boundary exits are net positive in aggregate, not the main loss
source. Their 44 winners are part of the reduced average-winner payoff; their
47 losers also contribute. This does not establish a counterfactual for removing
boundary closures, which remain unchanged.

## LONG versus SHORT

| Group | trades | wins | losses | win_rate_pct | net | pre_commission | average_win | average_loss | payoff | profit_factor | expectancy | mean_R | exits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LONG | 159 | 57 | 102 | 35.8491 | -336.7900 | -138.0400 | 23.7550 | 16.5767 | 1.4330 | 0.8008 | -2.1182 | -0.0819 | CLOSED_END_OF_RESEARCH_DAY: 52; CLOSED_STOP: 76; CLOSED_TARGET: 31 |
| SHORT | 150 | 44 | 106 | 29.3333 | -751.9300 | -564.4300 | 23.6545 | 16.9125 | 1.3986 | 0.5806 | -5.0129 | -0.2049 | CLOSED_TARGET: 26; CLOSED_STOP: 84; CLOSED_END_OF_RESEARCH_DAY: 39; CLOSED_STOP_AMBIGUOUS: 1 |

## Monthly attribution

| Group | trades | wins | losses | net | pre_commission | mean_R | profit_factor | exits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-02 | 86 | 26 | 60 | -373.9675 | -266.4675 | -0.1504 | 0.6723 | CLOSED_TARGET: 14; CLOSED_STOP: 40; CLOSED_END_OF_RESEARCH_DAY: 32 |
| 2024-03 | 99 | 26 | 73 | -593.6900 | -469.9400 | -0.2551 | 0.5032 | CLOSED_STOP: 54; CLOSED_TARGET: 14; CLOSED_END_OF_RESEARCH_DAY: 30; CLOSED_STOP_AMBIGUOUS: 1 |
| 2024-04 | 124 | 49 | 75 | -121.0625 | 33.9375 | -0.0449 | 0.8945 | CLOSED_STOP: 66; CLOSED_TARGET: 29; CLOSED_END_OF_RESEARCH_DAY: 29 |

Both directions lose before costs. SHORT contributes more negative net P&L.
All three months lose after fees; April is positive before fees (+$33.9375),
then loses $121.0625 after $155 commission. This is a sample description only.

## Holding duration

Duration = saved exit timestamp minus entry timestamp, using simulated completed
bar timestamps; it is not exact intrabar tick timing. Min 5, median 105, mean
146.9741, max 745 minutes. Buckets were fixed, not searched; all durations are
multiples of five, so (15,60] means 20–60 and (60,180] means 65–180 minutes.

Holding buckets

| Group | trades | net |
| --- | ---: | ---: |
| (15,60] | 70 | -570.7425 |
| (60,180] | 114 | -444.9400 |
| <=15 | 26 | -250.8600 |
| >180 | 99 | 177.8225 |

Holding duration is an outcome, not a pre-entry filter. Shorter realized holding
buckets lose while >180 minutes gains; no causal prescription follows.

## Signal-time research sessions

Existing config/xauusd_sessions.yaml: fixed UTC, first match wins. ASIA [00,08),
LONDON [08,13), overlap [13,16), NEW_YORK [16,21), OFF_SESSION [21,24).
Labels apply to saved completed signal timestamps, not broker permissions; no DST.

Session attribution

| Group | trades | win_rate_pct | net | mean_R |
| --- | ---: | ---: | ---: | ---: |
| ASIA | 136 | 31.6176 | -612.0075 | -0.1950 |
| LONDON | 71 | 25.3521 | -468.9225 | -0.2515 |
| LONDON_NEW_YORK_OVERLAP | 48 | 39.5833 | 5.6775 | 0.0058 |
| NEW_YORK | 50 | 36 | -25.7675 | -0.0056 |
| OFF_SESSION | 4 | 75 | 12.3000 | 0.1530 |

ASIA and LONDON account for most negative net P&L. Overlap and OFF_SESSION
are positive here, but OFF_SESSION has only four trades. No session filter is
proposed; categories are selected observations, not independent experiments.

## Original signal feature snapshots

Buckets were fixed before calculating their outcome tables. RSI: 5-point bands
from 30 through 70; absolute momentum_3: [0,1), [1,3), [3,6), >=6; absolute EMA
difference: [0,0.5), [0.5,1), [1,2), >=2; relative spread: [0,0.0001),
[0.0001,0.0002), [0.0002,0.0003), >=0.0003. Values at upper endpoints go to
the next band. Signed momentum/EMA are summarized by magnitude; LONG/SHORT
remain separately reported. RSI buckets are confounded with the original side
rules. Empty bins omitted. These are original signal-time values, not exit values.

rsi_14

| Group | trades | win_rate_pct | net | mean_R |
| --- | ---: | ---: | ---: | ---: |
| [30,35) | 34 | 29.4118 | -201.1750 | -0.2097 |
| [35,40) | 45 | 20 | -348.7475 | -0.3363 |
| [40,45) | 71 | 35.2113 | -202.0075 | -0.1193 |
| [55,60) | 62 | 32.2581 | -125.7750 | -0.1014 |
| [60,65) | 46 | 41.3043 | -44.4150 | -0.0203 |
| [65,70) | 51 | 35.2941 | -166.6000 | -0.1138 |

momentum_3

| Group | trades | win_rate_pct | net | mean_R |
| --- | ---: | ---: | ---: | ---: |
| >=6 | 1 | 0 | -0.2250 | -0.0097 |
| [0,1) | 114 | 29.8246 | -625.5825 | -0.2195 |
| [1,3) | 158 | 33.5443 | -406.6525 | -0.1031 |
| [3,6) | 36 | 38.8889 | -56.2600 | -0.0674 |

ema_difference

| Group | trades | win_rate_pct | net | mean_R |
| --- | ---: | ---: | ---: | ---: |
| >=2 | 28 | 42.8571 | -10.0150 | 0.0287 |
| [0,0.5) | 163 | 34.9693 | -390.8700 | -0.0932 |
| [0.5,1) | 65 | 23.0769 | -500.3000 | -0.3385 |
| [1,2) | 53 | 32.0755 | -187.5350 | -0.1390 |

relative_spread

| Group | trades | win_rate_pct | net | mean_R |
| --- | ---: | ---: | ---: | ---: |
| [0,0.0001) | 1 | 0 | -14.0750 | -0.5291 |
| [0.0001,0.0002) | 307 | 32.5733 | -1114.3200 | -0.1458 |
| [0.0002,0.0003) | 1 | 100 | 39.6750 | 1.5299 |

Every occupied RSI and momentum bucket loses net in this sample. EMA >=2 has
positive average R but negative dollar P&L: varying risk budgets make these
weightings different. 307/309 relative spreads occupy [0.0001,0.0002); the two
other bins have one trade each, providing no robust comparative evidence. No
best threshold, new feature, or optimized subset is inferred.

## Initial stop distance

Primary distance is |exact entry − submitted aligned stop| in quoted price units.
Raw structural distance is separately retained to distinguish alignment effects.

Distance summary

| Group | min | median | mean | max |
| --- | ---: | ---: | ---: | ---: |
| effective | 1.0520 | 4.1950 | 4.4934 | 10.0950 |
| raw structural | 1.0470 | 4.1900 | 4.4880 | 10.0900 |

Quartile cutoffs (nearest rank, ties assigned to lower bucket): 2.7920, 4.1950, 6.3950.
Computed from distances alone, without optimizing outcomes.

Stop quartiles

| Group | trades | mean_volume | volumes | win_rate_pct | mean_R | net |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q1 | 78 | 1.0192 | 1: 26; 1.5: 6; 2: 3; 0.75: 27; 1.25: 12; 1.75: 1; 0.5: 3 | 29.4872 | -0.2009 | -381.3625 |
| Q2 | 77 | 0.5390 | 0.75: 21; 0.5: 47; 0.25: 9 | 25.9740 | -0.2556 | -489.4775 |
| Q3 | 78 | 0.2917 | 0.5: 13; 0.25: 65 | 41.0256 | 0.0433 | 62.1250 |
| Q4 | 76 | 0.2500 | 0.25: 76 | 34.2105 | -0.1550 | -280.0050 |

## Volume and risk utilization

Planned risk includes stop-distance × 10 ounces/unit × volume plus $1.25 fee.
Saved selected volume was verified against the existing exact 0.25-step flooring
and maximum 2 rule for every executed trade. Average deployed/budget risk is
83.3820%. Mean unused budget is $3.803587: $3.766053 from step flooring and
$0.037534 from the volume cap, with three cap-constrained trades. These are
arithmetic sizing shortfalls, not missed profits or recommendations to raise risk.

Executed volume

| Group | trades | net | average_budget | average_planned_risk | mean_R |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.25 | 150 | -279.2375 | 21.3193 | 16.6518 | -0.0749 |
| 0.5 | 63 | -161.1850 | 23.4637 | 19.9981 | -0.1157 |
| 0.75 | 48 | -480.2025 | 25.4669 | 22.3433 | -0.3776 |
| 1 | 26 | -125.4400 | 25.4807 | 22.9700 | -0.2147 |
| 1.25 | 12 | 26.4375 | 26.0482 | 24.4771 | 0.0762 |
| 1.5 | 6 | -63.2400 | 26.8339 | 25.0275 | -0.3906 |
| 1.75 | 1 | -27.0625 | 27.3995 | 27.0625 | -0.9877 |
| 2 | 3 | 21.2100 | 27.5960 | 23.7300 | 0.2955 |

## Nominal 2R versus realized payoff

57/309 (18.4466%) reach target; 161/309 (52.1036%) stop, including one ambiguous
stop; 91/309 (29.4498%) exit at a research boundary. Target exits average
+1.491528 net budget-R, not +2R; ordinary stops average −0.839054R. The target
is 2× price distance, not 2× full risk budget after costs. Discrete utilization,
the fee reserved within sizing, target alignment, and exit mixture explain the
difference. All winners average +1.048521R and all losers −0.719505R. The 44
positive boundary exits average 0.4746R, diluting target-only winners.
The dollar payoff is $23.711213/$16.747849 = 1.415777, rather than 2. Dollar
payoff is not the ratio of mean R because balance, risk budgets and volumes vary.

## Consecutive outcomes and drawdowns

Maximum consecutive wins: 5; losses: 9. Drawdowns count distinct peak-to-recovery
episodes, including the final unrecovered episode, not every underwater trade or
repeated crossing. There are two episodes; exactly one exceeds each of 5%, 10%,
20%, and 30% (the same large unrecovered episode). Largest: $3,078.9675 peak at
2024-02-05 08:25 UTC to $1,818.865 trough at 2024-04-30 03:15 UTC (trade 302),
a $1,260.1025 / 40.926138% drawdown. It begins with trade 6 and remains
unrecovered at the end, despite recovering to $1,911.28. No risk limits inferred.

## Signal funnel

4,084 directional signals = 3,451 ignored while open + 633 attempted plans.
633 attempts = 30 boundary rejections + 294 minimum-volume rejections + 309
opened/closed trades. Exits = 57 target + 160 stop + 1 ambiguous stop + 91 boundary.
No grid or other rejections, unclosed trades or dropped signals.

## Corrected $500 comparison

Account comparison

| Group | trades | wins | losses | win_rate_pct | net | profit_factor | mean_R | median_R | mean_winning_R | mean_losing_R | min_R | max_R | exits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3000 | 309 | 101 | 208 | 32.6861 | -1088.7200 | 0.6875 | -0.1416 | -0.5840 | 1.0485 | -0.7195 | -0.9982 | 1.8461 | CLOSED_TARGET: 57; CLOSED_STOP: 160; CLOSED_END_OF_RESEARCH_DAY: 91; CLOSED_STOP_AMBIGUOUS: 1 |
| 500 | 44 | 9 | 35 | 20.4545 | -81.6550 | 0.2738 | -0.4022 | -0.6953 | 0.7785 | -0.7058 | -0.9978 | 1.0687 | CLOSED_END_OF_RESEARCH_DAY: 15; CLOSED_STOP: 22; CLOSED_TARGET: 7 |

$500 R distribution

| Group | trades | net | mean_R |
| --- | ---: | ---: | ---: |
| [-0.5,0) | 7 | -8.1500 | -0.2564 |
| [-1,-0.5) | 28 | -104.2975 | -0.8182 |
| [0,0.5) | 2 | 1.3725 | 0.1531 |
| [0.5,1) | 4 | 15.6325 | 0.8820 |
| [1,1.5) | 3 | 13.7875 | 1.0573 |

The $500 funnel: 4,084 = 175 ignored + 3,909 attempts; attempts = 30 boundary
rejections + 3,835 minimum-volume rejections + 44 trades. Only **3** signal
opportunities execute in both runs; 306 occur only in $3,000 and 41 only in $500.
This is not a controlled account-size comparison on identical trades. Eligibility
and open-position blocking select different populations. No matched-subset causal
effect is claimed. Full secondary attribution is retained in the JSON.

## Factual diagnosis and verification

1. Low hit rate: 32.6861% is below the observed-payoff break-even 41.3946%.
2. Stop losses exceed target and boundary gains; loss exists before fees.
3. Realized winner payoff is below nominal +2 budget-R because of sizing/cost
   conventions and the exit mixture; target ratio alone does not imply expectancy.
4. Commission adds $386.25 drag and flips seven small winners to losses.
5. SHORT and February/March contribute larger losses, descriptively. Boundary
   exits are net positive overall, so aggregate boundary-exit drag is unsupported.
6. Most budget is deployed but discrete volume flooring leaves unused risk; this
   does not establish that deploying more would improve results.

All grouping counts and P&L sums reconcile to the saved records, and frozen
counts, profit factor, payoff, balance, P&L and maximum drawdown were checked.
Feature snapshots match frozen per-day hashes and decision hashes. All six input
report hashes remain unchanged. No repository source code added; no full tests
needed for documentation-only work. Analysis assertions ran successfully. No
migration, strategy rerun, alternative parameter test, staging or commit. Git
status, working diff and staged diff inspected. Findings are observational,
overlapping, and drawn from a small retrospectively selected synthetic-contract
sample. No parameter, session, direction or month exclusion is recommended.
