from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from go_nogo_gate import check_gate
import auto_card


def _base_engine():
    return {
        "_snapshot_age_h": 0.1,
        "_tv_main": {"grade": "A多"},
        "_tv_cache_status": {"usable": True, "reason": "测试现场已验证"},
        "_final_verdict": {"state": "GO-A", "executable": True, "reason": "测试授权"},
        "_banned_live": False,
        "_reviews_count": 20,
        "_wfo_efficiency": 0.72,
        "_total_exposure_pct": 0,
    }


def _base_meta():
    return {"data_grade": "A", "rr_a": 2.5, "rr_b": 1.8, "protections_status": "通过", "status": "A多"}


def test_legacy_dual_diagnostic_cannot_override_final_verdict():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": True, "usable": True, "conflict": True}
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert result["go"]
    assert result["execution_authorized"]
    assert "dual_indicator" in result["red_gates"]
    assert "dual_indicator" in result["diagnostic_red_gates"]
    assert result["gates"]["dual_indicator"]["status"] == "red"


def test_dual_indicator_aligned_passes_gate():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": True, "usable": True, "conflict": False, "direction_verdict": "主副同向"}
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert result["go"]
    assert result["gates"]["dual_indicator"]["status"] == "green"


def test_legacy_tv_diagnostic_cannot_override_final_verdict():
    engine = _base_engine()
    engine.pop("_tv_cache_status")
    engine["_tv_pine"] = {"tables": [{"rows": ["等级 | A多"]}]}
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert result["go"]
    assert result["execution_authorized"]
    assert "tv_live" in result["red_gates"]
    assert result["gates"]["tv_live"]["status"] == "red"


def test_missing_tv_is_retained_as_diagnostic_when_final_verdict_is_authorized():
    engine = _base_engine()
    engine.pop("_tv_cache_status")
    engine.pop("_tv_main")
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert result["go"]
    assert result["execution_authorized"]
    assert "tv_live" in result["red_gates"]
    assert result["gates"]["tv_live"]["status"] == "red"


def test_required_full_timeframes_cannot_be_hidden_by_a_valid_main_period():
    engine = _base_engine()
    engine["_tv_five_tf_required"] = True
    engine["_tv_five_tf_status"] = {"usable": False, "coverage": 4, "missing": ["5m"]}

    result = check_gate("BTCUSDT", engine, _base_meta())

    assert result["go"]
    assert result["execution_authorized"]
    assert "tv_live" in result["red_gates"]
    assert "五周期" in result["gates"]["tv_live"]["reason"]


def test_missing_final_verdict_cannot_greenlight():
    engine = _base_engine()
    engine.pop("_final_verdict")
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert not result["go"]
    assert result["final_state"] == "NO-GO"
    assert "final_verdict" in result["red_gates"]


def test_single_source_haldro_conflict_is_yellow_not_hard_block():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {
        "asset_is_crypto": True, "usable": True, "valid_code": 1,
        "conflict": True, "hard_conflict": False, "direction_verdict": "单源冲突，仅等待",
    }
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert result["go"]
    assert result["gates"]["dual_indicator"]["status"] == "yellow"
    assert "dual_indicator" in result["yellow_gates"]


def test_invalid_haldro_is_yellow_and_cannot_create_red_conflict():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {
        "asset_is_crypto": True, "usable": False, "valid_code": 0,
        "conflict": False, "hard_conflict": False,
    }
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert result["go"]
    assert result["gates"]["dual_indicator"]["status"] == "yellow"


def test_rr_diagnostic_does_not_override_final_verdict():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": True, "usable": True, "conflict": False, "direction_verdict": "主副同向"}
    meta = _base_meta() | {"rr_a": 1.95, "rr_b": 1.8, "rr1": 1.95, "rr2": 1.8}
    result = check_gate("BTCUSDT", engine, meta)
    assert result["go"]
    assert result["execution_authorized"]
    assert result["gates"]["rr_ratio"]["status"] == "red"
    assert "rr_ratio" in result["red_gates"]


def test_primary_rr_diagnostic_does_not_override_final_verdict():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": True, "usable": True, "conflict": False, "direction_verdict": "主副同向"}
    meta = _base_meta() | {"rr_a": 0.69, "rr_b": 2.8, "rr1": 0.69, "rr2": 2.8}
    result = check_gate("BTCUSDT", engine, meta)
    assert result["go"]
    assert result["execution_authorized"]
    assert result["gates"]["rr_ratio"]["status"] == "red"
    assert "主线1:0.7" in result["gates"]["rr_ratio"]["reason"]


def test_non_crypto_without_haldro_does_not_block():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": False, "usable": True, "conflict": False, "direction_verdict": "非加密不套HALDRO"}
    result = check_gate("XAUUSD", engine, _base_meta())
    assert result["go"]
    assert result["max_score"] == 8
    assert result["gates"]["dual_indicator"]["status"] == "green"


def test_final_verdict_wait_is_single_execution_authority():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {
        "asset_is_crypto": True, "usable": False, "valid_code": 0,
        "conflict": False, "hard_conflict": False,
    }
    engine["_final_verdict"] = {
        "state": "WAIT", "executable": False,
        "reason": "等待：haldro_invalid/rr_ratio",
    }
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert not result["go"]
    assert result["final_state"] == "WAIT"
    assert result["verdict"].startswith("○ WAIT")


def test_final_verdict_no_go_overrides_legacy_green_gates():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {
        "asset_is_crypto": True, "usable": True, "valid_code": 2,
        "conflict": False, "hard_conflict": False, "direction_verdict": "主副同向",
    }
    engine["_final_verdict"] = {
        "state": "NO-GO", "executable": False,
        "reason": "硬闸门：risk_constitution",
    }
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert not result["go"]
    assert result["final_state"] == "NO-GO"
    assert result["verdict"].startswith("✗ NO-GO")


def test_tv_cache_indicator_mapping_keeps_lsr():
    studies = auto_card._tv_cache_indicators_to_studies({"indicators": {"lsr": 1.42, "composite": 31, "confirm_score": 4}})
    vals = auto_card._parse_tv_study_values(studies)
    main = auto_card._build_tv_main_data({}, vals)
    assert main["sub_lsr"] == 1.42
    assert main["sub_composite"] == 31


def test_dual_indicator_verdict_renders_lsr_crowding():
    engine = {"_tv_main": {"grade": "A多", "sub_composite": 31, "sub_confirm_score": 4, "sub_lsr": 1.42}}
    meta = {"status": "A多", "direction": "long", "data_grade": "A"}
    dual = auto_card._dual_indicator_verdict("BTCUSDT", meta, engine)
    assert dual["usable"]
    assert "LSR 1.42" in dual["haldro_position"]
    assert "多头拥挤" in dual["haldro_position"]
