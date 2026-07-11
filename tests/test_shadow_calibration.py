from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from shadow_calibration import append_shadow_signal, calibrate_groups, label_outcome


def _signal(**overrides):
    data = {
        "signal_id": "BTC-15m-1", "symbol": "BTCUSDT", "timeframe": "15m",
        "ts": 1, "side": "long", "entry": 100.0, "stop": 98.0, "target": 104.0,
        "model_id": "fvg_pullback", "regime": "trend", "grade": "A",
        "fvg_quality": 82.0, "ob_quality": 60.0, "haldro_valid_code": 2,
    }
    data.update(overrides)
    return data


def test_label_outcome_records_mfe_mae_and_first_barrier_for_each_horizon():
    bars = [
        {"high": 101.0, "low": 99.0},
        {"high": 103.0, "low": 99.5},
        {"high": 104.5, "low": 100.0},
        {"high": 105.0, "low": 99.0},
    ]
    out = label_outcome(_signal(), bars, horizons=(2, 4))
    assert out["h2"]["mfe_r"] == 1.5
    assert out["h2"]["mae_r"] == 0.5
    assert out["h2"]["first_hit"] == "none"
    assert out["h4"]["first_hit"] == "target"
    assert out["h4"]["bars_to_hit"] == 3


def test_short_outcome_uses_inverse_price_direction():
    bars = [{"high": 100.5, "low": 98.0}, {"high": 101.0, "low": 95.0}]
    signal = _signal(side="short", stop=102.0, target=96.0)
    out = label_outcome(signal, bars, horizons=(2,))
    assert out["h2"]["mfe_r"] == 2.5
    assert out["h2"]["mae_r"] == 0.5
    assert out["h2"]["first_hit"] == "target"


def test_append_shadow_signal_is_idempotent(tmp_path):
    path = tmp_path / "signals.jsonl"
    assert append_shadow_signal(path, _signal()) is True
    assert append_shadow_signal(path, _signal()) is False
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1


def test_append_shadow_signal_upgrades_same_bucket_when_live_authority_improves(tmp_path):
    path = tmp_path / "signals.jsonl"
    stale = _signal(haldro_valid_code=0) | {"dual": {"valid_code": 0}}
    fresh = _signal(haldro_valid_code=2) | {"dual": {"valid_code": 2}, "main": {"model_id": "fvg_pullback"}}
    assert append_shadow_signal(path, stale) is True
    assert append_shadow_signal(path, fresh) is True
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["dual"]["valid_code"] == 2
    assert "main" in rows[0]


def test_calibration_accepts_nested_regime_contract():
    rows = [
        _signal(signal_id=str(i), regime={"code": "trend"})
        | {"outcome": {"h16": {"first_hit": "target"}}}
        for i in range(30)
    ]
    stats = calibrate_groups(rows, horizon=16, min_samples=30)
    assert stats["trend|fvg_pullback"]["samples"] == 30
    assert stats["trend|fvg_pullback"]["calibrated_win_rate"] == 1.0


def test_calibration_never_emits_probability_below_min_samples():
    rows = []
    for i in range(29):
        rows.append(_signal(signal_id=str(i)) | {"outcome": {"h16": {"first_hit": "target"}}})
    stats = calibrate_groups(rows, horizon=16, min_samples=30)
    bucket = stats["trend|fvg_pullback"]
    assert bucket["samples"] == 29
    assert bucket["calibrated_win_rate"] is None
    rows.append(_signal(signal_id="29") | {"outcome": {"h16": {"first_hit": "stop"}}})
    stats = calibrate_groups(rows, horizon=16, min_samples=30)
    assert stats["trend|fvg_pullback"]["calibrated_win_rate"] == 29 / 30
