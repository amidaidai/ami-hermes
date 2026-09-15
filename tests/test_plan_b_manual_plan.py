"""PLAN-B（人工方案·非授权）不变量。

背景（2026-09-15 用户反馈 + 影子账本审计）：两个月 454 个信号里 GO-A 出现 0 次，
B 级（占 58%）被 P0-1 一律折成 WAIT/禁做，用户只看到「永远不给出方案」。这个
用例把「不能自动执行」与「不能给方案」的边界钉死：

1. B 级结构成立 + 三件套几何有效 + R:R≥1.5 + 无硬门 → PLAN-B，必须给出方案；
2. 方案只存在于 plan 字段，entry/stop/target 必须保持 None（物理上不可能被当
   成授权订单）；
3. 任何硬门 → 仍 NO-GO，连方案都不出；
4. R:R < 1.5 → 不进 PLAN-B；
5. GO-A 语义完全不变；C反 比 B 更弱，不进 PLAN-B。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision_loop import (  # noqa: E402
    BLOCKER_FAMILIES, PLAN_B_MIN_RR, _FAMILY_ORDER, resolve_final_verdict,
)
from decision_regime import classify_decision_regime


def _trend():
    return classify_decision_regime(
        adx=30, atr_ratio=1.0, ema_spread_atr=0.7,
        vwap_crosses_20=1, va_stay_ratio_20=0.2,
        displacement_atr=0.8, rvol=1.1,
    )


def _main(**overrides):
    data = {
        "grade": "B多", "direction": "long", "model_id": "fvg_pullback",
        "entry": 100.0, "stop": 98.0, "target": 105.0, "rr": 2.5,
        "mcp_fvg_quality_score": 82.0, "mcp_ob_quality_score": 70.0,
        "data_grade": "A", "snapshot_age_sec": 10.0,
        "location_valid": True, "trigger_confirmed": True, "bar_closed": True,
    }
    data.update(overrides)
    return data


def _dual(valid_code=2, conflict=False, **overrides):
    data = {
        "asset_is_crypto": True, "valid_code": valid_code, "conflict": conflict,
        "aligned": not conflict, "risk_code": 0,
    }
    data.update(overrides)
    return data


def test_b_grade_structure_yields_manual_plan_not_silence():
    out = resolve_final_verdict("BTCUSDT", _main(), _dual(), regime=_trend())
    assert out.state == "PLAN-B"
    assert out.plan is not None
    assert out.plan["authorized"] is False
    assert out.plan["side"] == "long"
    assert out.plan["label"] == "人工方案·非授权"
    assert len(out.plan["entry_zone"]) == 2
    assert len(out.plan["target_zone"]) == 2
    assert out.plan["invalidation"] == 98.0
    assert out.plan["rr"] >= PLAN_B_MIN_RR


def test_plan_never_leaks_into_execution_fields():
    out = resolve_final_verdict("BTCUSDT", _main(), _dual(), regime=_trend())
    assert out.executable is False
    assert out.side == "neutral"
    assert out.entry is None and out.stop is None and out.target is None
    # 方案价只能走 plan，且不得等于任何执行字段
    assert out.plan["entry_zone"][0] > 0
    assert out.plan["target_zone"][0] > 0


def test_plan_keeps_authority_blocker_recorded():
    out = resolve_final_verdict("BTCUSDT", _main(), _dual(), regime=_trend())
    # 不授权这件事必须留在证据层，方案不许把它洗掉
    assert "b_wait" in out.blockers
    assert out.primary_blocker
    assert out.blocker_groups


def test_hard_blocker_still_no_go_and_no_plan():
    out = resolve_final_verdict("BTCUSDT", _main(), _dual(2, True), regime=_trend())
    assert out.state == "NO-GO"
    assert out.plan is None
    assert out.entry is None
    assert "dual_indicator" in out.blockers


def test_rr_below_plan_floor_is_not_a_plan():
    out = resolve_final_verdict(
        "BTCUSDT", _main(entry=100.0, stop=98.0, target=102.0), _dual(), regime=_trend()
    )
    assert out.state == "WAIT"
    assert out.plan is None
    assert "rr_ratio" in out.blockers


def test_incomplete_geometry_is_not_a_plan():
    out = resolve_final_verdict("BTCUSDT", _main(stop=None), _dual(), regime=_trend())
    assert out.plan is None
    assert out.state != "PLAN-B"


def test_go_a_semantics_unchanged_and_carries_no_plan():
    out = resolve_final_verdict(
        "BTCUSDT", _main(grade="A多"), _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}},
    )
    assert out.state == "GO-A"
    assert out.executable is True
    assert out.entry == 100.0 and out.stop == 98.0 and out.target == 105.0
    assert out.plan is None
    assert out.plan_reason == ""


def test_c_reversal_is_weaker_than_b_and_gets_no_plan():
    out = resolve_final_verdict("BTCUSDT", _main(grade="C反多"), _dual(), regime=_trend())
    assert out.state == "WAIT"
    assert out.plan is None


def test_plan_b_min_rr_is_below_authorization_floor():
    # 授权硬线 1:2，人工方案线 1:1.5 —— 两者必须分离，否则 B 级永远无解。
    assert PLAN_B_MIN_RR == 1.5


def test_blocker_families_have_no_duplicates_and_cover_every_group():
    """家族清单重复会把「共 N 条拦因」算多（曾把 exhaustion_chase 写两遍）。"""
    for code, label, sev, members in BLOCKER_FAMILIES:
        assert len(members) == len(set(members)), f"{code} 家族有重复项"
        assert sev in ("hard", "soft"), f"{code} 严重度非法"
        assert label
    assert len({c for c, *_ in BLOCKER_FAMILIES}) == len(BLOCKER_FAMILIES)
    # 每个家族都要能被排序表覆盖，否则会出现只在 fallback 里露面的家族
    known = {c for c, *_ in BLOCKER_FAMILIES}
    assert known <= set(_FAMILY_ORDER)


def test_blocker_grouping_dedupes_and_keeps_evidence():
    from decision_loop import _blocker_groups
    primary, groups = _blocker_groups(
        ["exhaustion_chase"], ["b_wait", "haldro_invalid", "location"])
    assert primary == "exhaustion_chase", primary
    flat = [item for _label, items in groups for item in items]
    assert len(flat) == len(set(flat)), flat
    # 证据层一条都不能丢
    assert set(flat) == {"exhaustion_chase", "b_wait", "haldro_invalid", "location"}
