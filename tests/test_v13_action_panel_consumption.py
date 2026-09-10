#!/usr/bin/env python3
"""回归：v13 的 13 行主表 + 6 行副表必须完整进卡。

背景（2026-09-10 修）：auto_card 的 main_keys 硬编码为旧 10 行
（结论/方向/进场/止损/目标/确认/核对/风险/磁吸↑/磁吸↓），
而 v13 面板是 13 行（位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位）。
两版只有 4 个名字重合 → 同一份缓存里 13 行只有 4 行进卡，其余 9 行静默丢弃。
本测试用真实缓存形态把它钉死。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auto_card
import tv_indicator_contract as C

# 2026-09-10 实读 data/tv_dmi_cache.json 的真实 decision_table 键
LIVE_DECISION_TABLE = {
    "位置": "价在VA下·VWAP日·周月偏空·波80%",
    "结论": "价跌+OI升 · 新空扩仓 · ▼上级偏空",
    "方向": "观望 · 过热·耗尽",
    "路径": "失效×→过热远离",
    "风控": "禁做·不出价",
    "CVD": "日卖盘·卖弱·基差-0.04%",
    "OI": "▲新空 1.80% 共识99% ✓支持",
    "协同": "主X·副不覆盖·高周空 ⚡纽120m",
    "结构": "转空·CHoCH↓·等BOS·耗尽·等扫位·扫4/7",
    "磁吸↑": "↑周三 高 79737.3·11.7A·分46·43%",
    "磁吸↓": "↓上周 低 76151.9·3.2A·分64★HTF·53%",
    "前位": "VWAP 77806.4·过期·仍阻·↑6.9A·20:45定",
    "现位": "待·发现·不追·高点→MSS↓·21:15定",
    "信号": "🔴 S0无效·共振3/4·副源无效",
    "流向": "日·单所1m·本锚近10K卖·净24%·滚动同向",
    "持仓": "▲新空1.82%·同100%·滚10K",
    "量能": "·平量 x1.1·合0%·同步放量4/4",
    "操作": "仅作参考 · 副源无效",
}


def _tables(dt: dict):
    return auto_card._tv_cache_decision_tables(
        {"decision_table": dt}, grade="C等待", treatment="?")


def _rows(tables, name):
    for t in tables:
        if t["name"] == name:
            return [r.split(" | ", 1)[0] for r in t["tables"][0]["rows"]]
    return []


def test_all_13_main_rows_reach_the_card():
    rows = _rows(_tables(LIVE_DECISION_TABLE), "SVP+ICT+VWAP+CVD")
    for label in C.MAIN_ROW_LABELS:
        assert label in rows, f"主表漏行：{label}（现有 {rows}）"


def test_all_6_sub_rows_reach_the_card():
    rows = _rows(_tables(LIVE_DECISION_TABLE), "Volume Aggregated")
    for label in C.SUB_ROW_LABELS:
        assert label in rows, f"副表漏行：{label}（现有 {rows}）"


def test_regression_old_hardcoded_keys_would_have_dropped_nine_rows():
    """把旧硬编码名单拿来对比，证明修复前的损失是真实存在的（防止有人改回去）。"""
    old_main = ["结论", "方向", "进场", "止损", "目标", "确认", "核对", "风险", "磁吸↑", "磁吸↓"]
    old_hit = {k for k in old_main if k in LIVE_DECISION_TABLE}
    new_hit = {k for k in C.MAIN_ROW_LABELS if k in LIVE_DECISION_TABLE}
    assert old_hit <= new_hit
    assert len(old_hit) == 4 and len(new_hit) == 13
    lost = new_hit - old_hit
    assert {"位置", "路径", "风控", "CVD", "OI", "协同", "结构", "前位", "现位"} == lost


def test_row_order_follows_panel_not_dict_order():
    """顺序必须跟面板一致，不能跟缓存字典的键顺序。"""
    shuffled = dict(reversed(list(LIVE_DECISION_TABLE.items())))
    rows = _rows(_tables(shuffled), "SVP+ICT+VWAP+CVD")
    body = [r for r in rows if r not in ("等级", "处理")]
    assert body == [k for k in C.MAIN_ROW_LABELS if k in shuffled]


def test_dynamic_risk_label_is_picked_up():
    """v13 风控行标签是四态的，观察态必须照样进卡。"""
    dt = dict(LIVE_DECISION_TABLE)
    dt.pop("风控")
    dt["风控·观察"] = "入79056.6·止80482.8·1.8A·标76151.9·2.0R"
    rows = _rows(_tables(dt), "SVP+ICT+VWAP+CVD")
    assert "风控·观察" in rows

    dt2 = dict(LIVE_DECISION_TABLE)
    dt2.pop("风控")
    dt2["风控·未授权"] = "止80482.8·1.8A"
    assert "风控·未授权" in _rows(_tables(dt2), "SVP+ICT+VWAP+CVD")


def test_legacy_cache_rows_still_pass_through():
    """旧缓存里残留的进场/止损/目标不能丢（向后兼容）。"""
    dt = dict(LIVE_DECISION_TABLE)
    dt["进场"] = "79056.6"
    dt["风险"] = "低覆盖"
    tables = _tables(dt)
    assert "进场" in _rows(tables, "SVP+ICT+VWAP+CVD")
    assert "风险" in _rows(tables, "Volume Aggregated")


def test_degraded_cache_does_not_raise():
    """缓存残缺时必须优雅降级，不能抛异常打断出卡。"""
    assert auto_card._tv_cache_decision_tables({}, grade="", treatment="") == []
    assert auto_card._tv_cache_decision_tables({"decision_table": None}) == []
    one = _tables({"信号": "🔴S3冲突"})
    assert _rows(one, "Volume Aggregated") == ["信号"]
