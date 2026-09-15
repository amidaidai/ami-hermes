# -*- coding: utf-8 -*-
"""PLAN-B「人工方案」必须真的出现在卡面上，而不是只躺在裁决字段里。

背景：影子账本 2026-07-10→09-15 共 454 个信号，GO-A 出现 0 次，B 级占 58%，
全部折成 WAIT/禁做 —— 用户只看到「永远不给出方案」。修完 decision_loop 之后，
必须把方案一路送到两层渲染（原生卡 + card_reformat v7），否则等于没修。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_v96 import render_v96_card  # noqa: E402
from card_reformat import parse, render_tables  # noqa: E402

PLAN = {
    "side": "long",
    "grade": "B多",
    "model_id": "fvg_pullback",
    "authorized": False,
    "label": "人工方案·非授权",
    "entry_zone": [77130.0, 77350.0],
    "invalidation": 76629.0,
    "target_zone": [78041.0, 78261.0],
    "rr": 1.8,
    "upgrade_prereqs": ("b_wait", "haldro_invalid"),
    "note": "结构成立+方向明确，缺辅证确认；需人工判断，系统不授权执行。",
}

BASE_FV = {
    "state": "PLAN-B", "executable": False, "side": "neutral", "grade": "B多",
    "reason": "等待：b_wait/haldro_invalid", "entry": None, "stop": None, "target": None,
    "plan": PLAN, "plan_reason": "人工方案·非授权 — 结构成立+方向明确，缺辅证确认",
}


def _card(final_verdict):
    return render_v96_card(
        symbol="BTCUSDT", status="NO-GO", direction="wait", price=77263.0,
        high=79570.9, low=77130.0, chg=-0.54, tf_lines="", cvd_dir="卖", cvd_quality="A",
        taker_dir="", taker_ratio=1.08, funding_rate="0.0074%", kill_zone="伦敦",
        vwap_ema={}, fg_v="69",
        levels=[{"level": 77364.0, "kind": "1h·VAL"}, {"level": 76629.0, "kind": "4h·VAL"}],
        bearish=False, st_a={}, st_b={}, rr_a=0.9, rr_b=1.8, rr_a_note="", rr_b_note="",
        risk_amt=0, leverage_text="Binance 100x", inv_line="—", prot_status="通过",
        data_grade="A", sweep_state="", displacement="", one_reason="", model_id="fvg_pullback",
        n5=3, eng_conf=0.3, klines={},
        dual_indicator={"usable": True, "asset_is_crypto": True},
        final_verdict=final_verdict, source_matrix=[],
    )


def test_native_card_renders_manual_plan_block():
    card = _card(BASE_FV)
    assert "## 人工方案（非授权·需人工确认）" in card
    assert "77,130–77,350" in card, card
    assert "76,629" in card
    assert "78,041–78,261" in card
    assert "1:1.8" in card
    # 非授权这件事必须写在标题上，不能被读成可下单卡
    assert "非授权" in card


def test_native_card_omits_plan_block_without_plan():
    card = _card({"state": "WAIT", "executable": False, "reason": "等待", "plan": None})
    assert "人工方案" not in card


def test_v7_tables_carry_the_plan_and_flip_the_summary(tmp_path):
    native = tmp_path / "card.md"
    native.write_text(_card(BASE_FV), encoding="utf-8")
    out = render_tables(native)
    assert "**④ 人工方案（非授权·需人工确认）**" in out
    assert "77,130" in out and "76,629" in out
    # 有方案时不能再说「当前不给入场价」——那是自相矛盾
    assert "当前不给入场价" not in out
    assert "升级前置" in out


def test_v7_tables_unchanged_without_plan(tmp_path):
    native = tmp_path / "card.md"
    native.write_text(
        _card({"state": "WAIT", "executable": False, "reason": "等待：b_wait", "plan": None}),
        encoding="utf-8",
    )
    out = render_tables(native)
    assert "人工方案" not in out
    # 旧版式在无方案时必须原样保留提醒
    assert "当前不给入场价" in out


def test_parse_extracts_plan_rows(tmp_path):
    native = tmp_path / "card.md"
    native.write_text(_card(BASE_FV), encoding="utf-8")
    d = parse(native)
    assert d["manual_plan"], d.get("manual_plan")
    assert len(d["manual_plan"][0]) >= 5
    assert "haldro_invalid" in d["manual_plan_prereq"]


FV_WITH_GROUPS = dict(BASE_FV, primary_blocker="haldro_invalid",
                      blocker_groups=(("副指标未确认", ("haldro_invalid",)),
                                      ("未获执行授权", ("b_wait",))))


def test_primary_blocker_is_rendered_in_both_layers(tmp_path):
    """拦因归并：主因要单列出来，而不是让用户从一串符号里自己拼。"""
    card = _card(FV_WITH_GROUPS)
    assert "主因 haldro_invalid（副指标未确认）" in card
    # 「N 类 / M 条」—— 让塌缩看得见，而不是甩一个被同义门灌水的总数
    assert "2 类 / 2 条拦因" in card
    native = tmp_path / "card.md"
    native.write_text(card, encoding="utf-8")
    out = render_tables(native)
    assert "主因：haldro_invalid（副指标未确认）" in out


def test_no_primary_blocker_line_when_absent(tmp_path):
    card = _card(BASE_FV)
    assert "主因 " not in card
