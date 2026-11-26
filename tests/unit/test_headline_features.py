import numpy as np
import pytest

from trading_bot.backtesting import headline_features as H


def test_mood_uses_whole_words() -> None:
    assert H.mood(H.clean("Gold RISES as dollar slips")) == 0  # both
    assert H.mood(H.clean("Gold jumps to record high")) == 1
    assert H.mood(H.clean("Gold prices fell on Fed")) == -1
    assert H.mood(H.clean("Goldman upgrades miners")) == 0
    assert H.mood(H.clean("Gold set-up for the week")) == 0  # not "up"
    assert H.mood(H.clean("Gold &amp; silver: safe haven bid")) == 1


def test_only_articles_before_t_are_used() -> None:
    t = 1_000_000
    rows = [
        (t - 2 * H.DAY, "gold falls", -2.0, 0),  # in the week before
        (t - 5 * H.HOUR, "gold rises", 1.0, 1),  # 24 h only
        (t - 1 * H.HOUR, "gold jumps", 3.0, 0),  # 24 h and 3 h
        (t, "gold soars", 5.0, 0),  # at t: never used
    ]
    h = H.Headlines.of(rows)
    f = dict(zip(H.feature_names(), h.features_at(t), strict=True))
    assert f["hl24_count_log"] == pytest.approx(np.log1p(2))
    assert f["hl24_up_share"] == 1.0
    assert f["hl24_tone"] == pytest.approx(2.0)
    assert f["hl24_cb_log"] == pytest.approx(np.log1p(1))
    assert f["hl3_count_log"] == pytest.approx(np.log1p(1))
    assert f["hl3_tone"] == pytest.approx(3.0)
    assert f["hl24_count_vs_week"] == pytest.approx(np.log1p(2) - np.log1p(1 / 7))
    assert h.text_before(t) == "gold rises | gold jumps"
