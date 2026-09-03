from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import signal_confluence
import signal_validators


def _verdict(**overrides):
    value = {
        "state": "GO-A",
        "executable": True,
        "side": "long",
        "grade": "A多",
        "model_id": "fvg_pullback",
        "entry": 100.0,
        "stop": 98.0,
        "target": 105.0,
        "rr": 2.5,
        "risk_usd": 1.0,
        "reason": "全部硬闸门通过",
        "blockers": [],
        "warnings": [],
    }
    value.update(overrides)
    return value


def test_active_validator_accepts_only_a_complete_final_verdict():
    result = signal_validators.validate_final_verdict(_verdict())

    assert result["pass"] is True
    assert result["blockers"] == []


def test_active_validator_rejects_execution_fields_on_wait():
    result = signal_validators.validate_final_verdict(
        _verdict(state="WAIT", executable=False, side="neutral", entry=None, stop=None, target=None)
    )

    assert result["pass"] is True
    assert signal_validators.validate_plan("BTCUSDT", "long")["pass"] is False


def test_active_validator_uses_validated_tv_snapshot_for_alignment():
    snapshot = {
        "usable": True,
        "timeframes": {
            tf: {"direction": "偏多"}
            for tf in ("D", "4h", "1h", "15m", "5m")
        },
    }
    result = signal_validators.tf_alignment("BTCUSDT", snapshot=snapshot)

    assert result["available"] is True
    assert result["aligned"] is True
    assert result["regime_label"] == "trend"


def test_confluence_plan_is_only_a_final_verdict_projection():
    wait_plan = signal_confluence.compute_plan(
        final_verdict=_verdict(
            state="WAIT", executable=False, side="neutral",
            entry=None, stop=None, target=None,
        )
    )
    go_plan = signal_confluence.compute_plan(final_verdict=_verdict())

    assert wait_plan["qualified"] is False
    assert wait_plan["entry"] is None
    assert wait_plan["stop"] is None
    assert wait_plan["target"] is None
    assert go_plan["qualified"] is True
    assert (go_plan["entry"], go_plan["stop"], go_plan["target"]) == (100.0, 98.0, 105.0)
    assert go_plan["source"] == "FinalVerdict"


def test_confluence_report_marks_authority_without_numbered_gate_rows():
    report = signal_confluence.build_report({
        "symbol": "BTCUSDT",
        "final_verdict": _verdict(),
        "source_matrix": [{
            "label": "TV五周期", "status": "live",
            "entered_final_verdict": True, "impact": "五层完整性硬闸",
            "evidence": "覆盖5/5",
        }],
    }, "2026年9月2日17：30")

    assert "已入FinalVerdict" in report
    assert "| # |" not in report
    assert "| 1 |" not in report
