"""Offline authority-boundary regressions; no collectors or delivery imports."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from decision_loop import resolve_final_verdict
from decision_regime import classify_decision_regime


def _resolve(*, main_changes=None, dual_changes=None, advanced=None, missing=(), missing_dual=()):
    main = {
        "grade": "A多", "direction": "long", "model_id": "fvg_pullback",
        "entry": 100.0, "stop": 98.0, "target": 105.0, "rr": 2.5,
        "mcp_fvg_quality_score": 82.0, "data_grade": "A",
        "snapshot_age_sec": 10.0, "location_valid": True,
        "trigger_confirmed": True, "bar_closed": True,
    }
    main.update(main_changes or {})
    for key in missing:
        main.pop(key)
    dual = {"asset_is_crypto": True, "valid_code": 2,
            "conflict": False, "aligned": True, "risk_code": 0}
    dual.update(dual_changes or {})
    for key in missing_dual:
        dual.pop(key)
    regime = classify_decision_regime(
        adx=30, atr_ratio=1.0, ema_spread_atr=0.7,
        vwap_crosses_20=1, va_stay_ratio_20=0.2,
        displacement_atr=0.8, rvol=1.1,
    )
    return resolve_final_verdict(
        "BTCUSDT", main, dual, regime=regime,
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}} if advanced is None else advanced,
    )


def _assert_closed(out):
    assert out.state in ("WAIT", "NO-GO")
    assert out.executable is False
    assert out.side == "neutral"
    assert (out.entry, out.stop, out.target) == (None, None, None)


@pytest.mark.parametrize("field,blocker", [
    ("location_valid", "location"), ("trigger_confirmed", "trigger"),
])
@pytest.mark.parametrize("value", [None, False, 0, 1, "true", "false", ""])
def test_authorizing_evidence_requires_literal_true(field, blocker, value):
    out = _resolve(main_changes={field: value})
    _assert_closed(out)
    assert blocker in out.blockers
    assert out.gates[blocker]["status"] == "yellow"


@pytest.mark.parametrize("field", ["location_valid", "trigger_confirmed"])
def test_missing_evidence_preserves_decision_evidence_blocker(field):
    out = _resolve(missing=(field,))
    _assert_closed(out)
    assert out.state == "NO-GO"
    assert "decision_evidence" in out.blockers


def test_literal_true_evidence_can_authorize():
    out = _resolve()
    assert out.state == "GO-A"
    assert out.executable is True
    assert (out.entry, out.stop, out.target) == (100.0, 98.0, 105.0)


@pytest.mark.parametrize("value", [None, False, 0, 1, "true", "false", ""])
def test_main_sub_alignment_requires_literal_true(value):
    out = _resolve(dual_changes={"aligned": value})
    _assert_closed(out)
    assert "dual_alignment" in out.blockers
    assert out.gates["orderflow"]["status"] == "yellow"


def test_missing_crypto_alignment_cannot_authorize():
    out = _resolve(missing_dual=("aligned",))
    _assert_closed(out)
    assert "dual_alignment" in out.blockers


@pytest.mark.parametrize("aligned", [True, False, None, 1, "true"])
def test_hard_conflict_stays_no_go_regardless_of_alignment(aligned):
    out = _resolve(dual_changes={"conflict": True, "aligned": aligned})
    _assert_closed(out)
    assert out.state == "NO-GO"
    assert "dual_indicator" in out.blockers
    assert out.gates["orderflow"]["status"] == "red"


def test_explicit_noncrypto_main_sub_misalignment_cannot_authorize():
    out = _resolve(dual_changes={"asset_is_crypto": False, "aligned": False})
    _assert_closed(out)
    assert "dual_alignment" in out.blockers


@pytest.mark.parametrize("side", ["long", "short"])
@pytest.mark.parametrize("direction", ["long", "short", "neutral", None, "", 1, True, "buy"])
def test_advanced_direction_must_match_candidate_side(side, direction):
    changes = {} if side == "long" else {
        "direction": "short", "grade": "A空", "stop": 102.0, "target": 95.0,
    }
    out = _resolve(main_changes=changes,
                   advanced={"direction": direction, "gate": {"execute": True}})
    if direction == side:
        assert out.state == "GO-A"
        assert out.side == side
    else:
        _assert_closed(out)
        assert "advanced_direction" in out.blockers
        assert out.gates["orderflow"]["status"] == "yellow"


def test_advanced_veto_remains_hard_with_wrong_direction():
    out = _resolve(advanced={"direction": "short", "gate": {"execute": False}})
    _assert_closed(out)
    assert out.state == "NO-GO"
    assert "advanced_confluence" in out.blockers
    assert out.gates["orderflow"]["status"] == "red"