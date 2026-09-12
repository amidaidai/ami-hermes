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


def test_renderer_fails_closed_without_final_verdict_even_with_legacy_order_fields():
    render = _load(RENDER, "render_tv_card_missing_final_verdict")
    card = render.render_tv_card(
        {"grade": "A多", "entry": 100, "stop": 98, "target": 105},
        {}, "BTCUSDT", 100, mode="push",
    )
    # 无 FinalVerdict = 不可执行：只允许「等待」，不得出现任何方向主推。
    assert "⭐主推 多" not in card and "⭐主推 空" not in card
    assert "多 损98 标105" not in card
    assert "损98" not in card and "标105" not in card
    assert "⭐主推 等待" in card
    assert "WAIT" in card or "等待" in card or "禁做" in card


def test_push_card_uses_phone_friendly_one_table_format():
    render = _load(RENDER, "render_tv_card_under_test")
    card = render.render_tv_card(
        {
            "grade": "A多",
            "vwap": 62480,
            "vah": 63820,
            "val": 61950,
            "poc": 63100,
            "entry": 62480,
            "stop": 61950,
            "target": 63820,
            "_final_verdict": {
                "state": "GO-A", "executable": True, "side": "long",
                "grade": "A多", "entry": 62480,
                "stop": 61950, "target": 63820,
            },
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
    assert card.startswith("📊 BTC · ")
    assert "🟢做多 · 🟢A多" in card
    assert "| 执行 | 触发/价格 | 风险与目标 |" in card
    assert "| ⭐主推 多 | 62480 | 损61950 · 标63820 |" in card
    assert "| 🔁失效看空 | 前高 64,120" in card
    assert "订单流：持仓▲新多进场 · CVD▲买盘占优" in card
    assert "**实涨可信 · 新钱+买盘**" in card
    assert card.count("| 执行 |") == 1
    assert "| 验证 |" not in card


def test_auto_card_builds_current_risk_row_into_execution_prices():
    ac = _load(AUTO_CARD, "auto_card_under_test_risk_row")
    main = ac._build_tv_main_data(
        {
            "结论": "A空 反抽失败",
            "方向": "偏空 · 走弱",
            "路径": "等反抽不过",
            "风控": "入64200·止64850·1.4A·标62900·2.1R",
            "磁吸↑": "PDH 65200 分80",
            "磁吸↓": "VAL 62900 分85",
        },
        {
            "S VWAP": 64000, "VAH Price": 64600, "VAL Price": 62900, "POC Price": 63800,
            "MCP Entry Price": 64200, "MCP Stop Price": 64850, "MCP Target Price": 62900,
        },
    )
    assert main["risk_label"] == "风控"
    assert main["entry"] == 64200
    assert main["stop"] == 64850
    assert main["target"] == 62900
    assert main["price_source"] == "SVP执行导出"
    assert main["magnet_down"].startswith("VAL")


def test_auto_card_panel_risk_text_is_not_execution_export():
    ac = _load(AUTO_CARD, "auto_card_under_test_panel_not_export")
    main = ac._build_tv_main_data(
        {
            "结论": "A空 反抽失败",
            "风控": "入64200·止64850·1.4A·标62900·2.1R",
        },
        {"S VWAP": 64000},
    )
    assert main["risk_label"] == "风控"
    assert main.get("entry") is None
    assert main.get("price_source") == "none"
    assert "缺失" in str(main.get("price_contract_error") or "")


def test_auto_card_observation_risk_does_not_become_entry():
    ac = _load(AUTO_CARD, "auto_card_under_test_obs_risk")
    main = ac._build_tv_main_data(
        {
            "结论": "B空·等收线",
            "风控·观察": "入64200·止64850·1.8A·标62900·2.0R",
            "位置": "价在VA上",
        },
        {},
    )
    assert main.get("entry") in (None, "", [])
    assert main["candidate_entry"] == 64200
    assert main["candidate_source"] == "SVP风控·观察"


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


def test_auto_card_parses_current_sub_indicator_rows(ac=None):
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


def test_auto_card_converts_tv_bridge_cache_indicators_to_studies():
    ac = _load(AUTO_CARD, "auto_card_under_test_cache_bridge")
    cache = {"indicators": {
        "mcp_side_code": "-1", "mcp_grade_code": "3", "mcp_setup_score": "8",
        "mcp_entry_price": "64,200", "mcp_stop_price": "64,850",
        "mcp_target_price": "62,900", "mcp_cvd_value": "-2,400",
        "mcp_quality_code": "48", "mcp_bull_fvg_ce": "61,800",
        "mcp_bear_fvg_ce": "64,300", "mcp_fvg_quality_code": "23",
        "oi_total": "1.92 B", "estimated_cvd_value": "844.53 M",
        "cvd_method_code": "2", "cvd_quality_code": "3", "composite": "-31",
    }}
    vals = ac._parse_tv_study_values(ac._tv_cache_indicators_to_studies(cache))
    main = ac._build_tv_main_data({}, vals)
    assert main["grade"] == "A空"
    assert main["mcp_bear_fvg_ce"] == 64300
    assert main["mcp_fvg_quality_code"] == 23
    assert main["sub_estimated_cvd_value"] == 844530000
    assert main["sub_cvd_method_code"] == 2
    assert main["sub_composite"] == -31


def test_auto_card_builds_tables_from_tv_bridge_decision_cache():
    ac = _load(AUTO_CARD, "auto_card_under_test_decision_cache")
    tables = ac._tv_cache_decision_tables({"decision_table": {
        "结论": "A空 反抽", "方向": "偏空", "进场": "扫高受阻 64,200",
        "止损": "64,850", "目标": "VAL 62,900", "信号": "🟡 偏空 · 3/4共振",
        "持仓": "▼新空进场", "流向": "▼卖盘占优", "量能": "▲放量", "操作": "A空=可做",
    }}, grade="A空", treatment="反抽")
    main = ac._parse_tv_dmi_table(tables)
    sub = ac._parse_tv_sub_table(tables)
    assert main["等级"] == "A空"
    assert main["进场"] == "扫高受阻 64,200"
    assert sub["signal"].startswith("🟡 偏空")
    assert sub["oi"] == "▼新空进场"


def test_renderer_never_shows_star_order_when_final_verdict_is_no_go():
    render = _load(RENDER, "render_tv_card_final_verdict")
    card = render.render_tv_card(
        {
            "grade": "A多", "entry": 100, "stop": 98, "target": 105,
            "_final_verdict": {
                "state": "NO-GO", "executable": False, "side": "neutral",
                "grade": "X禁做", "entry": None, "stop": None, "target": None,
                "reason": "硬闸门：dual_indicator",
            },
        },
        {"signal": "偏空"}, "BTCUSDT", 100, mode="push",
    )
    # NO-GO 只允许「禁做」主推行，绝不允许把方向主推渲出来。
    assert "⭐主推 多" not in card and "⭐主推 空" not in card
    assert "⭐主推 禁做" in card
    assert "X禁做" in card


def test_renderer_surfaces_regime_model_and_final_state_once():
    render = _load(RENDER, "render_tv_card_regime")
    card = render.render_tv_card(
        {
            "grade": "A多", "entry": 100, "stop": 98, "target": 105,
            "_decision_regime": {"name": "趋势"},
            "_final_verdict": {
                "state": "GO-A", "executable": True, "side": "long", "grade": "A多",
                "entry": 100, "stop": 98, "target": 105, "model_id": "fvg_pullback", "reason": "全部通过",
            },
        }, {"signal": "偏多"}, "BTCUSDT", 100, mode="push",
    )
    assert card.count("体制趋势 · 模型fvg_pullback · GO-A") == 1


def test_no_go_card_never_claims_dual_alignment_when_final_verdict_blocks_conflict():
    render = _load(RENDER, "render_tv_card_no_go_dual_conflict")
    card = render.render_tv_card(
        {
            "grade": "A空", "entry": 100, "stop": 102, "target": 96,
            "_final_verdict": {
                "state": "NO-GO", "executable": False, "side": "neutral",
                "grade": "X禁做", "entry": None, "stop": None, "target": None,
                "reason": "硬闸门：dual_indicator",
            },
            "_dual": {"direction_verdict": "主副同向", "hard_conflict": True},
        },
        {"signal": "S3冲突"}, "BTCUSDT", 100, mode="push",
    )
    assert "主副同向" not in card
    assert "主副强冲突" in card


def test_wait_card_does_not_leak_raw_entry_as_a_trigger_price():
    render = _load(RENDER, "render_tv_card_wait_without_raw_entry")
    card = render.render_tv_card(
        {
            "grade": "A空", "entry": 100, "stop": 102, "target": 96,
            "_final_verdict": {
                "state": "WAIT", "executable": False, "side": "neutral",
                "grade": "C等待", "entry": None, "stop": None, "target": None,
                "reason": "等待：trigger/未收线",
            },
        },
        {"signal": "等待确认"}, "BTCUSDT", 99, mode="push",
    )
    assert "| ⭐主推 等待 | 等待确认 | 不追现价 |" in card
    assert "损102" not in card and "标96" not in card
    assert "| 🔵主推 等 | 100 |" not in card


def test_v96_missing_final_verdict_fails_closed_even_with_legacy_go_status():
    render = _load(ROOT / "scripts" / "render_v96.py", "render_v96_missing_final")
    card = render.render_v96_card(
        "BTCUSDT", "GO-A", "long", 100, 110, 90, 0, "", "买", "A", "买", 2.5,
        "0.01%", "纽约", {}, "25", [], False,
        {"entry": 100, "stop": 98, "target": 105}, {"entry": 100, "stop": 98, "target": 105},
        2.5, 2.0, "", "", risk_amt=1, leverage_text="", inv_line="—",
        prot_status="A", data_grade="A", sweep_state="", displacement="", one_reason="",
        model_id="legacy", n5=5, eng_conf=0.9, klines={}, final_verdict=None,
    )
    assert "⭐主推" not in card
    assert "损98" not in card and "标105" not in card
    assert "禁做" in card or "等确认" in card


def test_v96_card_uses_final_verdict_for_conflict_and_never_leaks_prices():
    render = _load(ROOT / "scripts" / "render_v96.py", "render_v96_final_verdict")
    card = render.render_v96_card(
        "BTCUSDT", "A多", "long", 100, 110, 90, 0, "", "买", "A", "买", 1.1,
        "0.01%", "纽约", {}, "25", [], False,
        {"stop": 98, "target": 105}, {"stop": 98, "target": 105}, 2.5, 2.0, "", "",
        risk_amt=10, leverage_text="", inv_line="—", prot_status="C",
        data_grade="", sweep_state="", displacement="", one_reason="",
        model_id="model", n5=0, eng_conf=0,
        klines={}, dual_indicator={"direction_verdict": "主副同向", "hard_conflict": True},
        final_verdict={"state": "NO-GO", "executable": False, "reason": "dual_indicator"},
    )
    assert "主副同向" not in card
    assert "主副强冲突" in card
    assert "损98" not in card and "标105" not in card


def test_v96_non_crypto_card_does_not_show_crypto_flow_fields():
    render = _load(ROOT / "scripts" / "render_v96.py", "render_v96_non_crypto")
    card = render.render_v96_card(
        "XAUUSD", "WAIT", "neutral", 100, 110, 90, 0, "", "N/A", "C", "buy", "1.2",
        "0.01%", "纽约", {}, "—", [], False,
        {}, {}, 0, 0, "", "", risk_amt=1, leverage_text="", inv_line="—",
        prot_status="C", data_grade="B", sweep_state="", displacement="", one_reason="",
        model_id="model", n5=0, eng_conf=0, dual_indicator={"asset_is_crypto": False},
        final_verdict={"state": "WAIT", "executable": False},
    )
    assert "Funding" not in card and "Taker" not in card and "恐贪" not in card


def test_v96_card_renders_source_status_and_final_verdict_usage():
    render = _load(ROOT / "scripts" / "render_v96.py", "render_v96_source_matrix")
    card = render.render_v96_card(
        "BTCUSDT", "WAIT", "neutral", 100, 110, 90, 0, "", "买", "A", "买", 1.1,
        "0.01%", "纽约", {}, "25", [], False,
        {}, {}, 0, 0, "", "", risk_amt=1, leverage_text="", inv_line="—",
        prot_status="C", data_grade="B", sweep_state="", displacement="", one_reason="",
        model_id="model", n5=0, eng_conf=0, klines={},
        source_matrix=[
            {"label": "TV五周期", "status": "live", "entered_final_verdict": True, "impact": "五层硬闸", "evidence": "覆盖5/5"},
            {"label": "X情绪", "status": "stale_cache", "entered_final_verdict": False, "impact": "催化剂盲点", "evidence": "过期"},
        ],
        final_verdict={"state": "WAIT", "executable": False},
    )

    assert "③ 多源验证 / 双指标" in card
    assert "TV五周期" in card and "live" in card
    assert "X情绪" in card and "stale_cache" in card
    assert "已入FinalVerdict" in card
    assert "仅展示/辅助" in card


def test_push_card_shows_compact_source_status_summary():
    render = _load(ROOT / "scripts" / "render_tv_card.py", "render_tv_card_source_summary")
    card = render.render_tv_card(
        {
            "grade": "C等待",
            "_source_matrix": [
                {"label": "TV五周期", "status": "live", "entered_final_verdict": True},
                {"label": "X情绪", "status": "stale_cache", "entered_final_verdict": False},
            ],
        },
        {"signal": "等待"}, "BTCUSDT", 100, mode="push",
    )

    assert "数据状态：TV五周期:live·裁决 / X情绪:stale_cache·辅助" in card


def test_push_card_uses_narrow_blocks_and_clean_table_boundaries():
    render = _load(RENDER, "render_tv_card_layout_contract")
    card = render.render_tv_card(
        {"grade": "C等待", "_final_verdict": {"state": "WAIT", "executable": False}},
        {"signal": "等待确认", "oi": "持平", "cvd_flow": "中性", "volume": "缩量"},
        "BTCUSDT", 100, mode="push",
    )
    lines = card.splitlines()
    tables = [i for i in range(len(lines) - 1)
              if lines[i].startswith("|") and lines[i + 1].startswith("|")
              and "---" in lines[i + 1]]
    assert len(tables) == 2
    for i in tables:
        assert i > 0 and lines[i - 1] == ""
        assert len(lines[i].split("|")) - 2 <= 3
    assert "【" not in card and "】" not in card


def test_inconsistent_go_a_side_and_geometry_never_render_as_execution():
    render = _load(RENDER, "render_tv_card_inconsistent_final")
    card = render.render_tv_card(
        {
            "grade": "A多", "entry": 100, "stop": 98, "target": 105,
            "_final_verdict": {
                "state": "GO-A", "executable": True, "grade": "A多",
                "side": "short", "entry": 100, "stop": 98, "target": 105,
            },
        },
        {"signal": "支持"}, "BTCUSDT", 100, mode="push",
    )
    assert "⭐主推 多" not in card
    assert "⭐主推 空" not in card
    assert "等待确认" in card
def test_a07_preserves_complete_prices_percentages_negation_and_source_status():
    render = _load(RENDER, "render_a07_complete_text")
    for text in ("回踩 64,321.25 未站稳不可做多", "新空持续增加但未确认 -0.05%", "HALDRO/AggVolume:live_not_confirmed"):
        assert render._clean_text(text, 12) == text
    card = render.render_tv_card(
        {"_source_matrix": [
            {"label": "HALDRO/AggVolume", "status": "live_not_confirmed"},
            {"label": "外部衍生品覆盖", "status": "stale_cache_not_executable"},
        ]},
        {"oi": "新空持续增加但未确认 -0.05%"}, "BTCUSDT", 100,
    )
    assert "新空持续增加但未确认 -0.05%" in card
    assert "HALDRO/AggVolume:live_not_confirmed" in card
    assert "stale_cache_not_executable" in card


def test_a07_missing_and_inherited_timeframes_are_explicit():
    render = _load(RENDER, "render_a07_timeframes")
    empty = render._tf_mini({})
    assert empty == "D未取 · 4h未取 · 1h未取 · 15m未取 · 5m未取"
    line = render._tf_mini({"_klines": {
        "1D": {"description": "偏空"},
        "4h": {"description": "偏多", "inherited": True, "timestamp": "2026-09-05 12:00"},
        "1h": {"description": "偏空", "inherited": True},
        "15m": {"description": "未收线"},
    }})
    assert "D🔴" in line
    assert "4h🟢继承2026-09-05 12:00" in line
    assert "1h🔴继承时间未提供" in line
    assert "5m未取" in line
