# Asia buy: what-if broker costs (2014-2022 only)

Sensitivity, not a new test: the Asia variants from `docs/xauusd-asia-drift.md` (stop 0.75 ADR) rerun with a fixed spread around the mid price, $7/lot round-trip commission (Equiti Premier, IC Markets Raw, Pepperstone Razor published) and $0.05 slippage per fill. 2023-2026 not loaded. Output of `scripts/study_xauusd_asia_costs.py`:

```
recorded spread by NY hour, 2021-22:
  18:00  median 0.42  90th 0.59
  19:00  median 0.39  90th 0.48
  20:00  median 0.39  90th 0.46
  21:00  median 0.38  90th 0.46
  22:00  median 0.38  90th 0.45
  23:00  median 0.37  90th 0.44
  00:00  median 0.37  90th 0.44
  01:00  median 0.38  90th 0.45
  02:00  median 0.37  90th 0.45
  03:00  median 0.35  90th 0.43
  08:00  median 0.35  90th 0.43
  10:00  median 0.34  90th 0.42
  14:00  median 0.35  90th 0.42

$ per trade (stop 0.75 ADR), commission $7/lot, slippage $0.05/fill, fixed spread:
variant | spread | 2014-20 $/trade win | 2021-22 $/trade | 2014-22 net
fall_20d 18-02 | none | +1.26 58% | +0.19 | +761
fall_20d 19-02 | none | +1.03 57% | +0.57 | +698
below_50d 19-02 | none | +1.01 57% | +0.51 | +988
fall_20d 20-02 | none | +0.74 55% | +0.95 | +603
none 19-02 | none | +0.49 52% | +0.23 | +949
fall_20d 18-02 | $0.10 | +0.65 56% | -0.09 | +354
fall_20d 19-02 | $0.10 | +0.39 54% | +0.29 | +280
below_50d 19-02 | $0.10 | +0.37 54% | +0.21 | +372
fall_20d 20-02 | $0.10 | +0.09 52% | +0.67 | +180
none 19-02 | $0.10 | -0.10 48% | -0.08 | -209
fall_20d 18-02 | $0.15 | +0.53 56% | -0.15 | +277
fall_20d 19-02 | $0.15 | +0.28 54% | +0.24 | +205
below_50d 19-02 | $0.15 | +0.26 53% | +0.15 | +263
fall_20d 20-02 | $0.15 | -0.02 51% | +0.62 | +106
none 19-02 | $0.15 | -0.20 48% | -0.14 | -417
fall_20d 18-02 | $0.20 | +0.42 55% | -0.20 | +203
fall_20d 19-02 | $0.20 | +0.17 54% | +0.19 | +131
below_50d 19-02 | $0.20 | +0.15 53% | +0.10 | +154
fall_20d 20-02 | $0.20 | -0.13 50% | +0.57 | +31
none 19-02 | $0.20 | -0.31 48% | -0.19 | -625
fall_20d 18-02 | $0.25 | +0.31 55% | -0.27 | +125
fall_20d 19-02 | $0.25 | +0.05 53% | +0.14 | +53
below_50d 19-02 | $0.25 | +0.03 52% | +0.04 | +40
fall_20d 20-02 | $0.25 | -0.30 50% | +0.51 | -75
none 19-02 | $0.25 | -0.42 47% | -0.25 | -837
fall_20d 18-02 | $0.35 | +0.09 53% | -0.37 | -23
fall_20d 19-02 | $0.35 | -0.18 51% | +0.04 | -95
below_50d 19-02 | $0.35 | -0.19 51% | -0.07 | -178
fall_20d 20-02 | $0.35 | -0.53 49% | +0.41 | -224
none 19-02 | $0.35 | -0.64 46% | -0.36 | -1278
```
