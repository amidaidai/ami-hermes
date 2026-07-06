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
        "_banned_live": False,
        "_reviews_count": 20,
        "_wfo_efficiency": 0.72,
        "_total_exposure_pct": 0,
    }


def _base_meta():
    return {"data_grade": "A", "rr_a": 2.5, "rr_b": 1.8, "protections_status": "通过", "status": "A多"}


def test_dual_indicator_conflict_blocks_go():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": True, "usable": True, "conflict": True}
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert not result["go"]
    assert "dual_indicator" in result["red_gates"]
    assert result["gates"]["dual_indicator"]["status"] == "red"


def test_dual_indicator_aligned_passes_gate():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": True, "usable": True, "conflict": False, "direction_verdict": "主副同向"}
    result = check_gate("BTCUSDT", engine, _base_meta())
    assert result["go"]
    assert result["gates"]["dual_indicator"]["status"] == "green"


def test_rr_below_two_blocks_execution_even_if_close():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": True, "usable": True, "conflict": False, "direction_verdict": "主副同向"}
    meta = _base_meta() | {"rr_a": 1.95, "rr_b": 1.8, "rr1": 1.95, "rr2": 1.8}
    result = check_gate("BTCUSDT", engine, meta)
    assert not result["go"]
    assert result["gates"]["rr_ratio"]["status"] == "red"
    assert "rr_ratio" in result["red_gates"]


def test_primary_rr_below_two_blocks_even_when_reverse_rr_is_good():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": True, "usable": True, "conflict": False, "direction_verdict": "主副同向"}
    meta = _base_meta() | {"rr_a": 0.69, "rr_b": 2.8, "rr1": 0.69, "rr2": 2.8}
    result = check_gate("BTCUSDT", engine, meta)
    assert not result["go"]
    assert result["gates"]["rr_ratio"]["status"] == "red"
    assert "主线1:0.7" in result["gates"]["rr_ratio"]["reason"]


def test_non_crypto_without_haldro_does_not_block():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": False, "usable": True, "conflict": False, "direction_verdict": "非加密不套HALDRO"}
    result = check_gate("XAUUSD", engine, _base_meta())
    assert result["go"]
    assert result["max_score"] == 8
    assert result["gates"]["dual_indicator"]["status"] == "green"


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
