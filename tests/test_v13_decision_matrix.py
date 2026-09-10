#!/usr/bin/env python3
"""v13 裁决矩阵测试。

重点钉住两条铁律：
  1. 合成**永不升级** —— 副指标只能确认/降权/否决，任何组合都不得把 B/C 变成 A。
  2. 副指标强时**不能**给 A；副指标冲突时主 A 必须硬阻断。
期望值取自 2026-09-10 实盘（BINANCE:BTCUSDT.P，NoTrade=1976）。
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import decision_matrix as D

# 实盘：NoTrade 1976 = 8+16+32+128+256+512+1024
LIVE_NO_TRADE = 1976

GRADES = ["X禁做", "C等待", "", "B多", "B空", "C反多", "C反空", "A多", "A空"]


# ── 1. 解除条件 ──────────────────────────────────────────────────────

def test_release_plan_live_1976():
    plan = D.release_plan(LIVE_NO_TRADE)
    assert len(plan) == 7
    assert [p["bit"] for p in plan] == [8, 16, 32, 128, 256, 512, 1024]
    reasons = {p["bit"]: p["reason"] for p in plan}
    assert reasons[8] == "价格几何不成立"
    assert reasons[1024] == "副指标冲突/降权"
    # 临时项必须被标出来（能让用户先做能立刻做的）
    transients = {p["bit"] for p in plan if p["transient"]}
    assert transients == {256, 512, 1024}


def test_release_plan_edges():
    assert D.release_plan(0) == []
    assert D.release_plan(None) == []
    assert D.release_plan("") == []
    assert [p["bit"] for p in D.release_plan(1)] == [1]
    assert len(D.release_plan(2047)) == len(D.NO_TRADE_BITS)


def test_every_release_action_is_verifiable_not_platitude():
    """解除条件必须是可判断「现在满足了吗」的动作，不能是安慰话术。"""
    for bit, action in D.RELEASE_ACTIONS.items():
        assert action.startswith("等") or action.startswith("先修"), f"位{bit} 不是可验证条件：{action}"
    assert set(D.RELEASE_ACTIONS) == set(D.NO_TRADE_BITS)


def test_format_release_puts_transient_first():
    one_line = D.format_release(LIVE_NO_TRADE)
    assert one_line
    parts = one_line.split("；")
    assert len(parts) == 7
    # 临时项（收线/新触发/总线）排在前面
    assert "收线" in parts[0] or "触发" in parts[0] or "总线" in parts[0]
    assert D.format_release(0) == ""
    assert D.format_release(None) == ""


# ── 2. R:R 档位 ──────────────────────────────────────────────────────

def test_rr_tier_boundaries_match_indicator():
    live = D.rr_tier(2.0)
    assert live["tier"] == "A级" and live["a_ok"] and live["bc_ok"]
    assert live["value"] == 2.0
    mid = D.rr_tier(1.5)
    assert mid["tier"] == "B/C" and not mid["a_ok"] and mid["bc_ok"]
    low = D.rr_tier(1.2)
    assert low["tier"] == "不足" and not low["a_ok"] and not low["bc_ok"]
    miss = D.rr_tier(None)
    assert miss["tier"] == "缺失" and not miss["a_ok"] and not miss["bc_ok"]
    assert D.rr_tier("2.3")["a_ok"] is True          # 字符串兼容（DW 回来是字符串）
    assert D.rr_tier("1.50")["bc_ok"] is True
    assert D.rr_tier(0)["tier"] == "不足"


# ── 3. 九宫格 ────────────────────────────────────────────────────────

def test_a_plus_sub_confirm_is_executable():
    syn = D.synthesis_verdict(main_grade="A多", haldro_state=1, haldro_valid=2, rr=2.3)
    assert syn["verdict"] == "A执行" and syn["executable"] and not syn["hard_block"]
    assert syn["sub_role"] == "确认"
    assert "顺向" in syn["reason"]


def test_a_plus_sub_short_alignment():
    syn = D.synthesis_verdict(main_grade="A空", haldro_state=2, haldro_valid=2, rr=2.5)
    assert syn["verdict"] == "A执行"


def test_a_plus_sub_conflict_hard_blocks():
    syn = D.synthesis_verdict(main_grade="A多", haldro_state=3, haldro_valid=2, rr=3.0)
    assert syn["verdict"] == "不执行·副冲突"
    assert syn["executable"] is False and syn["hard_block"] is True
    assert syn["sub_role"] == "否决（硬阻断）"
    assert "硬阻断" in syn["reason"]


def test_a_plus_sub_degraded_downgrades_to_manual_candidate():
    for state in (4,):
        syn = D.synthesis_verdict(main_grade="A多", haldro_state=state, haldro_valid=2, rr=2.5)
        assert syn["verdict"] == "A降级候选"
        assert syn["executable"] is False and syn["hard_block"] is False
        assert syn["sub_role"] == "降权"


def test_a_plus_sub_unwired_degrades_and_says_so():
    """副指标未接时绝不能假装副指同意了。"""
    syn = D.synthesis_verdict(main_grade="A多", haldro_state=0, haldro_valid=0, rr=2.5)
    assert syn["verdict"] == "A降级候选" and syn["executable"] is False
    assert syn["sub_role"] == "未接/无效"
    assert "未接" in syn["reason"]

    none_state = D.synthesis_verdict(main_grade="A多", haldro_state=None, haldro_valid=None, rr=2.5)
    assert none_state["verdict"] == "A降级候选"


def test_a_plus_sub_reverse_downgrades():
    syn = D.synthesis_verdict(main_grade="A多", haldro_state=2, haldro_valid=2, rr=2.5)
    assert syn["verdict"] == "A降级候选"
    assert "反向" in syn["reason"]


def test_b_c_with_confirm_stays_manual_candidate():
    syn = D.synthesis_verdict(main_grade="B多", haldro_state=1, haldro_valid=2, rr=1.6)
    assert syn["verdict"] == "B/C人工候选"
    assert syn["executable"] is False
    assert "候选价" in syn["reason"] and "不给执行指令" in syn["reason"]


def test_x_never_executes_regardless_of_sub():
    for state in (0, 1, 2, 3, 4):
        syn = D.synthesis_verdict(main_grade="X禁做", haldro_state=state, haldro_valid=2, rr=9.9)
        assert syn["verdict"] == "X禁做"
        assert syn["executable"] is False


def test_non_crypto_sub_does_not_participate():
    syn = D.synthesis_verdict(main_grade="A多", haldro_state=3, haldro_valid=2, rr=3.0, is_crypto=False)
    assert syn["sub_role"] == "不参与（非加密）"
    assert syn["hard_block"] is False
    assert syn["verdict"] == "A执行"       # 加密副指标不得否决 XAU/外汇
    assert "非加密" in syn["reason"]


def test_no_upgrade_invariant_across_full_grid():
    """全网格扫描：合成结果的「可执行」只可能来自主指标 A，不可能被副指标造出来。"""
    checked = 0
    for grade, state in itertools.product(GRADES, [None, 0, 1, 2, 3, 4]):
        for rr in (None, 1.0, 1.5, 2.0, 3.0):
            syn = D.synthesis_verdict(main_grade=grade, haldro_state=state, haldro_valid=2, rr=rr)
            checked += 1
            base_is_a = str(grade).startswith("A")
            if syn["executable"]:
                assert base_is_a, f"{grade}/S{state}/rr{rr} 凭空变成可执行 → 违反「副指标不能升级」"
            if not base_is_a:
                assert syn["verdict"] != "A执行", f"{grade}/S{state}/rr{rr} 被升级为 A"
            # 主 X / B / C 一律不可执行
            if str(grade).startswith("X") or str(grade).startswith(("B", "C")) or not grade:
                assert syn["executable"] is False
    assert checked == len(GRADES) * 6 * 5


def test_hard_block_only_for_main_a():
    """副 S3 冲突只对主 A 构成硬阻断；本来就不是 A 的维持原级。"""
    a = D.synthesis_verdict(main_grade="A多", haldro_state=3, haldro_valid=2, rr=2.5)
    b = D.synthesis_verdict(main_grade="B多", haldro_state=3, haldro_valid=2, rr=1.6)
    assert a["hard_block"] is True
    assert b["hard_block"] is False and b["verdict"] == "B/C人工候选"


# ── 4. 卡片一行渲染 ──────────────────────────────────────────────────

def test_format_synthesis_line():
    syn = D.synthesis_verdict(main_grade="A多", haldro_state=3, haldro_valid=2, rr=2.5)
    line = D.format_synthesis(syn, release_code=LIVE_NO_TRADE)
    assert "不执行·副冲突" in line
    assert "解除：" in line
    # 可执行时不该再堆解除条件
    ok = D.synthesis_verdict(main_grade="A多", haldro_state=1, haldro_valid=2, rr=2.5)
    assert "解除：" not in D.format_synthesis(ok, release_code=LIVE_NO_TRADE)
    assert D.format_synthesis({}) == ""
    assert D.format_synthesis(None) == ""


def test_matrix_version_tagged():
    assert D.MATRIX_VERSION == "v13"
    syn = D.synthesis_verdict(main_grade="A多", haldro_state=1, haldro_valid=2, rr=2.5)
    assert syn["matrix_version"] == "v13"
