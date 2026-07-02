#!/usr/bin/env python3
"""Regression tests for the dual TradingView indicator card renderer."""
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / "scripts" / "render_tv_card.py"
AUTO_CARD = ROOT / "scripts" / "auto_card.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_push_card_uses_action_panel_trade_fields_without_emoji():
    render = _load(RENDER, "render_tv_card_under_test")
    card = render.render_tv_card(
        {
            "grade": "A多",
            "vwap": 62480,
            "vah": 63820,
            "val": 61950,
            "poc": 63100,
            "entry": "扫低收回 62,480",
            "stop": "61,950 (1.8ATR)",
            "target": "POC 63,820 R:R 2.5R",
            "magnet_up": "前高 64,120 分82",
            "magnet_down": "VAL 61,950 分76",
        },
        {
            "signal": "🟢 偏多 · 3/4共振",
            "conclusion": "实涨可信 · 新钱+买盘 ✅",
            "oi": "▲新多进场",
            "cvd_flow": "▲买盘占优",
            "volume": "▲放量 · ⚠永续主导",
        },
        "BTCUSDT.P",
        62500,
        mode="push",
    )
    assert "↑做多 A多" in card
    assert "进 扫低收回 62,480" in card
    assert "损 61,950 (1.8ATR)" in card
    assert "标 POC 63,820 R:R 2.5R" in card
    assert "磁吸 上 前高 64,120" in card
    assert "🔥" not in card and "🟢" not in card and "✅" not in card
    assert "**" not in card and "|" not in card


def test_auto_card_builds_v2_action_panel_fields_for_renderer():
    ac = _load(AUTO_CARD, "auto_card_under_test_render")
    main = ac._build_tv_main_data(
        {
            "等级": "A空",
            "结论": "A空 反抽",
            "方向": "偏空 · 深溢价",
            "进场": "扫高受阻 64,200",
            "止损": "64,850 (1.4ATR)",
            "目标": "VAL 62,900 2.1R",
            "核对": "HTF✓ EMA✓ CVD✓",
            "磁吸↑": "PDH 65,200 分80",
            "磁吸↓": "VAL 62,900 分85",
        },
        {"S VWAP": 64000, "VAH Price": 64600, "VAL Price": 62900, "POC Price": 63800},
    )
    assert main["grade"] == "A空"
    assert main["entry"] == "扫高受阻 64,200"
    assert main["stop"] == "64,850 (1.4ATR)"
    assert main["target"] == "VAL 62,900 2.1R"
    assert main["magnet_down"] == "VAL 62,900 分85"
    assert main["vwap"] == 64000


def test_auto_card_accepts_current_mcp_data_window_fields():
    ac = _load(AUTO_CARD, "auto_card_under_test_mcp_dw")
    vals = ac._parse_tv_study_values([
        {"name": "SVP+ICT+VWAP+CVD", "values": {
            "MCP Side Code": "-1", "MCP Grade Code": "3", "MCP Setup Score": "8",
            "MCP Entry Price": "64,200", "MCP Stop Price": "64,850",
            "MCP Target Price": "62,900", "MCP Quality Code": "48",
        }},
        {"name": "Volume Aggregated Spot & Futures", "values": {
            "OI Total": "106.25 K", "Coverage Exchanges": "4", "Confirm Score": "3", "Composite": "-31",
        }},
    ])
    main = ac._build_tv_main_data({}, vals)
    assert main["grade"] == "A空"
    assert main["mcp_setup_score"] == 8
    assert main["mcp_quality_code"] == 48
    assert main["sub_oi_total"] == 106250
    assert main["sub_composite"] == -31


def test_auto_card_parses_current_sub_indicator_rows():
    ac = _load(AUTO_CARD, "auto_card_under_test_sub_rows")
    rows = ac._parse_tv_sub_table([{"name": "Volume Aggregated Spot & Futures", "tables": [{"rows": [
        "信号 | 🟡 偏空 · 2/4共振 · 新空 3/5",
        "结论 | 真实下跌 · 新空进场 ✅",
        "风险 | ⚠单所主导",
        "覆盖 | 聚合4/5 · 现3 永4 · 覆盖80%",
        "量能 | ▲放量 · 合72%⚠主导",
        "操作 | 配合主指标 A空 = 可做",
    ]}]}])
    assert rows["signal"].startswith("🟡 偏空")
    assert rows["risk"] == "⚠单所主导"
    assert rows["coverage"].startswith("聚合4/5")
    assert rows["volume"].startswith("▲放量")
