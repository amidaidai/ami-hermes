from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from backtest_runner_v2 import replay_shadow_records


def _record(conflict=False):
    return {
        "signal_id": "s1", "symbol": "BTCUSDT",
        "main": {"grade": "A多", "direction": "long", "model_id": "fvg_pullback",
                 "entry": 100, "stop": 98, "target": 104, "rr": 2,
                 "mcp_fvg_quality_score": 80},
        "dual": {"asset_is_crypto": True, "valid_code": 2, "conflict": conflict},
        "regime": {"code": "trend", "name": "趋势",
                   "allowed_models": ["fvg_pullback"], "blocked_models": [],
                   "position_multiplier": 1.0, "exhausted": False, "reason": "趋势"},
        "risk": {"allowed": True, "risk_usd": 1.0, "violations": []},
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
    bars = [{"high": 101, "low": 99}, {"high": 104.5, "low": 100}]
    result = replay_shadow_records([_record()], {"s1": bars}, horizons=(2,))
    assert result["executed"] == 1
    assert result["trades"][0]["outcome"]["h2"]["first_hit"] == "target"
    assert result["trades"][0]["model_id"] == "fvg_pullback"
