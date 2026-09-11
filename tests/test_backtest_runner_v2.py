from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from backtest_runner_v2 import replay_shadow_records


def test_replay_never_upgrades_recorded_live_block():
    for fields in ({"final_state": "WAIT", "blockers": ["live_gate"]},
                   {"final_state": "NO-GO"}, {"execution_authorized": False}):
        record = _record() | fields
        result = replay_shadow_records([record], {})
        assert result["authorized"] == 0
        assert result["blocked"] == 1


def _record(conflict=False):
    return {
        "signal_id": "s1", "symbol": "BTCUSDT",
        "main": {"grade": "A多", "direction": "long", "model_id": "fvg_pullback",
                 "entry": 100, "stop": 98, "target": 104, "rr": 2,
                 "mcp_fvg_quality_score": 80, "data_grade": "A",
                 "snapshot_age_sec": 10, "location_valid": True,
                 "trigger_confirmed": True, "bar_closed": True},
        "dual": {"asset_is_crypto": True, "valid_code": 2, "aligned": True, "conflict": conflict},
        "regime": {"code": "trend", "name": "趋势",
                   "allowed_models": ["fvg_pullback"], "blocked_models": [],
                   "position_multiplier": 1.0, "exhausted": False, "reason": "趋势"},
        "risk": {"allowed": True, "risk_usd": 1.0, "violations": []},
        "advanced": {"gate": {"execute": True}},
    }


def test_backtest_v2_replays_same_final_verdict_and_blocks_conflict():
    result = replay_shadow_records([_record(conflict=True)], {"s1": [{"high": 105, "low": 99}]})
    assert result["executed"] == 0
    assert result["blocked"] == 1
    assert result["gate_stats"]["dual_indicator"] == 1


def test_backtest_v2_replays_flat_shadow_record_for_backward_compatibility():
    flat = {
        "signal_id": "flat1", "symbol": "BTCUSDT", "side": "neutral",
        "entry": 100, "stop": 98, "target": 104, "model_id": "vwap_pullback",
        "grade": "B等待", "regime": "unknown", "haldro_valid_code": 0,
        "haldro_risk_code": 0, "final_state": "WAIT",
    }
    result = replay_shadow_records([flat], {"flat1": []})
    assert result["total"] == 1
    assert result["blocked"] == 1
    assert result["executed"] == 0


def test_backtest_v2_labels_executed_trade_without_legacy_models():
    bars = [{"open": 100, "close": 100, "high": 101, "low": 99}, {"open": 100, "close": 104, "high": 104.5, "low": 100}]
    record = _record() | {"order_model": {"type": "limit"}}
    result = replay_shadow_records([record], {"s1": bars}, horizons=(2,))
    assert result["executed"] == 1
    assert result["trades"][0]["outcome"]["h2"]["first_hit"] == "target"
    assert result["trades"][0]["model_id"] == "fvg_pullback"


def test_authorization_is_not_fill_and_no_data_is_not_a_trade():
    for bars in ([], [{"open": 104, "high": 105, "low": 103, "close": 104}]):
        record = _record() | {"order_model": {"type": "limit"}}
        result = replay_shadow_records([record], {"s1": bars}, horizons=(1,))
        assert result["authorized"] == 1
        assert result["executed"] == 0
        assert result["total"] == 1
        assert len(result["orders"]) == 1
        assert result["trades"] == []


def test_missing_model_does_not_create_trade_or_oos_return():
    result = replay_shadow_records([_record()], {"s1": [{"open": 100, "high": 105, "low": 99, "close": 104}]}, horizons=(1,))
    assert result["authorized"] == 1
    assert result["executed"] == 0
    assert result["orders"][0]["outcome"]["h1"]["net_r"] is None
