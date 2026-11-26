import pytest
from test_sr_compare import bars_with_day, breakout_path, only_prev_day

from trading_bot.backtesting import breakout as B
from trading_bot.backtesting import sr_compare as C
from trading_bot.backtesting.sr_strategy import Mids
from trading_bot.backtesting.sweep_strategy import build_days


def setup(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    bars = bars_with_day(breakout_path)
    days = build_days(bars)
    k = len(days) - 1
    monkeypatch.setattr(C, "type_levels", only_prev_day)
    mid = Mids.of(bars)
    s = next(
        x
        for x in C.find_signals(bars, days, k, mid, ("prev_day",))
        if x.kind == "breakout"
    )
    return bars, days, k, mid, s


def test_sixty_variants() -> None:
    assert len(B.VARIANTS) == 60
    assert len({v.name for v in B.VARIANTS}) == 60


def test_fixed_stop_is_adr_units_from_entry_and_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars, days, k, mid, s = setup(monkeypatch)
    stop = B.stop_for(s, mid, 0.4)
    assert stop == pytest.approx(mid.o[s.entry_minute] - 0.4 * s.adr)
    assert B.stop_for(s, mid, None) == s.stop
    assert B.stop_for(s, mid, 100.0) is None  # over the $30 cap


def test_no_cost_result_is_the_price_move_in_r(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars, days, k, mid, s = setup(monkeypatch)
    raw = B.mid_bars(bars)
    assert (raw["ask_open"] == raw["bid_open"]).all()
    v = B.Variant("prev_day", 0.25, 1.0)
    r = B.simulate(raw, mid, days[k], s, v, B.NO_COSTS)
    assert r is not None and r.trade.exit_reason == "target"
    assert B.r_of(r) == pytest.approx(1.0, rel=1e-4)
    from test_sr_compare import COSTS

    net = B.simulate(bars, mid, days[k], s, v, COSTS)
    assert net is not None and B.r_of(net) < B.r_of(r)
