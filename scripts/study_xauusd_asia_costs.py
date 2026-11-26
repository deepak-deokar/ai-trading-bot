"""What-if costs for the Asia buy, 2014-2022 only (2023-24 untouched)."""

from datetime import datetime, time

import numpy as np
import study_xauusd_asia_drift as S
from study_xauusd_news_model import summary

from trading_bot.backtesting.news_day import NY, execute
from trading_bot.backtesting.session_window import CostModel, Sizing, load_bars
from trading_bot.backtesting.sweep_strategy import build_days
from trading_bot.data.histdata_bulk import BARS_DIR

bars = load_bars(BARS_DIR, 201401, 202212)
m = bars["minute_utc"]
sp = bars["ask_open"] - bars["bid_open"]
hrs = np.array([datetime.fromtimestamp(int(t), NY).hour for t in m[::15]])
yrs = np.array([datetime.fromtimestamp(int(t), NY).year for t in m[::15]])
s15 = sp[::15]
print("recorded spread by NY hour, 2021-22:")
for h in [17, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 8, 10, 14]:
    k = (hrs == h) & (yrs >= 2021)
    if k.any():
        print(
            f"  {h:02d}:00  median {np.median(s15[k]):.2f}  90th {np.quantile(s15[k], 0.9):.2f}"
        )
mid = {
    p: (bars[f"bid_{p}"] + bars[f"ask_{p}"]) / 2
    for p in ("open", "high", "low", "close")
}
tdays = build_days(bars)
closes = [d.close for d in tdays]
ranges = [d.high - d.low for d in tdays]
days = []
for k, d in enumerate(tdays):
    if k < 50:
        continue
    adr = float(np.mean(ranges[k - 20 : k]))
    prev = closes[k - 1]
    days.append(
        (
            d,
            adr,
            (prev - closes[k - 21]) / adr,
            prev < float(np.mean(closes[k - 50 : k])),
        )
    )
cut = float(np.quantile([c for d, a, c, b in days if d.day.year <= 2020], 1 / 3))
variants = [
    ("fall_20d", 18, 2),
    ("fall_20d", 19, 2),
    ("below_50d", 19, 2),
    ("fall_20d", 20, 2),
    ("none", 19, 2),
]
cm = CostModel(extra_spread_per_oz=0.0, commission_per_lot=7.0, slippage_per_oz=0.05)
print(
    "\n$ per trade (stop 0.75 ADR), commission $7/lot, slippage $0.05/fill, fixed spread:"
)
print("variant | spread | 2014-20 $/trade win | 2021-22 $/trade | 2014-22 net")
for spread in (0.0, 0.10, 0.15, 0.20, 0.25, 0.35):
    b = {"minute_utc": m}
    for p in ("open", "high", "low", "close"):
        b[f"bid_{p}"] = mid[p] - spread / 2
        b[f"ask_{p}"] = mid[p] + spread / 2
    c = cm if spread > 0 else CostModel(0.0, 0.0, 0.0)
    for f, h0, h1 in variants:
        tr = []
        for d, adr, chg, below in days:
            if f == "fall_20d" and chg > cut:
                continue
            if f == "below_50d" and not below:
                continue
            if 0.75 * adr > 30:
                continue
            i = int(np.searchsorted(m, S.ts(d.day, time(h0), True)))
            j = int(np.searchsorted(m, S.ts(d.day, time(h1), False)))
            if not (d.i0 <= i < j <= d.i1):
                continue
            t = execute(b, d.day, i, j - 1, 1, c, Sizing(), risk=0.75 * adr)
            if t:
                tr.append(t)
        e = summary([t for t in tr if t.day.year <= 2020])
        l = summary([t for t in tr if t.day.year > 2020])
        print(
            f"{f} {h0}-0{h1} | {'none' if spread == 0 else f'${spread:.2f}'} | {e['avg_per_trade']:+.2f} {e['win_rate']:.0%} | {l['avg_per_trade']:+.2f} | {e['net_usd'] + l['net_usd']:+.0f}"
        )
