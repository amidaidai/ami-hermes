from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from position_sizer import position_from_final_verdict


def test_position_sizer_cannot_override_no_go():
    result = position_from_final_verdict({
        "state": "NO-GO", "executable": False, "risk_usd": 0,
        "entry": None, "stop": None, "side": "neutral", "reason": "dual_indicator",
    }, symbol="BTCUSDT")
    assert result["tier"] == "禁止"
    assert result["risk_usd"] == 0


def test_position_sizer_projects_authoritative_risk_and_quantity():
    result = position_from_final_verdict({
        "state": "GO-A", "executable": True, "risk_usd": 1.0,
        "entry": 100.0, "stop": 98.0, "side": "long", "reason": "全部通过",
    }, symbol="BTCUSDT")
    assert result["risk_usd"] == 1.0
    assert result["position_qty_btc"] == 0.5
    assert result["tier"] == "常规"
