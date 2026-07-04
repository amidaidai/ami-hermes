from __future__ import annotations

from go_nogo_gate import check_gate


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


def test_non_crypto_without_haldro_does_not_block():
    engine = _base_engine()
    engine["_dual_indicator_verdict"] = {"asset_is_crypto": False, "usable": True, "conflict": False, "direction_verdict": "非加密不套HALDRO"}
    result = check_gate("XAUUSD", engine, _base_meta())
    assert result["go"]
    assert result["gates"]["dual_indicator"]["status"] == "green"
