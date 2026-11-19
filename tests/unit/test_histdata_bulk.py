import io
from datetime import UTC, datetime

from trading_bot.data.histdata_bulk import build_minute_bars, parse_epoch


def epoch(*args: int) -> int:
    return int(datetime(*args, tzinfo=UTC).timestamp())


def test_parse_epoch_uses_fixed_utc_minus_five_even_in_summer() -> None:
    assert parse_epoch("20240716 120000000") == epoch(2024, 7, 16, 17, 0)
    assert parse_epoch("20240116 235959999") == epoch(2024, 1, 17, 4, 59, 59)


def test_minute_bars_ohlc_and_spread() -> None:
    data = io.StringIO(
        "20240116 120000100,2000.10,2000.40,0\n"
        "20240116 120020000,2001.00,2001.20,0\n"
        "20240116 120040000,1999.50,2000.30,0\n"
        "20240116 120059999,2000.00,2000.25,0\n"
        "20240116 120100000,2000.05,2000.35,0\n"
    )
    bars, quality = build_minute_bars(data)
    assert list(bars["minute_utc"]) == [
        epoch(2024, 1, 16, 17, 0),
        epoch(2024, 1, 16, 17, 1),
    ]
    assert list(bars["tick_count"]) == [4, 1]
    assert bars["bid_open"][0] == 2000.10
    assert bars["bid_high"][0] == 2001.00
    assert bars["bid_low"][0] == 1999.50
    assert bars["bid_close"][0] == 2000.00
    assert bars["ask_high"][0] == 2001.20
    assert bars["ask_low"][0] == 2000.25
    assert abs(bars["spread_max"][0] - 0.80) < 1e-9
    assert quality.valid_ticks == 5


def test_bad_rows_are_counted_not_used() -> None:
    data = io.StringIO(
        "garbage\n"
        "20240116 120000100,2000.10,2000.00,0\n"  # crossed
        "20240116 120000200,0,2000.00,0\n"  # nonpositive
        "20240116 120000300,2000.10,2000.40,0\n"
        "20240116 115900000,2000.10,2000.40,0\n"  # out of order
    )
    bars, quality = build_minute_bars(data)
    assert (quality.malformed, quality.crossed, quality.nonpositive) == (1, 1, 1)
    assert quality.out_of_order == 1
    assert quality.valid_ticks == 1
    assert len(bars["minute_utc"]) == 1


def test_one_second_jitter_is_kept_in_current_bar() -> None:
    data = io.StringIO(
        "20240116 120010000,2000.10,2000.40,0\n"
        "20240116 120009000,1999.00,1999.30,0\n"  # 1s backwards: kept
        "20240116 120005000,2005.00,2005.30,0\n"  # 5s backwards: rejected
    )
    bars, quality = build_minute_bars(data)
    assert (quality.valid_ticks, quality.jitter_kept, quality.out_of_order) == (2, 1, 1)
    assert bars["bid_low"][0] == 1999.00
    assert bars["bid_high"][0] == 2000.10
