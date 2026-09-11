"""Offline Pine-authority contracts: the pure verdict must own all vetoes."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

import pytest

os.environ["HANGQING_NO_SEND"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from decision_loop import resolve_final_verdict
from decision_regime import DecisionRegime, classify_decision_regime


def _inputs():
    return {
        "symbol": "BTCUSDT",
        "main": {
            "grade": "A多", "direction": "long", "model_id": "fvg_pullback",
            "entry": 100.0, "stop": 98.0, "target": 105.0,
            "risk_label": "风控", "mcp_entry_valid_code": 3,
            "mcp_no_trade_reason_code": 0,
            "data_grade": "A", "snapshot_age_sec": 10.0,
            "location_valid": True, "trigger_confirmed": True, "bar_closed": True,
        },
        "dual": {"asset_is_crypto": True, "valid_code": 2, "aligned": True},
        "regime": classify_decision_regime(
            adx=30, atr_ratio=1.0, ema_spread_atr=0.7,
            vwap_crosses_20=1, va_stay_ratio_20=0.2,
            displacement_atr=0.8, rvol=1.1,
        ),
        "risk": {"allowed": True, "violations": [], "risk_usd": 1.0},
        "advanced": {"direction": "long", "gate": {"execute": True}},
    }


def _closed(out):
    assert out.executable is False
    assert out.state in {"WAIT", "NO-GO"}
    assert out.side == "neutral"
    assert (out.entry, out.stop, out.target) == (None, None, None)


@pytest.mark.parametrize("label", ["风控·观察", "风控·未授权", "禁做·不出价", "", None, "unknown"])
def test_explicit_risk_label_cannot_be_upgraded_by_a_grade(label):
    inputs = _inputs()
    inputs["main"]["risk_label"] = label
    out = resolve_final_verdict(**inputs)
    _closed(out)
    assert "svp_authorization" in out.blockers
    assert out.gates["risk"]["status"] != "green"


def test_normal_risk_label_and_legacy_payload_remain_compatible():
    inputs = _inputs()
    assert resolve_final_verdict(**inputs).state == "GO-A"
    for field in ("risk_label", "mcp_entry_valid_code", "mcp_no_trade_reason_code"):
        inputs["main"].pop(field)
    assert resolve_final_verdict(**inputs).state == "GO-A"
