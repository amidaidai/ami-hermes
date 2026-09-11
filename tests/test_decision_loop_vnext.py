from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision_loop import resolve_final_verdict
from decision_regime import classify_decision_regime


def _trend():
    return classify_decision_regime(
        adx=30, atr_ratio=1.0, ema_spread_atr=0.7,
        vwap_crosses_20=1, va_stay_ratio_20=0.2,
        displacement_atr=0.8, rvol=1.1,
    )


def _main(**overrides):
    data = {
        "grade": "A多", "direction": "long", "model_id": "fvg_pullback",
        "entry": 100.0, "stop": 98.0, "target": 105.0, "rr": 2.5,
        "mcp_fvg_quality_score": 82.0, "mcp_ob_quality_score": 70.0,
        "data_grade": "A", "snapshot_age_sec": 10.0,
        "location_valid": True, "trigger_confirmed": True, "bar_closed": True,
    }
    data.update(overrides)
    return data


def _dual(valid_code=2, conflict=False, **overrides):
    data = {
        "asset_is_crypto": True, "valid_code": valid_code, "conflict": conflict,
        "aligned": not conflict, "risk_code": 0,
    }
    data.update(overrides)
    return data


def test_aggregated_haldro_conflict_is_hard_no_go_and_clears_order():
    out = resolve_final_verdict("BTCUSDT", _main(), _dual(2, True), regime=_trend())
    assert out.state == "NO-GO"
    assert out.side == "neutral"
    assert out.entry is None and out.stop is None and out.target is None
    assert "dual_indicator" in out.blockers


def test_fallback_haldro_conflict_can_only_wait_not_execute():
    out = resolve_final_verdict("BTCUSDT", _main(), _dual(1, True), regime=_trend())
    assert out.state == "WAIT"
    assert out.entry is None
    assert "haldro_fallback_conflict" in out.warnings


def test_invalid_haldro_does_not_invent_conflict_but_requires_wait():
    out = resolve_final_verdict("BTCUSDT", _main(), _dual(0, True), regime=_trend())
    assert out.state == "WAIT"
    assert "dual_indicator" not in out.blockers
    assert "haldro_invalid" in out.warnings


def test_non_crypto_ignores_haldro_and_can_go():
    dual = {"asset_is_crypto": False, "valid_code": 0, "conflict": True}
    out = resolve_final_verdict(
        "XAUUSD", _main(), dual, regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}},
    )
    assert out.state == "GO-A"
    assert out.entry == 100.0


def test_low_quality_primary_zone_cannot_execute():
    out = resolve_final_verdict(
        "BTCUSDT", _main(mcp_fvg_quality_score=50.0), _dual(), regime=_trend()
    )
    assert out.state == "WAIT"
    assert "zone_quality" in out.blockers


def test_regime_model_mismatch_is_no_go():
    balance = classify_decision_regime(
        adx=15, atr_ratio=1.0, ema_spread_atr=0.2,
        vwap_crosses_20=6, va_stay_ratio_20=0.8,
        displacement_atr=0.2, rvol=0.8,
    )
    out = resolve_final_verdict("BTCUSDT", _main(), _dual(), regime=balance)
    assert out.state == "NO-GO"
    assert "regime_model" in out.blockers


def test_risk_constitution_is_final_authority():
    out = resolve_final_verdict(
        "BTCUSDT", _main(), _dual(), regime=_trend(),
        risk={"allowed": False, "violations": ["日回撤熔断"], "risk_usd": 0.0},
    )
    assert out.state == "NO-GO"
    assert "risk_constitution" in out.blockers
    assert out.risk_usd == 0.0


def test_all_hard_gates_pass_returns_go_a():
    out = resolve_final_verdict(
        "BTCUSDT", _main(), _dual(), regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}},
    )
    assert out.state == "GO-A"
    assert out.side == "long"
    assert out.entry == 100.0
    assert out.risk_usd == 1.0
    assert set(out.gates) == {"data", "background", "regime", "location", "trigger", "orderflow", "rr", "risk"}
    assert all(gate["status"] == "green" for gate in out.gates.values())


def test_go_a_missing_execution_prices_fails_closed_to_wait():
    out = resolve_final_verdict(
        "BTCUSDT",
        _main(entry=None, stop=None, target=None),
        _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
    )

    assert out.state == "WAIT"
    assert out.executable is False
    assert out.entry is None and out.stop is None and out.target is None
    assert "execution_contract" in out.blockers


def test_go_a_invalid_execution_geometry_fails_closed_to_wait():
    out = resolve_final_verdict(
        "BTCUSDT",
        _main(stop=102.0),
        _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
    )

    assert out.state == "WAIT"
    assert out.executable is False
    assert out.entry is None and out.stop is None and out.target is None
    assert "execution_contract" in out.blockers


def test_go_a_uses_geometric_rr_instead_of_trusting_claimed_rr():
    out = resolve_final_verdict(
        "BTCUSDT",
        _main(target=101.0, rr=2.5),
        _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
    )

    assert out.state == "WAIT"
    assert out.executable is False
    assert out.rr == 0.5
    assert "rr_ratio" in out.blockers


def test_short_execution_uses_short_geometry_and_geometric_rr():
    out = resolve_final_verdict(
        "BTCUSDT",
        _main(direction="short", grade="A空", stop=102.0, target=94.0, rr=99.0),
        _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}},
    )

    assert out.state == "GO-A"
    assert out.side == "short"
    assert out.rr == 3.0


def test_nonfinite_execution_price_fails_closed():
    out = resolve_final_verdict(
        "BTCUSDT",
        _main(entry="nan"),
        _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
    )

    assert out.state == "WAIT"
    assert out.executable is False
    assert "execution_contract" in out.blockers


def test_zero_risk_budget_cannot_produce_go_a():
    out = resolve_final_verdict(
        "BTCUSDT", _main(), _dual(), regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 0.0},
    )

    assert out.state == "NO-GO"
    assert out.executable is False
    assert "risk_constitution" in out.blockers


def test_wait_keeps_observation_fields_separate_from_execution_tuple():
    out = resolve_final_verdict(
        "BTCUSDT",
        _main(grade="C等待", direction="short"),
        _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
    )

    assert out.state == "WAIT"
    assert out.side == "neutral"
    assert out.entry is None and out.stop is None and out.target is None
    assert out.watch_side == "short"
    assert out.watch_entry == 100.0


def test_required_five_timeframe_snapshot_is_a_hard_data_gate():
    out = resolve_final_verdict(
        "BTCUSDT",
        _main(tv_five_tf_required=True, tv_five_tf_verified=False),
        _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
    )

    assert out.state == "NO-GO"
    assert out.executable is False
    assert "tv_five_tf" in out.blockers
    assert out.gates["tv_five_tf"]["status"] == "red"


def test_cross_source_hard_blockers_are_consumed_by_final_verdict():
    out = resolve_final_verdict(
        "BTCUSDT",
        _main(cross_source_hard_blockers=["tv_main"], cross_source_warnings=["cg_pro"]),
        _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
    )

    assert out.state == "NO-GO"
    assert "cross_source" in out.blockers
    assert out.gates["cross_source"]["status"] == "red"
    assert "cross_source:cg_pro" in out.warnings


def test_unknown_legacy_model_is_inferred_from_active_zone_quality():
    main = _main(model_id="无", mcp_fvg_quality_score=82, mcp_ob_quality_score=50)
    out = resolve_final_verdict("BTCUSDT", main, _dual(), regime=_trend())
    assert out.model_id == "fvg_pullback"
    assert out.state == "NO-GO"
    assert "risk_constitution" in out.blockers


def test_execution_candidate_missing_explicit_data_evidence_fails_closed():
    main = _main()
    for key in ("data_grade", "snapshot_age_sec", "location_valid", "trigger_confirmed"):
        main.pop(key)
    out = resolve_final_verdict(
        "BTCUSDT", main, _dual(), regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}},
    )
    assert out.state == "NO-GO"
    assert "decision_evidence" in out.blockers


def test_execution_candidate_missing_advanced_gate_can_only_wait():
    out = resolve_final_verdict(
        "BTCUSDT", _main(), _dual(), regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
    )
    assert out.state == "WAIT"
    assert "advanced_pending" in out.blockers


def test_source_snapshot_uses_the_same_one_hour_ttl_as_data_boundary():
    ok = resolve_final_verdict(
        "BTCUSDT", _main(snapshot_age_sec=3599), _dual(), regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}},
    )
    stale = resolve_final_verdict(
        "BTCUSDT", _main(snapshot_age_sec=3601), _dual(), regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}},
    )
    assert ok.state == "GO-A"
    assert stale.state == "NO-GO"
    assert "data" in stale.blockers


def test_unclosed_svp_action_text_forces_wait_even_when_legacy_grade_is_a():
    out = resolve_final_verdict(
        "BTCUSDT",
        _main(conclusion="⚠未收线 · 等收线", treatment="等收线", action="A空"),
        _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
    )
    assert out.state == "WAIT"
    assert not out.executable
    assert out.entry is None and out.stop is None and out.target is None
    assert "svp_wait_language" in out.blockers


def test_svp_conflict_text_forces_wait_even_when_legacy_grade_is_a():
    out = resolve_final_verdict(
        "BTCUSDT",
        _main(conclusion="A空 ⚠冲突", path="等解除"),
        _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
    )
    assert out.state == "WAIT"
    assert not out.executable
    assert "svp_wait_language" in out.blockers
