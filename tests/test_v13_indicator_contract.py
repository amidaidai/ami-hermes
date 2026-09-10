#!/usr/bin/env python3
"""v13 双指标接口契约测试。

关键：解码器的期望值来自 2026-09-10 在 BINANCE:BTCUSDT.P 上实读到的
Data Window 真值，不是自造的样例 —— 保证解码与指标源码一致。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tv_indicator_contract as C


# ── 真实样本（2026-09-10 实读 BINANCE:BTCUSDT.P 15m）────────────────
LIVE = {
    "MCP Side Code": -1,
    "MCP Grade Code": 2,
    "MCP Setup Score": 4,
    "MCP Entry Valid Code": -2,
    "MCP NoTrade Reason Code": 1976,
    "MCP Execution Pack": 1801,
    "MCP Quality Code": 2,
    "MCP StructPack": -9879,
    "HALDRO State Pack": 3,
    "HALDRO Valid Code": 2,
    "HALDRO Contract Pack": 22002,
    "OI Agreement %": 75,
    "Coverage Exchanges": 5,
}
LIVE_RISK_ROW = "风控·观察 | 入79056.6·止80482.8·1.8A·标76151.9·2.0R"


def test_main_rows_match_v13_panel():
    assert C.MAIN_ROW_LABELS == [
        "位置", "结论", "方向", "路径", "风控", "CVD", "OI",
        "协同", "结构", "磁吸↑", "磁吸↓", "前位", "现位",
    ]
    assert len(C.MAIN_ROW_LABELS) == 13


def test_sub_rows_match_v13_panel():
    assert C.SUB_ROW_LABELS == ["信号", "结论", "流向", "持仓", "量能", "操作"]
    assert len(C.SUB_ROW_LABELS) == 6


def test_no_trade_reason_decodes_live_1976():
    """1976 = 8+16+32+128+256+512+1024（实盘 BTCUSDT 未接总线时的真值）。"""
    reasons = C.decode_no_trade(1976)
    assert reasons == [
        "价格几何不成立", "R:R不足", "CVD质量不达标",
        "溢折价不允许", "本根未收线", "触发不新鲜", "副指标冲突/降权",
    ]
    assert sum(1 for b in C.NO_TRADE_BITS if 1976 & b) == 7


def test_no_trade_reason_bit_boundaries():
    assert C.decode_no_trade(0) == []
    assert C.decode_no_trade(None) == []
    assert C.decode_no_trade("") == []
    assert C.decode_no_trade(1) == ["HTF冲突X"]
    assert C.decode_no_trade(1024) == ["副指标冲突/降权"]
    assert C.decode_no_trade(2047) == list(C.NO_TRADE_BITS.values())
    assert C.format_no_trade(1976) == "价格几何不成立+R:R不足+CVD质量不达标+溢折价不允许+本根未收线+触发不新鲜+副指标冲突/降权"
    assert C.format_no_trade(0) == ""


def test_entry_valid_codes():
    assert C.decode_entry_valid(LIVE["MCP Entry Valid Code"]) == "价格几何不成立"
    assert C.decode_entry_valid(3) == "可执行(A)"
    assert C.decode_entry_valid(2) == "可执行(B/C)"
    assert C.decode_entry_valid(-3) == "X禁做"
    assert C.decode_entry_valid(None) == "缺失"
    assert C.decode_entry_valid(99) == "未知"


def test_haldro_state_codes():
    assert C.decode_haldro_state(LIVE["HALDRO State Pack"]) == "S3冲突"
    assert C.decode_haldro_state(0) == "S0未接/无效"
    assert C.decode_haldro_state(1) == "S1支持多"
    assert C.decode_haldro_state(2) == "S2支持空"
    assert C.decode_haldro_state(4) == "S4降权"


def test_execution_pack_cross_validates_own_decoders():
    """Execution Pack 1801 应自洽地解出：几何0 / 未收线 / 止损1.80ATR / 入场码-2。
    这条同时校验 Execution Pack 与 Entry Valid Code 两个解码器。"""
    pack = LIVE["MCP Execution Pack"]
    geom = (pack // 1_000_000) % 10
    confirmed = (pack // 100_000) % 10
    stop_atr = (pack // 10) % 10_000
    entry_code = pack % 10 - 3
    assert (geom, confirmed, stop_atr, entry_code) == (0, 0, 180, -2)
    assert entry_code == LIVE["MCP Entry Valid Code"]
    assert C.decode_entry_valid(entry_code) == "价格几何不成立"
    # 未收线在 NoTrade 掩码里也必须置位
    assert "本根未收线" in C.decode_no_trade(LIVE["MCP NoTrade Reason Code"])


def test_rr_gate_alignment():
    assert "过硬闸" in C.rr_gate(2.0)
    assert "过硬闸" in C.rr_gate(3.4)
    assert "仅B/C直通" in C.rr_gate(1.5)
    assert "不足" in C.rr_gate(1.2)
    assert C.rr_gate(None) == "R:R缺失"
    assert C.RR_HARD_MIN == 2.0 and C.RR_BC_MIN == 1.5


def test_parse_risk_row_live_sample():
    """v13 把 入场/止损/目标/R:R 折进「风控」行，解析必须吃得住真实的观察态写法。"""
    got = C.parse_risk_row(LIVE_RISK_ROW)
    assert got["label"] == "风控·观察"
    assert got["entry"] == 79056.6
    assert got["stop"] == 80482.8
    assert got["target"] == 76151.9
    assert got["stop_atr"] == 1.8
    assert got["rr"] == 2.0
    # 只传右侧值也要能解析
    assert C.parse_risk_row(LIVE_RISK_ROW.split(" | ", 1)[1])["entry"] == 79056.6


def test_parse_risk_row_variants():
    banned = C.parse_risk_row("禁做·不出价")
    assert banned["label"] == "禁做·不出价"
    assert banned["entry"] is None and banned["rr"] is None

    stop_only = C.parse_risk_row("止80482.8·1.8A")
    assert stop_only["stop"] == 80482.8 and stop_only["entry"] is None

    plain = C.parse_risk_row("风控")
    assert plain["label"] == "风控" and plain["entry"] is None

    assert C.parse_risk_row("")["label"] == ""
    # 千分位与负号
    big = C.parse_risk_row("风控 | 入79,056.6·止80482.8")
    assert big["entry"] == 79056.6


def test_dw_names_match_indicator_source():
    """DW 名必须与两份 v13 源码里的 plot(title=) 完全一致（含中文后缀）。"""
    assert "MCP CVD Method Code (0=不参与决策,2=lower-TF estimate,1=bar estimate)" in C.DW_MAIN
    assert "MCP NoTrade Reason Code" in C.DW_MAIN
    assert "MCP RR Ratio" in C.DW_MAIN
    assert "MCP Entry Valid Code" in C.DW_MAIN
    assert "MCP Trigger Pack" in C.DW_MAIN
    assert "MCP Contract Pack" in C.DW_MAIN
    assert "Basic Packed Bus (唯一主副连接)" in C.DW_SUB
    assert "HALDRO State Pack (0无效/1支持多/2支持空/3冲突/4降权)" in C.DW_SUB
    assert "CVD Method Code (1=当前所K线方向/2=当前所1m方向)" in C.DW_SUB
    assert "CVD Value" in C.DW_SUB
    # 已废止的不得出现在权威清单里
    for dead in ("MCP CVD Value", "OI Total", "Estimated CVD Value", "MCP EMA Length 1"):
        assert dead not in C.DW_MAIN and dead not in C.DW_SUB


def test_alias_maps_cover_all_new_fields():
    for key, name in C.DW_ALIASES_MAIN.items():
        assert name in C.DW_MAIN, f"{key} -> {name} 不在 v13 主指标 DW 清单内"
    # 副指标别名允许带旧名兜底，但 v13 权威名必须都在
    v13_sub_aliases = {k: v for k, v in C.DW_ALIASES_SUB.items()}
    for key, name in v13_sub_aliases.items():
        assert name in C.DW_SUB, f"{key} -> {name} 不在 v13 副指标 DW 清单内"
    for key in ("mcp_rr_ratio", "mcp_no_trade_reason_code", "mcp_entry_valid_code"):
        assert key in C.DW_ALIASES_MAIN
    for key in ("haldro_state_pack", "basic_packed_bus", "oi_breadth"):
        assert key in C.DW_ALIASES_SUB


def test_new_in_v13_is_actually_new_and_documented():
    assert len(C.NEW_IN_V13) >= 18
    assert "MCP RR Ratio" in C.NEW_IN_V13
    assert "MCP NoTrade Reason Code" in C.NEW_IN_V13
    # 每个新增字段都必须能在权威清单里找到
    for name in C.NEW_IN_V13:
        assert name in C.DW_MAIN or name in C.DW_SUB, name


def test_legacy_rows_kept_for_backcompat():
    assert "进场" in C.LEGACY_MAIN_ROWS and "止损" in C.LEGACY_MAIN_ROWS
    assert "风险" in C.LEGACY_SUB_ROWS and "爆仓" in C.LEGACY_SUB_ROWS
    assert set(C.SYNTH_ROWS) == {"等级", "处理"}
    assert C.CONTRACT_VERSION in ("v13", "v14"), "版本升级时此处需同步放宽"
