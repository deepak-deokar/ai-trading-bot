"""Daily-zone liquidity-sweep strategy (from a YouTube gold intraday video).

Rules as described in the video, made exact (assumptions marked *):

1. Zones from the previous day's daily candle (mid prices). Supply = upper wick
   [max(open, close), high]; demand = lower wick [low, min(open, close)]. If that
   day is an inside bar of the day before, use the larger "mother" candle instead.
   *Trading day = 17:00 to 17:00 New York (the usual MT5 broker day).
2. Next day on 15-minute candles: sells only from supply, buys only from demand.
3. Sell setup: candle 2 trades above candle 1's high and closes back below it
   (a "liquidity sweep"), with candle 2's high reaching into the supply zone*.
   Entry when a later candle closes below the sweep candle's low; *the setup
   expires after 4 candles or if price goes above the sweep high first. Buys mirror.
4. Stop beyond the sweep candle's extreme; target 2R (video also shows 3R).
   Video: the stop only counts when a 15-minute candle CLOSES beyond it ("close");
   also tested with a normal stop order that fills on touch ("touch").
5. Several trades per day, one at a time; *no new entries after 16:00 New York
   and anything still open is closed at 16:45 New York (no overnight).

Optional variants (not in the video): ``trend_filter`` takes a sell only when the
confirmation candle closes below the 20-hour moving average of hourly closes (buys
above it); ``trail`` moves a touch stop to 1R behind the best price once the trade
is 1R in profit (exit reason "trail").

Entries fill at the next 15-minute candle's open (ask for buys, bid for sells)
plus the cost model's extra spread and slippage; targets fill on touch, checked
minute by minute; if one minute hits both stop and target the stop wins.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np

from trading_bot.backtesting.session_hold import HoldTrade
from trading_bot.backtesting.session_window import Array, CostModel, Sizing, lots_for

NY = ZoneInfo("America/New_York")
BAR_SECONDS = 15 * 60
SETUP_EXPIRY_BARS = 4
MIN_DAY_MINUTES = 600  # ignore holiday stubs as reference or trading days
LAST_ENTRY = time(16, 0)
FORCED_EXIT = time(16, 45)
MAX_MOTHER_LOOKBACK = 5


TREND_HOURS = 20  # trend filter: 20-period moving average of hourly mid closes


@dataclass(frozen=True)
class SweepRule:
    target_r: float
    stop_mode: Literal["close", "touch"]
    # only sell below / buy above the 20-hour average of hourly closes
    trend_filter: bool = False
    # once the trade is 1R in profit, trail a touch stop 1R behind the best price
    # (this also moves it to break-even or better)
    trail: bool = False

    @property
    def name(self) -> str:
        extra = ("+trend" if self.trend_filter else "") + (
            "+trail" if self.trail else ""
        )
        return f"{self.target_r:g}R/{self.stop_mode}-stop{extra}"


@dataclass(frozen=True)
class HourlyTrend:
    """20-hour moving average, known only once each hour has finished."""

    hour_last_minute: Array  # 1-minute index of the last minute of each hour
    average: Array  # average of the 20 hourly closes ending that hour (nan before)

    def at(self, minute: int) -> float:
        """Average from the hours fully completed before 1-minute index `minute`."""
        k = int(np.searchsorted(self.hour_last_minute, minute - 1, side="right")) - 1
        return float(self.average[k]) if k >= 0 else float("nan")


def hourly_trend(bars: dict[str, Array], hours: int = TREND_HOURS) -> HourlyTrend:
    m = bars["minute_utc"]
    hb = m // 3600
    last = np.flatnonzero(np.diff(hb, append=hb[-1] + 1))
    closes = (bars["bid_close"][last] + bars["ask_close"][last]) / 2
    avg = np.full(len(closes), np.nan)
    if len(closes) >= hours:
        c = np.cumsum(np.concatenate([[0.0], closes]))
        avg[hours - 1 :] = (c[hours:] - c[:-hours]) / hours
    return HourlyTrend(last, avg)


@dataclass(frozen=True)
class TradingDay:
    day: date
    i0: int  # 1-minute index range [i0, i1)
    i1: int
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Zones:
    supply_bottom: float
    supply_top: float
    demand_bottom: float
    demand_top: float


def ny_utc(day: date, at: time) -> int:
    return int(datetime.combine(day, at, tzinfo=NY).astimezone(UTC).timestamp())


def trading_day_ordinals(minute_utc: Array) -> Array:
    """Date ordinal of the 17:00-New-York trading day each minute belongs to."""
    first = datetime.fromtimestamp(int(minute_utc[0]), UTC).date() - timedelta(days=2)
    last = datetime.fromtimestamp(int(minute_utc[-1]), UTC).date() + timedelta(days=2)
    days = [first + timedelta(days=k) for k in range((last - first).days + 1)]
    # trading day D starts at 17:00 New York on D-1
    starts = np.array([ny_utc(d - timedelta(days=1), time(17, 0)) for d in days])
    idx = np.searchsorted(starts, minute_utc, side="right") - 1
    ordinals = np.array([d.toordinal() for d in days])
    return ordinals[idx]


def build_days(bars: dict[str, Array]) -> list[TradingDay]:
    minutes = bars["minute_utc"]
    if len(minutes) == 0:
        return []
    ords = trading_day_ordinals(minutes)
    mid_h = (bars["bid_high"] + bars["ask_high"]) / 2
    mid_l = (bars["bid_low"] + bars["ask_low"]) / 2
    mid_o = (bars["bid_open"] + bars["ask_open"]) / 2
    mid_c = (bars["bid_close"] + bars["ask_close"]) / 2
    cuts = np.flatnonzero(np.diff(ords)) + 1
    starts = np.concatenate([[0], cuts])
    ends = np.concatenate([cuts, [len(minutes)]])
    out = []
    for s, e in zip(starts, ends, strict=True):
        if e - s < MIN_DAY_MINUTES:
            continue
        out.append(
            TradingDay(
                date.fromordinal(int(ords[s])),
                int(s),
                int(e),
                float(mid_o[s]),
                float(mid_h[s:e].max()),
                float(mid_l[s:e].min()),
                float(mid_c[e - 1]),
            )
        )
    return out


def _inside(day: TradingDay, mother: TradingDay) -> bool:
    return day.high <= mother.high and day.low >= mother.low


def zones_for(days: Sequence[TradingDay], k: int) -> Zones | None:
    """Zones for trading day k from the previous day (or its mother candle)."""
    if k < 1:
        return None
    j = k - 1
    while j >= 1 and k - 1 - j < MAX_MOTHER_LOOKBACK and _inside(days[j], days[j - 1]):
        j -= 1
    ref = days[j]
    return Zones(
        supply_bottom=max(ref.open, ref.close),
        supply_top=ref.high,
        demand_bottom=ref.low,
        demand_top=min(ref.open, ref.close),
    )


@dataclass(frozen=True)
class Bars15:
    start: Array  # 1-minute index where each 15-minute candle starts
    end: Array  # exclusive
    open: Array
    high: Array
    low: Array
    close: Array


def to_15m(bars: dict[str, Array], i0: int, i1: int) -> Bars15:
    m = bars["minute_utc"][i0:i1]
    _, rel = np.unique(m // BAR_SECONDS, return_index=True)
    start = rel + i0
    end = np.concatenate([start[1:], [i1]])
    mh = (bars["bid_high"][i0:i1] + bars["ask_high"][i0:i1]) / 2
    ml = (bars["bid_low"][i0:i1] + bars["ask_low"][i0:i1]) / 2
    return Bars15(
        start=start,
        end=end,
        open=(bars["bid_open"][start] + bars["ask_open"][start]) / 2,
        high=np.maximum.reduceat(mh, rel),
        low=np.minimum.reduceat(ml, rel),
        close=(bars["bid_close"][end - 1] + bars["ask_close"][end - 1]) / 2,
    )


def _first(mask: Array) -> int:
    hits = np.flatnonzero(mask)
    return int(hits[0]) if len(hits) else -1


def _manage(
    bars: dict[str, Array],
    day: TradingDay,
    s: int,
    last: int,
    direction: int,
    stop: float,
    rule: SweepRule,
    costs: CostModel,
    sizing: Sizing,
) -> HoldTrade | None:
    """Open at minute s, manage minute by minute up to minute `last` inclusive."""
    pf = costs.per_fill
    if direction == 1:
        entry = float(bars["ask_open"][s]) + pf
        if stop >= float(bars["bid_open"][s]):
            return None
    else:
        entry = float(bars["bid_open"][s]) - pf
        if stop <= float(bars["ask_open"][s]):
            return None
    lots = lots_for(entry, stop, costs, sizing)
    if lots == 0.0:
        return None
    target = entry + direction * rule.target_r * abs(entry - stop)
    sl = slice(s, last + 1)
    if direction == 1:
        hit_target = _first(bars["bid_high"][sl] >= target)
        touch = _first(bars["bid_low"][sl] <= stop)
    else:
        hit_target = _first(bars["ask_low"][sl] <= target)
        touch = _first(bars["ask_high"][sl] >= stop)
    if rule.stop_mode == "touch":
        hit_stop = touch
    else:
        mids = (bars["bid_close"][sl] + bars["ask_close"][sl]) / 2
        bucket = bars["minute_utc"][sl] // BAR_SECONDS
        candle_end = np.concatenate([bucket[1:] != bucket[:-1], [True]])
        beyond = mids < stop if direction == 1 else mids > stop
        hit_stop = _first(beyond & candle_end)

    hit_trail, trail_levels = -1, None
    if rule.trail:
        risk = abs(entry - stop)
        if direction == 1:
            best = np.maximum.accumulate(bars["bid_high"][sl])
        else:
            best = np.minimum.accumulate(bars["ask_low"][sl])
        # the trail for minute i uses the best price up to minute i-1, so a minute
        # never both sets a new best and stops out on it (we can't see the order)
        prev_best = np.concatenate([[np.nan], best[:-1]])
        active = (prev_best - entry) * direction >= risk
        trail_levels = prev_best - direction * risk
        if direction == 1:
            crossed = bars["bid_low"][sl] <= trail_levels
        else:
            crossed = bars["ask_high"][sl] >= trail_levels
        hit_trail = _first(active & crossed)

    candidates = [
        (k, r)
        for k, r in ((hit_stop, "stop"), (hit_trail, "trail"), (hit_target, "target"))
        if k >= 0
    ]
    if candidates:
        k_rel, reason = min(candidates, key=lambda x: (x[0], x[1] == "target"))
    else:
        k_rel, reason = last - s, "time_exit"
    k = s + k_rel
    if reason == "trail" and trail_levels is not None:
        o = bars["bid_open"][k] if direction == 1 else bars["ask_open"][k]
        lvl = float(trail_levels[k_rel])
        level = min(lvl, o) if direction == 1 else max(lvl, o)
        exit_px = float(level) - direction * pf
        pnl = (exit_px - entry) * direction * costs.contract_size_oz * lots
        pnl -= costs.commission_per_lot * lots
        hold = int((bars["minute_utc"][k] - bars["minute_utc"][s]) // 60) + 1
        return HoldTrade(
            day.day,
            direction,
            s,
            entry,
            stop,
            exit_px,
            lots,
            pnl,
            "trail",
            hold,
            k,
            target,
        )
    if reason == "target":
        o = bars["bid_open"][k] if direction == 1 else bars["ask_open"][k]
        level = max(target, o) if direction == 1 else min(target, o)
    elif reason == "stop" and rule.stop_mode == "touch":
        o = bars["bid_open"][k] if direction == 1 else bars["ask_open"][k]
        level = min(stop, o) if direction == 1 else max(stop, o)
    else:  # candle-close stop or time exit: out at that minute's close
        level = bars["bid_close"][k] if direction == 1 else bars["ask_close"][k]
    exit_px = float(level) - direction * pf
    pnl = (exit_px - entry) * direction * costs.contract_size_oz * lots
    pnl -= costs.commission_per_lot * lots
    hold = int((bars["minute_utc"][k] - bars["minute_utc"][s]) // 60) + 1
    return HoldTrade(
        day.day, direction, s, entry, stop, exit_px, lots, pnl, reason, hold, k, target
    )


def simulate_day(
    bars: dict[str, Array],
    day: TradingDay,
    zones: Zones,
    rule: SweepRule,
    costs: CostModel,
    sizing: Sizing,
    trend: HourlyTrend | None = None,
) -> list[HoldTrade]:
    c = to_15m(bars, day.i0, day.i1)
    minutes = bars["minute_utc"]
    entry_cutoff = ny_utc(day.day, LAST_ENTRY)
    exit_at = ny_utc(day.day, FORCED_EXIT)
    last = int(np.searchsorted(minutes, exit_at) - 1)
    trades: list[HoldTrade] = []
    pending: dict[int, tuple[float, float, int]] = {}  # dir -> (extreme, other, expiry)
    q = 1
    n = len(c.start)
    while q < n:
        signal = None
        for d in (1, -1):
            if d not in pending:
                continue
            extreme, other, expiry = pending[d]
            if (d == -1 and c.high[q] > extreme) or (d == 1 and c.low[q] < extreme):
                del pending[d]
            elif (d == -1 and c.close[q] < other) or (d == 1 and c.close[q] > other):
                signal = (d, extreme)
                pending.clear()
                break
            elif q >= expiry:
                del pending[d]
        if signal is None:
            sell = (
                c.high[q] > c.high[q - 1]
                and c.close[q] < c.high[q - 1]
                and c.high[q] >= zones.supply_bottom
            )
            buy = (
                c.low[q] < c.low[q - 1]
                and c.close[q] > c.low[q - 1]
                and c.low[q] <= zones.demand_top
            )
            if sell and not buy:
                pending[-1] = (float(c.high[q]), float(c.low[q]), q + SETUP_EXPIRY_BARS)
            elif buy and not sell:
                pending[1] = (float(c.low[q]), float(c.high[q]), q + SETUP_EXPIRY_BARS)
            q += 1
            continue
        d, stop = signal
        if q + 1 >= n:
            break
        if rule.trend_filter:
            if trend is None:
                raise ValueError("trend_filter needs the hourly trend")
            avg = trend.at(int(c.end[q]))
            if not (c.close[q] - avg) * d > 0:  # nan (too early) also skips
                q += 1
                continue
        s = int(c.start[q + 1])
        if minutes[s] >= entry_cutoff or s > last:
            break
        trade = _manage(bars, day, s, last, d, stop, rule, costs, sizing)
        if trade is None:
            q += 1
            continue
        trades.append(trade)
        # resume scanning with the first candle that starts after the exit minute
        q = int(np.searchsorted(c.start, trade.exit_bar, side="right"))
        q = max(q, 1)
    return trades


def run_sweep(
    bars: dict[str, Array],
    days: Sequence[TradingDay],
    rule: SweepRule,
    costs: CostModel,
    sizing: Sizing,
    years: range,
) -> tuple[list[HoldTrade], int]:
    """All trades on trading days whose year is in `years`, plus days evaluated."""
    trades: list[HoldTrade] = []
    evaluated = 0
    trend = hourly_trend(bars) if rule.trend_filter else None
    for k, day in enumerate(days):
        if day.day.year not in years:
            continue
        zones = zones_for(days, k)
        if zones is None:
            continue
        evaluated += 1
        trades.extend(simulate_day(bars, day, zones, rule, costs, sizing, trend))
    return trades, evaluated
