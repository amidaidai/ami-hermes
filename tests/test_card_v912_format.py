# -*- coding: utf-8 -*-
"""v9.12 分析卡格式契约（2026-09-14 用户批准「按建议推进」）。

本次改版把完整卡从 120 行压到 ≤40 行，规则三条：
1. 并簇：相邻 <0.15% 的结构位合成一个区间（77,847+77,865 → 77,847–77,865 阻力簇）；
2. 角色制：② 只回答「上面卡哪 / 中间看什么 / 下面废哪」——≤4 行，其余下沉「远端」注脚；
3. 去重与上限：删掉与 ②/④ 重复的【现在】【做法】表；每张表 ≤3 列；全卡 ≤40 行。

截图负责结构，文字负责决策 —— 本文件把这些规则钉成回归测试。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_v96 import (  # noqa: E402
    _cluster_levels,
    _level_role_rows,
    _source_footer,
    render_v96_card,
)

PRICE = 77668.0

# 2026-09-14 实测（BTC 15m 行动格 + TV 结构位标签）
REAL_BANDS_INPUT = [
    {"level": 77864.7, "kind": "15m·阻"},
    {"level": 77847.4, "kind": "1h·VAH"},
    {"level": 77597.85, "kind": "15m·POC"},
    {"level": 77576.2, "kind": "1h·POC"},
    {"level": 77348.0, "kind": "1h·VWAP"},
    {"level": 77346.0, "kind": "5m·VWAP"},
    {"level": 77275.0, "kind": "D·VAH"},
]

KLINES = {
    "D": {"description": "转多·CHoCH↑·等BOS·趋势·", "cvd": {"direction": "买", "value": 2659016}},
    "4h": {"description": "转多·CHoCH↑·等BOS·平衡·", "cvd": {"direction": "卖", "value": -10432}},
    "1h": {"description": "空趋势·BOS↓·守摆高·平衡·看V", "cvd": {"direction": "买", "value": 10717}},
    "15m": {"description": "转多·CHoCH↑·等BOS·平衡·", "cvd": {"direction": "买", "value": 492}},
    "5m": {"description": "多趋势·BOS↑·守摆低·平衡·看V", "cvd": {"direction": "买", "value": 156}},
}


def _card(final_verdict=None, levels=None, source_matrix=None):
    return render_v96_card(
        symbol="BTCUSDT", status="NO-GO", direction="wait", price=PRICE,
        high=77864.7, low=76350.1, chg=0.73, tf_lines="", cvd_dir="买", cvd_quality="A",
        taker_dir="", taker_ratio=0.93, funding_rate="0.0087%", kill_zone="伦敦",
        vwap_ema={}, fg_v="57", levels=list(levels if levels is not None else REAL_BANDS_INPUT),
        bearish=False, st_a={}, st_b={}, rr_a=0.5, rr_b=3.4, rr_a_note="", rr_b_note="",
        risk_amt=0, leverage_text="Binance 100x", inv_line="—", prot_status="通过",
        data_grade="A", sweep_state="", displacement="", one_reason="", model_id="m",
        n5=1, eng_conf=0, klines=KLINES,
        dual_indicator={"usable": True, "asset_is_crypto": True},
        final_verdict=final_verdict if final_verdict is not None else {
            "state": "NO-GO", "executable": False, "reason": "haldro_state_conflict"},
        source_matrix=source_matrix or [],
    )


# ── 规则 1：并簇 ────────────────────────────────────────────────────────

def test_adjacent_levels_merge_into_bands():
    bands = _cluster_levels(list(REAL_BANDS_INPUT), PRICE)
    texts = [b["price_txt"] for b in bands]
    assert texts == ["77,576–77,598", "77,847–77,865", "77,275–77,348"], texts
    # 相距 <0.15% 的位必须落进同一个带（77,346/77,348 与 77,576/77,598）
    assert all("~" not in t or "–" in t for t in texts)


def test_band_distance_range_is_ordered():
    bands = _cluster_levels(list(REAL_BANDS_INPUT), PRICE)
    by_text = {b["price_txt"]: b for b in bands}
    assert by_text["77,847–77,865"]["dist_txt"] == "+0.23%~+0.25%"
    assert by_text["77,576–77,598"]["dist_txt"] == "-0.09%~-0.12%"


def test_price_inside_band_is_shown_first():
    """现价落在带内时该带不得消失，且距离按升序展示。"""
    levels = [
        {"level": 77000.0, "kind": "15m·VAL"},
        {"level": 77200.0, "kind": "15m·POC"},
        {"level": 77300.0, "kind": "15m·VAH"},
        {"level": 78000.0, "kind": "D·VAH"},
    ]
    bands = _cluster_levels(levels, 77250.0)
    roles, _rest = _level_role_rows(bands, 77250.0)
    assert roles and roles[0]["role"] == "⚖ 现价所在带", roles
    dist = roles[0]["band"]["dist_txt"]
    lo, hi = [float(x.replace("%", "")) for x in dist.split("~")]
    assert lo < hi, dist


# ── 规则 2：角色制 ──────────────────────────────────────────────────────

def test_role_rows_answer_three_questions_only():
    bands = _cluster_levels(list(REAL_BANDS_INPUT), PRICE)
    roles, rest = _level_role_rows(bands, PRICE)
    assert len(roles) <= 4
    labels = [r["role"] for r in roles]
    assert labels[0] == "🔴 上沿阻力簇"
    assert "🟢 主观察" in labels
    assert roles[0]["band"]["price_txt"] == "77,847–77,865"
    assert rest == []  # 三个带全部落到角色行


def test_rest_levels_go_to_far_note_not_dropped():
    levels = list(REAL_BANDS_INPUT) + [
        {"level": 76350.1, "kind": "24h·低"},
        {"level": 78042.7, "kind": "D·VAH"},
    ]
    card = _card(levels=levels)
    assert "远端：" in card
    far = [ln for ln in card.splitlines() if ln.startswith("远端：")][0]
    assert "78,043" in far or "76,350" in far, far


# ── 规则 3：去重、列数与行数上限 ────────────────────────────────────────

def test_card_has_no_duplicate_structure_or_action_tables():
    card = _card()
    assert "【现在】" not in card and "【做法】" not in card
    assert "| 维度 | 内容 |" not in card
    assert "| 结构位 | 价格 | 用法 | 距现价 |" not in card
    assert "| 周期 | SVP主指标 | HALDRO副指标 | 位置 |" not in card


def test_every_table_has_at_most_three_columns_and_no_fullwidth_pipe():
    card = _card()
    lines = card.splitlines()
    headers = [i for i in range(len(lines) - 1)
               if lines[i].startswith("|") and set(lines[i + 1]) <= set("|:- ")]
    assert headers, "卡面应至少有 ① 之外的三张表"
    for i in headers:
        cols = len(lines[i].split("|")) - 2
        assert cols <= 3, f"表列数超限({cols}): {lines[i]}"
    assert "｜" not in card


def test_full_card_body_within_line_budget():
    for card in (_card(), _card(final_verdict={"state": "WAIT", "executable": False})):
        body = card.rstrip("\n").splitlines()
        assert len(body) <= 40, f"完整卡超行数上限: {len(body)} 行"


def test_health_strip_keeps_five_timeframes_and_main_marker():
    card = _card()
    strip = [ln for ln in card.splitlines() if ln.startswith("① 周期体温")][0]
    for tf in ("D", "4h", "1h", "15m", "5m"):
        assert tf in strip, strip
    assert "15m⭐" in strip, strip
    assert "| " not in strip  # 体温条是行，不再是宽四列表


def test_source_footer_groups_verdict_and_aux_sources():
    footer = _source_footer([
        {"label": "TV五周期", "status": "live", "entered_final_verdict": True},
        {"label": "X情绪", "status": "stale_cache", "entered_final_verdict": False},
    ])
    assert "已入FinalVerdict：TV五周期 live" in footer
    assert "仅展示/辅助：X情绪 stale_cache" in footer
    assert "｜" not in footer
