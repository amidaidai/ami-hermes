"""Offline fixtures for the uploaded indicator contract; not live prices."""
import pytest
import auto_card as card
import tv_indicator_contract as contract
import decision_matrix as matrix


def test_observation_risk_label_and_prices_stay_atomic():
    main = card._build_tv_main_data(
        {"等级": "B多", "方向": "偏多", "风控·观察": "入100·止99·1.8A·标103·3.0R"},
        {"MCP Entry Price": 888, "MCP Stop Price": 887, "MCP Target Price": 891},
        symbol="BTCUSDT",
    )
    assert main["risk_label"] == "风控·观察"
    assert [main.get(k) for k in ("entry", "stop", "target")] == [None] * 3
    assert [main.get("candidate_" + k) for k in ("entry", "stop", "target")] == [100, 99, 103]
    assert main["candidate_source"] == "SVP风控·观察"


def test_current_short_dw_names_reach_production_parser():
    main = card._build_tv_main_data({}, {
        "MCP CVD Method Code": 2,
        "MCP StructPack": -9879,
        "S VWAP +Band1": 102,
        "S VWAP -Band1": 98,
        "CVD Method Code (1=当前所K线方向/2=当前所1m方向)": 2,
    }, symbol="BTCUSDT")
    assert main["mcp_cvd_method_code"] == 2
    assert main["mcp_struct_pack"] == -9879
    assert main["s_vwap_band_upper"] == 102
    assert main["s_vwap_band_lower"] == 98
    assert main["sub_cvd_method_code"] == 2


@pytest.mark.parametrize("label", ["风控·未授权", "禁做·不出价"])
def test_unauthorized_rows_never_create_candidates(label):
    main = card._build_tv_main_data({"等级": "A多", label: "入100·止99·标103·3.0R"}, {}, symbol="BTCUSDT")
    assert main["risk_label"] == label
    assert all(main.get(key) is None for key in (
        "entry", "stop", "target", "candidate_entry", "candidate_stop", "candidate_target"))


def test_authorized_row_uses_whole_export_tuple_not_mixed_prices():
    main = card._build_tv_main_data(
        {"等级": "A多", "风控": "入100·止99·标103·3.0R"},
        {"MCP Entry Price": 100.04, "MCP Stop Price": 99.01, "MCP Target Price": 103.09},
        symbol="BTCUSDT")
    assert [main.get(k) for k in ("entry", "stop", "target")] == [100.04, 99.01, 103.09]
    assert main["price_source"] == "SVP执行导出"


def test_partial_execution_export_does_not_get_filled_from_panel():
    main = card._build_tv_main_data({"等级": "A多", "风控": "入100·止99·标103·3.0R"},
                                    {"MCP Entry Price": 100}, symbol="BTCUSDT")
    assert [main.get(k) for k in ("entry", "stop", "target")] == [None] * 3
    assert main["price_contract_error"] == "SVP执行三件套缺失"
