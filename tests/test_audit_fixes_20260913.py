"""2026-09-13 审计修复回归：S3 同源 / 门5·6·7·8 降级语义 / 渲染文案。

从当日实测缺陷逐条提炼（无网络、不写业务盘）：
1. S3（CVD/OI 背离）未进入 dual verdict → 门7 在 usable=True 下误显示 GREEN，
   与 decision_loop 的 haldro_state_conflict 硬阻断自相矛盾；
2. 「副指标不足」与「共振 GREEN」并存；
3. 未接持仓时暴露默认 0 → 「暴露0.0%」绿灯（缺失被显示成安全）；
4. 「样本仅0」恒假值（_reviews_count 无生产赋值）；
5. Protections 快照陈旧（2026-07-10）仍显示「全部通过」。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auto_card
from go_nogo_gate import check_gate
from shadow_calibration import shadow_sample_stats
from render_v96 import _final_dual_verdict


def _dual(**updates):
    dual = {
        "asset_is_crypto": True, "usable": True, "conflict": False,
        "hard_conflict": False, "valid_code": 2, "direction_verdict": "主副同向",
    }
    dual.update(updates)
    return dual


def _engine(**updates):
    engine = {
        "_snapshot_age_h": 0.1,
        "_banned_live": False,
        "_final_verdict": {"state": "WAIT", "executable": False,
                           "reason": "等待：haldro_state_conflict"},
        "_tv_main": {"grade": "C等待"},
        "_dual_indicator_verdict": _dual(),
        "_reviews_count": 20,
        "_wfo_efficiency": 0.72,
    }
    engine.update(updates)
    return engine


def _meta(**updates):
    meta = {"data_grade": "A", "rr_a": 2.5, "rr_b": 1.8, "protections_status": "通过"}
    meta.update(updates)
    return meta


# ── 1. S3 同源：dual verdict + 门7 ─────────────────────────────────────

def test_s3_state_flows_into_dual_and_red_gate():
    engine_tv = {"_tv_main": {"grade": "C等待", "sub_haldro_state_pack": 3,
                              "sub_composite": -1.0, "sub_confirm_score": 4,
                              "sub_coverage_exchanges": 5}}
    dual = auto_card._dual_indicator_verdict("BTCUSDT", {"status": "C等待"}, engine_tv)
    assert dual["s3_conflict"] is True, dual
    assert dual["hard_conflict"] is True, dual
    assert dual["direction_verdict"] == "副S3冲突·CVD/OI背离"

    res = check_gate("BTCUSDT", _engine(_dual_indicator_verdict=dual), _meta(status="C等待"))
    gate = res["gates"]["dual_indicator"]
    assert gate["status"] == "red", gate
    assert "dual_indicator" in res["red_gates"]
    assert "副S3" in gate["reason"], gate


def test_aligned_dual_without_s3_is_not_affected():
    engine_tv = {"_tv_main": {"grade": "A多", "sub_haldro_state_pack": 2,
                              "sub_composite": 31, "sub_confirm_score": 4,
                              "sub_coverage_exchanges": 5}}
    dual = auto_card._dual_indicator_verdict("BTCUSDT",
                                             {"status": "A多", "direction": "long"}, engine_tv)
    assert dual["hard_conflict"] is False
    assert dual["direction_verdict"] == "主副同向"

    res = check_gate("BTCUSDT", _engine(_dual_indicator_verdict=dual), _meta(status="A多"))
    assert res["gates"]["dual_indicator"]["status"] == "green"


# ── 2. 弱共振不再 GREEN ───────────────────────────────────────────────

def test_unresonated_dual_is_yellow_not_green():
    res = check_gate("BTCUSDT",
                     _engine(_dual_indicator_verdict=_dual(direction_verdict="副指标不足")),
                     _meta())
    gate = res["gates"]["dual_indicator"]
    assert gate["status"] == "yellow", gate
    assert "未共振" in gate["reason"]
    assert "dual_indicator" in res["yellow_gates"]


def test_crowded_aligned_dual_is_yellow():
    res = check_gate("BTCUSDT",
                     _engine(_dual_indicator_verdict=_dual(direction_verdict="同向但拥挤降级")),
                     _meta())
    assert res["gates"]["dual_indicator"]["status"] == "yellow"


# ── 3. 暴露未评估不冒充 0.0% ─────────────────────────────────────────

def test_missing_exposure_is_yellow_not_green_zero():
    res = check_gate("BTCUSDT", _engine(), _meta())
    gate = res["gates"]["portfolio_exposure"]
    assert gate["status"] == "yellow", gate
    assert "未评估" in gate["reason"]


def test_present_exposure_zero_keeps_legacy_green():
    res = check_gate("BTCUSDT", _engine(_total_exposure_pct=0), _meta())
    assert res["gates"]["portfolio_exposure"]["status"] == "green"


# ── 4. 样本/WFO 接真实统计 ───────────────────────────────────────────

def test_sample_gate_without_wiring_is_honest():
    res = check_gate("BTCUSDT",
                     _engine(_reviews_count=None, _wfo_efficiency=None),
                     _meta())
    gate = res["gates"]["wfo_samples"]
    assert gate["status"] == "yellow"
    assert "未接入" in gate["reason"], gate


def test_sample_gate_reports_real_shadow_numbers():
    res = check_gate("BTCUSDT",
                     _engine(_reviews_count=142, _wfo_efficiency=None,
                             _shadow_stats={"total": 157, "mature": 142, "evaluable": 0}),
                     _meta())
    gate = res["gates"]["wfo_samples"]
    assert gate["status"] == "yellow"
    assert "142" in gate["reason"] and "WFO未计算" in gate["reason"], gate
    assert "缺订单模型" in gate["reason"]


def test_shadow_sample_stats_counting(tmp_path):
    path = tmp_path / "outcomes.jsonl"
    rows = [
        {"signal_id": "a", "outcome": {"h4": {"mature": True, "filled": False,
                                              "status": "missing_order_model"}}},
        {"signal_id": "b", "outcome": {"h4": {"mature": True, "filled": True},
                                       "h16": {"mature": True, "filled": True}}},
        {"signal_id": "c"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert shadow_sample_stats(path) == {"total": 3, "mature": 2, "evaluable": 1}
    assert shadow_sample_stats(tmp_path / "missing.jsonl") == {"total": 0, "mature": 0, "evaluable": 0}


# ── 5. Protections 快照陈旧可见降级 ───────────────────────────────────

def test_stale_protections_snapshot_visible_downgrade():
    res = check_gate("BTCUSDT", _engine(),
                     _meta(protections_snapshot="2026-07-10", protections_snapshot_stale=True))
    gate = res["gates"]["protections"]
    assert gate["status"] == "yellow", gate
    assert "2026-07-10" in gate["reason"]
    assert "protections" in res["yellow_gates"]


def test_fresh_protections_snapshot_stays_green():
    res = check_gate("BTCUSDT", _engine(), _meta())
    assert res["gates"]["protections"]["status"] == "green"


# ── 6. 渲染文案 ───────────────────────────────────────────────────────

def test_render_forbidden_action_has_no_execute_verb():
    src = (ROOT / "scripts" / "render_v96.py").read_text(encoding="utf-8")
    assert '不做单' in src, "NO-GO 场景必须使用「不做单」而非「只执行禁做」"


def test_final_dual_verdict_keeps_s3_label():
    assert _final_dual_verdict(
        {"hard_conflict": True, "direction_verdict": "副S3冲突·CVD/OI背离"}, {}
    ) == "副S3冲突·CVD/OI背离"
    assert _final_dual_verdict(
        {"hard_conflict": True, "direction_verdict": "主副强冲突"}, {}
    ) == "主副强冲突"
