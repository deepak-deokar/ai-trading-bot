from datetime import date
from pathlib import Path

import pytest

from trading_bot.data.macro_daily import SYMBOLS, MacroHistory, load


def history() -> MacroHistory:
    days = [date(2024, 1, d) for d in (2, 3, 4, 5, 8)]
    values: dict[str, list[float | None]] = {
        n: [1.0, 2.0, None, 4.0, 5.0] for n in SYMBOLS
    }
    return MacroHistory(days, values)


def test_closes_before_never_includes_the_same_day() -> None:
    h = history()
    assert h.closes_before(date(2024, 1, 5), "usd", 3) == [1.0, 2.0]  # 4th missing
    assert h.closes_before(date(2024, 1, 8), "usd", 2) == [2.0, 4.0]
    assert h.closes_before(date(2024, 1, 2), "usd", 2) == []


def test_load_refuses_data_after_2024(tmp_path: Path) -> None:
    p = tmp_path / "m.csv"
    header = "date," + ",".join(SYMBOLS)
    p.write_text(f"{header}\n2025-01-02," + ",".join(["1"] * len(SYMBOLS)) + "\n")
    with pytest.raises(ValueError):
        load(p)
    p.write_text(f"{header}\n2024-12-31," + ",".join(["1"] * len(SYMBOLS)) + "\n")
    assert load(p).values["usd"] == [1.0]
