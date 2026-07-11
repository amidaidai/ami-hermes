from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auto_card
import tv_data_bridge


def test_tv_data_bridge_adds_stable_aliases(monkeypatch):
    monkeypatch.setattr(
        tv_data_bridge,
        "_tv_json",
        lambda *args, **kwargs: {
            "success": True,
            "studies": [{
                "name": "SVP+HALDRO",
                "values": {
                    "MCP StructPack (FvgQ*10000+(OB+1)*100+(BOS+2)*10+(LV+1))": "10121",
                    "MCP Risk Pack (Risk%*10000+DailyLoss%*100+WeeklyLoss%)": "10306",
                    "MCP CVD Method Code (2=lower-TF estimate,1=bar estimate)": "2",
                    "MCP EMA Length 1": "9", "MCP EMA Length 2": "21",
                    "MCP EMA Length 3": "34", "MCP EMA Length 4": "55",
                    "MCP FVG Quality Score": "78", "MCP OB Quality Score": "82",
                    "OI Change % (Normalized)": "0.42",
                    "HALDRO Risk Code": "64",
                    "HALDRO Valid Code": "2",
                },
            }],
        },
    )
    values = tv_data_bridge.read_indicators("BINANCE:BTCUSDT.P")
    assert values["mcp_struct_pack"] == "10121"
    assert values["mcp_risk_pack"] == "10306"
    assert values["mcp_cvd_method_code"] == "2"
    assert [values[f"mcp_ema_length_{i}"] for i in range(1, 5)] == ["9", "21", "34", "55"]
    assert values["mcp_fvg_quality_score"] == "78"
    assert values["mcp_ob_quality_score"] == "82"
    assert values["oi_change_pct_normalized"] == "0.42"
    assert values["haldro_risk_code"] == "64"
    assert values["haldro_valid_code"] == "2"


def test_cache_aliases_roundtrip_to_study_values():
    studies = auto_card._tv_cache_indicators_to_studies({
        "indicators": {
            "mcp_struct_pack": 10121,
            "mcp_risk_pack": 10306,
            "mcp_cvd_method_code": 2,
            "mcp_ema_length_1": 9, "mcp_ema_length_2": 21,
            "mcp_ema_length_3": 34, "mcp_ema_length_4": 55,
            "mcp_fvg_quality_score": 78, "mcp_ob_quality_score": 82,
            "oi_change_pct_normalized": 0.42,
            "haldro_risk_code": 64,
            "haldro_valid_code": 2,
        }
    })
    merged = {k: v for study in studies for k, v in study["values"].items()}
    assert merged["MCP StructPack (FvgQ*10000+(OB+1)*100+(BOS+2)*10+(LV+1))"] == 10121
    assert merged["MCP Risk Pack (Risk%*10000+DailyLoss%*100+WeeklyLoss%)"] == 10306
    assert [merged[f"MCP EMA Length {i}"] for i in range(1, 5)] == [9, 21, 34, 55]
    assert merged["MCP FVG Quality Score"] == 78
    assert merged["MCP OB Quality Score"] == 82
    assert merged["OI Change % (Normalized)"] == 0.42
    assert merged["HALDRO Risk Code"] == 64


def test_dual_verdict_downgrades_a_signal_on_lsr_crowding():
    meta = {"status": "A做多", "direction": "long", "data_grade": "A"}
    engine_data = {
        "_tv_main": {
            "grade": "A多",
            "direction_text": "偏多",
            "sub_composite": 31,
            "sub_confirm_score": 3,
            "sub_oi_total": 1_000_000,
            "sub_oi_change_pct_normalized": 0.42,
            "sub_lsr": 1.5,
            "sub_haldro_risk_code": 64,
            "sub_coverage_exchanges": 5,
            "sub_cvd_quality_code": 0,
        }
    }
    result = auto_card._dual_indicator_verdict("BTCUSDT", meta, engine_data)
    assert result["state"].startswith("B等待")
    assert result["direction_verdict"] == "同向但拥挤降级"
    assert "LSR拥挤" in result["haldro_quality"]
    assert "0.42%" in result["haldro_position"]


def test_haldro_valid_code_controls_conflict_authority():
    base_meta = {"status": "A多", "direction": "long", "data_grade": "A"}

    def run(valid_code):
        engine = {"_tv_main": {
            "grade": "A多", "direction_text": "偏多",
            "sub_composite": -30, "sub_confirm_score": 4,
            "sub_haldro_valid_code": valid_code,
            "sub_haldro_risk_code": 0,
        }}
        return auto_card._dual_indicator_verdict("BTCUSDT", dict(base_meta), engine)

    invalid = run(0)
    fallback = run(1)
    aggregated = run(2)
    assert invalid["valid_code"] == 0 and invalid["conflict"] is False and invalid["usable"] is False
    assert fallback["valid_code"] == 1 and fallback["conflict"] is True and fallback["hard_conflict"] is False
    assert aggregated["valid_code"] == 2 and aggregated["conflict"] is True and aggregated["hard_conflict"] is True


def test_final_verdict_projection_removes_executable_order_on_no_go():
    main = {"grade": "A多", "direction_text": "偏多", "entry": 100, "stop": 98, "target": 105}
    final = {
        "state": "NO-GO", "executable": False, "side": "neutral", "grade": "X禁做",
        "entry": None, "stop": None, "target": None, "reason": "主副强冲突",
    }
    projected = auto_card._project_final_verdict(main, final)
    assert projected["grade"] == "X禁做"
    assert projected["direction_text"] == "观望"
    assert projected.get("entry") in (None, "")
    assert projected["_final_verdict"]["state"] == "NO-GO"
