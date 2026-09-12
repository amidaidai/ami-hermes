"""Offline collector regressions: no CLI, chart mutation, network or live cache writes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tv_data_bridge as bridge
from tv_indicator_contract import RISK_ROW_VARIANTS

MAIN = "副S3冲突·不执行 · 等解除"
SUB = "逆高周 · 降级 · ▼上级偏空"


def tables():
    return {"studies": [
        {"name": "SVP v13", "tables": [{"rows": [
            f"结论 | {MAIN}", "方向 | 观望", "路径 | 等解除", "风控·未授权 | 不执行"]}]},
        {"name": "AggVol v13", "tables": [{"rows": [f"结论 | {SUB}", "信号 | S3", "操作 | 等待"]}]},
    ]}


def test_main_table_does_not_merge_substudy(monkeypatch):
    """Main SVP study rows must NOT be polluted by sub-study tables."""
    payload = tables()
    monkeypatch.setattr(bridge, "_tv_json", lambda *a, **k: payload)
    result = bridge.read_dmi_table()
    # Only main SVP study rows, sub-study rows excluded
    assert result == {
        "结论": MAIN, "方向": "观望", "路径": "等解除", "风控·未授权": "不执行"
    }, f"Expected main-only table, got: {result}"
    # Sub-table should be independently accessible via study-role-aware call
    sub_result = bridge.read_dmi_table(study_role="sub")
    assert sub_result == {
        "结论": SUB, "信号": "S3", "操作": "等待"
    }, f"Expected sub-only table, got: {sub_result}"


def test_risk_row_label_uses_contract_authority(monkeypatch):
    """risk_row_label must use tv_indicator_contract RISK_ROW_VARIANTS, not hardcoded set."""
    payload = tables()
    monkeypatch.setattr(bridge, "_tv_json", lambda *a, **k: payload)
    result = bridge.read_dmi_table()
    # Use contract-authoritative label identification
    label = bridge.risk_row_label(result)
    # Must pick the most conservative (last in reversed order) matching label
    # '风控·未授权' appears before '风控' in RISK_ROW_VARIANTS reversed scan
    assert label == "风控·未授权", f"Expected '风控·未授权', got '{label}'"
    # Value must match the label
    value = bridge.risk_row_value(result)
    assert value == "不执行", f"Expected '不执行', got '{value}'"


def test_collect_with_main_only_dmi(monkeypatch, tmp_path):
    """_collect_and_cache_locked must not require hardcoded required_action_rows from merged tables."""
    monkeypatch.setattr(bridge, "CACHE", tmp_path / "tv_dmi_cache.json")
    monkeypatch.setattr(bridge, "tv_available", lambda: True)
    monkeypatch.setattr(bridge, "ensure_expected_symbol", lambda _: True)
    monkeypatch.setattr(bridge, "read_state_symbol", lambda: "BINANCE:BTCUSDT.P")
    monkeypatch.setattr(bridge, "read_indicators", lambda *_args: {
        "poc_price": "78000", "vah_price": "78500", "val_price": "77500",
        "s_vwap": "78000", "mcp_side_code": "1", "mcp_grade_code": "5",
        "mcp_setup_score": "85", "mcp_entry_price": "78000"
    })
    monkeypatch.setattr(bridge, "read_dmi_table", lambda *a: {
        "结论": MAIN, "方向": "观望", "路径": "等解除", "风控·未授权": "不执行", "等级": "5"
    })
    monkeypatch.setattr(bridge, "read_pine_lines", lambda *_args: [])
    monkeypatch.setattr(bridge, "read_quote", lambda *_args: 78001.0)
    monkeypatch.setattr(bridge, "read_chart_state", lambda: {
        "symbol": "BINANCE:BTCUSDT.P", "resolution": "15",
        "studies": [{"name": "SVP+ICT+VWAP+CVD"}],
    })
    monkeypatch.setattr(bridge, "read_pine_boxes", lambda *_args: [])
    monkeypatch.setattr(bridge, "read_pine_labels", lambda *_args: [])
    monkeypatch.setattr(bridge, "read_binance_snapshot", lambda *_a, **_k: {"status": "unavailable"})
    monkeypatch.setattr(bridge.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(bridge, "read_quote_payload", lambda *a: {
        "symbol": "BINANCE:BTCUSDT.P", "exchange": "Binance", "type": "swap",
        "last": 78001.0, "open": 77900.0, "high": 78100.0, "low": 77800.0,
        "close": 78001.0,
    })
    cache = bridge.collect_and_cache(expect_symbol="BINANCE:BTCUSDT.P")
    # Should succeed: main DMI has all required action rows with contract-authoritative labels
    assert cache is not None, "collect_and_cache returned None but should have succeeded"
    assert cache["identity_valid"] is True
    assert cache["action_table_complete"] is True
    assert cache["source_quality"] == "A"
    # The grade should reflect the contract-authorized label
    assert cache["grade"] in ("5", "A"), f"Expected grade A/5, got '{cache['grade']}'"