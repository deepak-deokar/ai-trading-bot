# XAUUSD level breakouts: raw edge first, then costs

Rules fixed before running: [docs/xauusd-breakout-plan.md](xauusd-breakout-plan.md). Development years 2014-2022, every setup on its own.

## Step 1: no costs (fills at the mid price)

All numbers are **R per trade** (1R = the stop distance). **Raw** = average result with no costs. **Twin** = the same trade at the same clock time on a random other day (200 runs). **Excess** = raw - twin, the level's own edge. **Cost** = what Equiti cautious costs take per trade on the same setups. To pass, excess must be at least 2x cost in both periods.

| Variant | Trades | Stop $ 14-20 / 21-22 | Raw 14-20 | Excess 14-20 | Cost 14-20 | Raw 21-22 | Excess 21-22 | Cost 21-22 | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| prev_day / stop level / target close | 1470 | $5 / $7 | +0.081 | +0.064 | 0.148 | +0.062 | +0.044 | 0.099 | no |
| swing / stop level / target 2.0R | 4398 | $5 / $6 | +0.038 | +0.040 | 0.132 | +0.058 | +0.051 | 0.098 | no |
| prev_day+swing / stop level / target 2.0R | 5156 | $5 / $6 | +0.044 | +0.044 | 0.140 | +0.050 | +0.040 | 0.095 | no |
| prev_day / stop level / target 2.0R | 1470 | $5 / $7 | +0.070 | +0.073 | 0.162 | +0.018 | +0.007 | 0.082 | no |
| prev_day+swing / stop level / target 1.5R | 5156 | $5 / $6 | +0.034 | +0.036 | 0.136 | +0.042 | +0.038 | 0.083 | no |
| prev_day / stop level / target 1.5R | 1470 | $5 / $7 | +0.065 | +0.066 | 0.140 | +0.009 | +0.007 | 0.092 | no |
| swing / stop 0.25ADR / target 2.0R | 4498 | $4 / $6 | +0.059 | +0.062 | 0.150 | +0.024 | +0.011 | 0.089 | no |
| swing / stop level / target 1.5R | 4398 | $5 / $6 | +0.033 | +0.033 | 0.137 | +0.048 | +0.039 | 0.080 | no |
| swing / stop 0.25ADR / target 1.5R | 4498 | $4 / $6 | +0.059 | +0.062 | 0.153 | +0.016 | +0.004 | 0.088 | no |
| prev_day+swing / stop 0.25ADR / target 1.5R | 5269 | $4 / $6 | +0.060 | +0.064 | 0.151 | +0.001 | -0.005 | 0.089 | no |
| swing / stop level / target close | 4398 | $5 / $6 | +0.050 | +0.029 | 0.143 | +0.051 | +0.029 | 0.089 | no |
| prev_day+swing / stop level / target close | 5156 | $5 / $6 | +0.050 | +0.032 | 0.142 | +0.053 | +0.026 | 0.093 | no |
| swing / stop 0.25ADR / target close | 4498 | $4 / $6 | +0.068 | +0.054 | 0.153 | +0.026 | -0.002 | 0.092 | no |
| prev_day+swing / stop 0.25ADR / target 2.0R | 5269 | $4 / $6 | +0.056 | +0.058 | 0.150 | +0.005 | -0.008 | 0.087 | no |
| prev_day+swing / stop 0.25ADR / target close | 5269 | $4 / $6 | +0.066 | +0.049 | 0.150 | +0.021 | -0.006 | 0.093 | no |
| prev_day / stop 0.4ADR / target close | 1500 | $7 / $10 | +0.023 | +0.014 | 0.094 | +0.027 | +0.023 | 0.060 | no |
| swing / stop level / target 1.0R | 4398 | $5 / $6 | +0.038 | +0.041 | 0.139 | -0.003 | -0.004 | 0.080 | no |
| prev_day / stop 0.25ADR / target close | 1500 | $4 / $6 | +0.085 | +0.070 | 0.143 | -0.015 | -0.033 | 0.089 | no |
| prev_day / stop level / target 1.0R | 1470 | $5 / $7 | +0.092 | +0.097 | 0.150 | -0.062 | -0.062 | 0.079 | no |
| prev_day+swing / stop level / target 1.0R | 5156 | $5 / $6 | +0.042 | +0.044 | 0.137 | -0.011 | -0.010 | 0.081 | no |
| prev_day / stop 0.25ADR / target 1.5R | 1500 | $4 / $6 | +0.075 | +0.080 | 0.149 | -0.045 | -0.049 | 0.090 | no |
| prev_day / stop 0.4ADR / target 1.5R | 1500 | $7 / $10 | +0.010 | +0.010 | 0.096 | +0.023 | +0.020 | 0.062 | no |
| prev_day / stop 0.4ADR / target 2.0R | 1500 | $7 / $10 | +0.006 | +0.005 | 0.087 | +0.028 | +0.024 | 0.060 | no |
| prev_day / stop 0.25ADR / target 2.0R | 1500 | $4 / $6 | +0.073 | +0.078 | 0.144 | -0.043 | -0.051 | 0.074 | no |
| swing / stop 0.25ADR / target 1.0R | 4498 | $4 / $6 | +0.050 | +0.053 | 0.146 | -0.033 | -0.029 | 0.077 | no |
| swing / stop 0.8ADR / target 2.0R | 4382 | $13 / $19 | +0.016 | +0.017 | 0.048 | +0.006 | +0.007 | 0.030 | no |
| prev_day+swing / stop 0.4ADR / target close | 5269 | $7 / $10 | +0.024 | +0.015 | 0.093 | +0.017 | +0.009 | 0.057 | no |
| prev_day / stop 0.25ADR / target 1.0R | 1500 | $4 / $6 | +0.095 | +0.097 | 0.151 | -0.084 | -0.074 | 0.086 | no |
| prev_day+swing / stop 0.4ADR / target 1.5R | 5269 | $7 / $10 | +0.013 | +0.013 | 0.089 | +0.012 | +0.009 | 0.054 | no |
| swing / stop 0.4ADR / target 2.0R | 4498 | $7 / $10 | +0.030 | +0.028 | 0.092 | -0.008 | -0.007 | 0.055 | no |
| swing / stop 0.4ADR / target close | 4498 | $7 / $10 | +0.027 | +0.018 | 0.092 | +0.011 | +0.003 | 0.056 | no |
| prev_day+swing / stop 0.25ADR / target 1.0R | 5269 | $4 / $6 | +0.053 | +0.057 | 0.145 | -0.039 | -0.037 | 0.081 | no |
| prev_day / stop 0.4ADR / target 1.0R | 1500 | $7 / $10 | +0.013 | +0.016 | 0.098 | -0.004 | +0.003 | 0.048 | no |
| swing / stop 0.6ADR / target 2.0R | 4456 | $10 / $15 | +0.026 | +0.022 | 0.065 | -0.006 | -0.004 | 0.038 | no |
| prev_day+swing / stop 0.4ADR / target 2.0R | 5269 | $7 / $10 | +0.021 | +0.019 | 0.091 | +0.002 | -0.001 | 0.055 | no |
| swing / stop 0.8ADR / target 1.5R | 4382 | $13 / $19 | +0.017 | +0.016 | 0.049 | -0.001 | +0.001 | 0.029 | no |
| prev_day+swing / stop 0.6ADR / target close | 5222 | $10 / $15 | +0.019 | +0.014 | 0.063 | +0.003 | +0.003 | 0.039 | no |
| swing / stop 0.8ADR / target close | 4382 | $13 / $19 | +0.015 | +0.014 | 0.048 | +0.004 | +0.003 | 0.030 | no |
| swing / stop 0.4ADR / target 1.5R | 4498 | $7 / $10 | +0.019 | +0.019 | 0.088 | +0.007 | -0.003 | 0.051 | no |
| prev_day+swing / stop 0.6ADR / target 2.0R | 5222 | $10 / $15 | +0.019 | +0.014 | 0.064 | -0.002 | +0.002 | 0.038 | no |
| swing / stop 0.4ADR / target 1.0R | 4498 | $7 / $10 | +0.019 | +0.020 | 0.094 | -0.004 | -0.004 | 0.050 | no |
| swing / stop 0.6ADR / target 1.5R | 4456 | $10 / $15 | +0.029 | +0.028 | 0.064 | -0.014 | -0.013 | 0.037 | no |
| swing / stop 0.6ADR / target close | 4456 | $10 / $15 | +0.024 | +0.020 | 0.064 | -0.000 | -0.006 | 0.040 | no |
| prev_day+swing / stop 0.4ADR / target 1.0R | 5269 | $7 / $10 | +0.018 | +0.021 | 0.096 | -0.007 | -0.007 | 0.050 | no |
| swing / stop 0.8ADR / target 1.0R | 4382 | $13 / $19 | +0.018 | +0.019 | 0.050 | -0.007 | -0.006 | 0.030 | no |
| swing / stop 0.6ADR / target 1.0R | 4456 | $10 / $15 | +0.019 | +0.019 | 0.061 | -0.004 | -0.005 | 0.037 | no |
| prev_day+swing / stop 0.6ADR / target 1.5R | 5222 | $10 / $15 | +0.020 | +0.019 | 0.063 | -0.007 | -0.005 | 0.038 | no |
| prev_day+swing / stop 0.8ADR / target 1.5R | 5140 | $13 / $19 | +0.012 | +0.012 | 0.049 | -0.002 | +0.000 | 0.028 | no |
| prev_day+swing / stop 0.6ADR / target 1.0R | 5222 | $10 / $15 | +0.012 | +0.013 | 0.061 | -0.001 | -0.001 | 0.037 | no |
| prev_day+swing / stop 0.8ADR / target 2.0R | 5140 | $13 / $19 | +0.013 | +0.012 | 0.048 | +0.005 | -0.000 | 0.030 | no |
| prev_day+swing / stop 0.8ADR / target 1.0R | 5140 | $13 / $19 | +0.012 | +0.014 | 0.049 | -0.006 | -0.004 | 0.030 | no |
| prev_day / stop 0.8ADR / target 1.0R | 1461 | $13 / $19 | +0.004 | +0.009 | 0.047 | +0.002 | +0.002 | 0.030 | no |
| prev_day+swing / stop 0.8ADR / target close | 5140 | $13 / $19 | +0.013 | +0.012 | 0.048 | +0.002 | -0.002 | 0.030 | no |
| prev_day / stop 0.8ADR / target close | 1461 | $13 / $19 | +0.012 | +0.010 | 0.049 | +0.003 | +0.000 | 0.029 | no |
| prev_day / stop 0.6ADR / target 1.0R | 1485 | $10 / $15 | +0.008 | +0.010 | 0.064 | -0.005 | -0.003 | 0.038 | no |
| prev_day / stop 0.8ADR / target 2.0R | 1461 | $13 / $19 | +0.010 | +0.008 | 0.049 | +0.004 | -0.002 | 0.031 | no |
| prev_day / stop 0.6ADR / target close | 1485 | $10 / $15 | +0.015 | +0.009 | 0.063 | -0.001 | -0.004 | 0.037 | no |
| prev_day / stop 0.6ADR / target 1.5R | 1485 | $10 / $15 | +0.009 | +0.004 | 0.063 | -0.001 | -0.001 | 0.037 | no |
| prev_day / stop 0.6ADR / target 2.0R | 1485 | $10 / $15 | +0.011 | +0.004 | 0.064 | -0.005 | -0.002 | 0.036 | no |
| prev_day / stop 0.8ADR / target 1.5R | 1461 | $13 / $19 | +0.008 | +0.006 | 0.050 | -0.001 | -0.003 | 0.028 | no |

## Step 2: costs back in

Nothing passed step 1, so step 2 did not run.

## Step 3: 2023-2024

Nothing passed step 2, so 2023-2024 was not looked at.
