import importlib.util
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from test_market_state_v2 import oscillating

from trading_bot.features.market_state_v2 import calculate_market_state_v2
from trading_bot.features.market_taxonomy import STATES, WARMUP, StateObservation
from trading_bot.features.research_repository import content_hash


def runner():
    spec = importlib.util.spec_from_file_location(
        "state_validation", Path("scripts/validate_xauusd_market_state.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_policy_exact_no_calibration(monkeypatch):
    import trading_bot.features.market_taxonomy as taxonomy

    def forbidden(*args, **kwargs):
        raise AssertionError("no quantile calibration allowed")

    monkeypatch.setattr(taxonomy, "quantile", forbidden)
    m = runner()
    p = m.load_frozen_taxonomy()
    assert p.model_dump(mode="json") == json.loads(m.G3.read_text())["policy"]
    rows = calculate_market_state_v2(oscillating(count=90))
    assert [p.classify(r) for r in rows] == [p.classify(r) for r in rows]
    assert p.volatility_low == Decimal(
        "0.70772125992621078662459452035253405481804084608722"
    )


def test_dataset_identity_and_tamper_rejected(tmp_path, monkeypatch):
    m = runner()
    assert content_hash(m.verified_manifest()) == m.IDENTITY
    raw = json.loads(m.SOURCE.read_text())
    raw["manifest"]["days"][0]["bar_count"] = 275
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(raw))
    monkeypatch.setattr(m, "SOURCE", path)
    with pytest.raises(ValueError, match="identity"):
        m.verified_manifest()


def test_config_tampering_rejected(tmp_path, monkeypatch):
    m = runner()
    p = tmp_path / "policy.yaml"
    p.write_text(
        m.CONFIG.read_text().replace(
            "0.70772125992621078662459452035253405481804084608722", "0.1"
        )
    )
    monkeypatch.setattr(m, "CONFIG", p)
    with pytest.raises(ValueError, match="taxonomy"):
        m.load_frozen_taxonomy()


def test_summary_warmup_continuity_and_identity():
    m = runner()
    now = datetime(2024, 5, 1, 5, tzinfo=UTC)
    states = [WARMUP, STATES[0], STATES[0], STATES[1], STATES[1]]
    records = [
        {
            "month": "2024-05",
            "session": "ASIA",
            "core": s,
            "attribute": None if s == WARMUP else "EXPANDED",
        }
        for s in states
    ]
    sequence = [
        StateObservation("synthetic", now + timedelta(minutes=5 * i), s, i in (0, 4))
        for i, s in enumerate(states)
    ]
    first = m.summarize(records, sequence)
    assert first["overall"]["classified"] == 4
    assert first["overall"]["unclassified"] == 1
    assert first["transitions"] == 2
    assert first["same_state_transitions"] == 1
    assert first["run_bar_count"] == 4
    assert content_hash(first) == content_hash(m.summarize(records, sequence))


def test_validation_feature_resets_and_causality():
    m = runner()
    p = m.load_frozen_taxonomy()
    source = oscillating(count=330, gap_at=45)
    rows = calculate_market_state_v2(source)
    assert rows[45].ratio_unavailable == "GAP_WARMUP"
    assert rows[81].volatility_ratio_12_36 is not None
    day = next(
        i for i, r in enumerate(rows) if r.baseline.sequence_reset == "SOURCE_DAY"
    )
    assert p.classify(rows[day])[0] == WARMUP
    prefix = source.model_copy(
        update={"inputs": source.inputs[:100], "as_of": source.inputs[99].available_at}
    )
    assert calculate_market_state_v2(prefix) == rows[:100]


def test_historical_artifacts_unchanged():
    import hashlib

    frozen = {
        "src/trading_bot/features/market_state_v2.py": (
            "68554227667e2d83158131f7046e68c5" "21fefe0c7ab7103aee2cfb418cdcc005"
        ),
        "src/trading_bot/features/market_state.py": (
            "36cdab649c6a88315551149a9142899f" "1884f1e18f33367672a0a2a8a069a4eb"
        ),
        "config/xauusd_market_state_taxonomy_v2.yaml": (
            "18ae6a473f92922c846e1b25ae7b259d" "14db9f644848807f527fc4698cc5b96e"
        ),
        "docs/xauusd-market-state-taxonomy-v2.json": (
            "ec27495e2f306e15d8fee519384b08af" "76ee9f5da26101ce1ba200db1745d115"
        ),
        "docs/xauusd-market-state-characterization.json": (
            "96c395cdfa7bd811c036f900dc30b183" "e46768610cf98eaa32cf82ec18cf46b4"
        ),
        "docs/xauusd-may-july-validation-dataset.json": (
            "8867442f67250a015d371479a128e6e2" "a10799efc5cc1684103de7eb05906ac7"
        ),
    }
    for path, expected in frozen.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
