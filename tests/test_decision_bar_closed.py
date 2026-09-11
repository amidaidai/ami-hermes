"""Offline closed-bar authority and deterministic decision identity contracts."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from decision_loop import resolve_final_verdict
from decision_regime import classify_decision_regime


def _inputs():
    return {
        "symbol": "BTCUSDT",
        "main": {
            "grade": "A多", "direction": "long", "model_id": "fvg_pullback",
            "entry": 100.0, "stop": 98.0, "target": 105.0,
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


@pytest.mark.parametrize("value", [False, None, 0, 1, "true", "false", "", [], {}])
def test_bar_closed_requires_literal_true(value):
    inputs = _inputs()
    inputs["main"]["bar_closed"] = value
    out = resolve_final_verdict(**inputs)
    assert out.state == "WAIT"
    assert out.executable is False
    assert (out.entry, out.stop, out.target) == (None, None, None)
    assert "bar_closed" in out.blockers
    assert out.gates["trigger"]["status"] == "yellow"


def test_missing_a_bar_closed_is_missing_decision_evidence():
    inputs = _inputs()
    del inputs["main"]["bar_closed"]
    out = resolve_final_verdict(**inputs)
    assert out.state == "NO-GO"
    assert "decision_evidence" in out.blockers
    assert "bar_closed" in out.blockers


def test_literal_closed_bar_can_authorize():
    out = resolve_final_verdict(**_inputs())
    assert out.state == "GO-A"
    assert out.executable is True


@pytest.mark.parametrize("grade,state", [("B多", "WAIT"), ("C反多", "WAIT")])
def test_observation_preserves_all_watch_prices_without_execution(grade, state):
    inputs = _inputs()
    inputs["main"]["grade"] = grade
    del inputs["main"]["bar_closed"]
    out = resolve_final_verdict(**inputs)
    assert out.state == state
    assert out.executable is False
    assert (out.entry, out.stop, out.target) == (None, None, None)
    assert out.watch_side == "long"
    assert (out.watch_entry, out.watch_stop, out.watch_target) == (100.0, 98.0, 105.0)
    assert "decision_evidence" not in out.blockers


@pytest.mark.parametrize("grade", ["X禁做", "B多", "C反多", "A多"])
def test_hard_block_clears_all_watch_prices(grade):
    inputs = _inputs()
    inputs["main"]["grade"] = grade
    inputs["main"]["tv_live_verified"] = False
    out = resolve_final_verdict(**inputs)
    assert out.state == "NO-GO"
    assert out.executable is False
    assert out.watch_side == "neutral"
    assert (out.entry, out.stop, out.target) == (None, None, None)
    assert (out.watch_entry, out.watch_stop, out.watch_target) == (None, None, None)


def test_x_grade_alone_is_hard_block_without_watch_prices():
    inputs = _inputs()
    inputs["main"]["grade"] = "X禁做"
    out = resolve_final_verdict(**inputs)
    assert out.state == "NO-GO"
    assert "x_forbidden" in out.blockers
    assert out.watch_side == "neutral"
    assert (out.watch_entry, out.watch_stop, out.watch_target) == (None, None, None)


def test_decision_id_is_canonical_sha256_and_json_replay_stable():
    import hashlib
    import json
    from dataclasses import asdict
    from decision_regime import DecisionRegime

    inputs = _inputs()
    payload = {**inputs, "regime": asdict(inputs["regime"])}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    out = resolve_final_verdict(**inputs)
    assert out.decision_id == expected
    assert out.to_dict()["decision_id"] == expected
    replay = json.loads(canonical)
    replay["regime"] = DecisionRegime(**replay["regime"])
    assert resolve_final_verdict(**replay).decision_id == expected
    reordered = {key: inputs[key] for key in reversed(inputs)}
    reordered["main"] = dict(reversed(list(inputs["main"].items())))
    reordered["advanced"] = {"gate": {"execute": True}, "direction": "long"}
    assert resolve_final_verdict(**reordered).decision_id == expected


@pytest.mark.parametrize("component", ["symbol", "main", "dual", "regime", "risk", "advanced"])
def test_decision_id_covers_every_decision_input(component):
    from dataclasses import replace

    inputs = _inputs()
    baseline = resolve_final_verdict(**inputs).decision_id
    if component == "symbol":
        inputs[component] = "ETHUSDT"
    elif component == "regime":
        inputs[component] = replace(inputs[component], position_multiplier=0.5)
    else:
        inputs[component]["identity_probe"] = "different input"
    assert resolve_final_verdict(**inputs).decision_id != baseline
