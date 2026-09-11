"""Offline renderer acceptance; all fixtures are TEST SAMPLES, not market data."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["HANGQING_NO_SEND"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pytest
from render_tv_card import render_tv_card
from render_v96 import render_v96_card


def sample_main():
    return {
        "grade": "B空", "position": "价在VA下·VWAP日·周月偏空",
        "conclusion": "B空·未收线·等收线", "direction_text": "偏空·条件6/10",
        "path": "已扫高→等MSS↓→反抽失败后复核；未收线不执行",
        "risk_label": "风控·未授权", "risk": "未收线·触发过期·不出价",
        "cvd_state": "日卖盘·卖弱·基差-0.04%", "oi_state": "新空1.80%·共识99%",
        "sync": "主B·副S4降权·高周空", "structure": "CHoCH↓·等BOS·等扫位",
        "magnet_up": "周高 79737.3·11.7A", "magnet_down": "上周低 76151.9·3.2A",
        "prev_level": "VWAP 77806.4·过期·仅背景",
        "now_level": "待·发现·不追·高点→MSS↓·21:15定",
        "no_trade_reasons": "本根未收线+触发不新鲜+副指标冲突/降权",
        "release_text": "收线后复核新触发与副指标，不满足则继续等待",
        "vwap": 77900, "vah": 79000, "val": 76000, "poc": 77500,
        "_final_verdict": {
            "state": "WAIT", "executable": False, "side": "neutral", "grade": "B空",
            "entry": None, "stop": None, "target": None, "reason": "等待：本根未收线",
        },
        "_source_matrix": [{"label": "TV", "status": "live_not_confirmed", "entered_final_verdict": True}],
    }


def sample_sub():
    return {
        "signal": "S4降权·共振2/4·缺量+HTF", "conclusion": "扩仓待确认·覆盖不足不升级",
        "cvd_flow": "日·单所1m·本锚近10K卖·净24%·滚动同向",
        "oi": "新空1.82%·同100%·滚10K", "volume": "平量x1.1·同步放量2/4",
        "operation": "不升级·等覆盖恢复与2所同向",
    }


def table_headers(card):
    lines = card.splitlines()
    return [(i, line) for i, line in enumerate(lines[:-1])
            if line.startswith("|") and lines[i + 1].startswith("|") and "---" in lines[i + 1]]


def test_light_card_keeps_main_action_chain_and_six_sub_semantics():
    main, sub = sample_main(), sample_sub()
    card = render_tv_card(main, sub, "BTCUSDT", 77000)
    assert card.count("⭐主推 等待") == 1
    assert "**B空·未收线·等收线**" in card
    for key in ("position", "direction_text", "path", "risk", "cvd_state", "oi_state", "sync", "structure", "magnet_up", "magnet_down", "prev_level", "now_level", "no_trade_reasons", "release_text"):
        assert main[key] in card, key
    for key, value in sub.items():
        assert value in card, key
    assert "SVP" in card and "AggVol" in card
    assert "当前所估算CVD≠5所主动流" in card
    assert "OI≠人数" in card and "失衡≠爆仓" in card
    assert len(table_headers(card)) == 2
    assert all(len(line.split("|")) - 2 <= 3 for _, line in table_headers(card))
    assert "| 验证 |" not in card
    assert "**下一步**：待·发现·不追·高点→MSS↓·21:15定" in card


@pytest.mark.parametrize("grade", ["B空", "C反空"])
def test_wait_candidate_only_uses_final_watch_tuple(grade):
    main = sample_main()
    main["grade"] = grade
    main.update(candidate_entry=88888, entry=88888, stop=88999, target=88777)
    main["risk"] = "入88888·止88999·1.8A·标88777·2.0R·未收线不执行"
    main["path"] = "B/C候选88888·已扫高→等MSS↓·未收线不执行"
    main["_final_verdict"].update(grade=grade, watch_side="short", watch_entry=78234,
                                   watch_stop=78634, watch_target=77434, rr=9.9)
    card = render_tv_card(main, sample_sub(), "BTCUSDT", 77000)
    assert card.count("⭐主推 等待") == 1
    assert "【人工候选，未授权】" in card
    assert "入`78,234`" in card and "止`78,634`" in card and "标`77,434`" in card
    assert "R:R 1:2.00" in card and "1:9.9" not in card
    assert all(str(price) not in card for price in (88888, 88999, 88777))
    assert "未收线不执行" in card


@pytest.mark.parametrize("grade,state", [("C等待", "WAIT"), ("X禁做", "WAIT"), ("B空", "NO-GO")])
def test_wait_or_veto_cannot_leak_raw_or_watch_order_prices(grade, state):
    main = sample_main()
    main.update(grade=grade, entry=88888, stop=88999, target=88777)
    main["risk"] = "入88888·止88999·标88777·未收线不执行"
    main["path"] = "B/C候选88888·等MSS↓·未收线不执行"
    main["_final_verdict"].update(state=state, grade=grade, watch_side="short", watch_entry=78234,
                                   watch_stop=78634, watch_target=77434)
    card = render_tv_card(main, sample_sub(), "BTCUSDT", 77000)
    assert "【人工候选，未授权】" not in card
    assert all(str(price) not in card.replace(",", "") for price in (88888, 88999, 88777, 78234, 78634, 77434))
    assert "未收线不执行" in card
    assert card.count("⭐主推") == 1
    if state == "NO-GO" or grade.startswith("X"):
        assert "⭐主推 禁做" in card


def test_partial_watch_tuple_does_not_fall_back_to_raw_candidate():
    main = sample_main()
    main.update(candidate_entry=88888, candidate_stop=88999, candidate_target=88777)
    main["_final_verdict"].update(watch_side="short", watch_entry=78234, watch_stop=78634)
    card = render_tv_card(main, {}, "BTCUSDT", 77000)
    assert "【人工候选，未授权】" not in card
    assert "候选数据不完整" in card
    assert "78234" not in card.replace(",", "") and "88888" not in card


def _full_card(final_verdict, grade="B空"):
    """完整报告卡（render_v96）与推送卡必须共享同一份候选判定。"""
    return render_v96_card(
        symbol="BTCUSDT", status=grade, direction="short", price=77000.0,
        high=77500.0, low=76500.0, chg=0.0,
        tf_lines="D偏空 · 4h偏空 · 1h偏空 · 15m偏空 · 5m待判",
        cvd_dir="卖", cvd_quality="A", taker_dir="卖", taker_ratio=1.1,
        funding_rate="0.01%", kill_zone="", vwap_ema={}, fg_v="", levels=[],
        bearish=True, st_a={"stop": 88999.0, "target": 88777.0, "rr": 2.5},
        st_b={"stop": 78634.0, "target": 77434.0, "rr": 2.0},
        rr_a=2.5, rr_b=2.0, rr_a_note="", rr_b_note="",
        risk_amt=1.0, leverage_text="", inv_line=88999.0, prot_status="通过",
        data_grade="A", sweep_state="待扫", displacement="待判", one_reason="共振",
        model_id="fvg_pullback", n5=5, eng_conf=0.9,
        klines={tf: {} for tf in ("D", "4h", "1h", "15m", "5m")},
        dual_indicator={"asset_is_crypto": True, "haldro_direction": "偏空"},
        final_verdict=final_verdict,
    )


def test_full_report_card_shows_watch_candidate_only_and_labeled_unauathorized():
    verdict = {"state": "WAIT", "executable": False, "side": "neutral", "grade": "B空",
               "entry": None, "stop": None, "target": None, "reason": "等待：b_wait",
               "watch_side": "short", "watch_entry": 78234, "watch_stop": 78634,
               "watch_target": 77434}
    card = _full_card(verdict)
    assert "人工候选（未授权）" in card
    assert "78,234" in card and "78,634" in card
    assert "1:2.00" in card
    # 原始 st_a 价（88999/88777）不得出现在 WAIT 卡面
    assert "88,999" not in card and "88,777" not in card


def test_full_report_card_never_leaks_candidate_on_hard_veto():
    verdict = {"state": "NO-GO", "executable": False, "side": "neutral", "grade": "X禁做",
               "entry": None, "stop": None, "target": None, "reason": "硬闸门：dual_indicator",
               "watch_side": "neutral", "watch_entry": None, "watch_stop": None,
               "watch_target": None}
    card = _full_card(verdict, grade="X禁做")
    assert "人工候选（未授权）" not in card
    assert "78,234" not in card and "88,999" not in card


def test_full_report_card_flags_incomplete_candidate_instead_of_guessing():
    verdict = {"state": "WAIT", "executable": False, "side": "neutral", "grade": "B空",
               "entry": None, "stop": None, "target": None, "reason": "等待：b_wait",
               "watch_side": "short", "watch_entry": 78234, "watch_stop": None,
               "watch_target": None}
    card = _full_card(verdict)
    assert "人工候选（未授权）" not in card
    assert "候选数据不完整" in card
    assert "78,234" not in card
