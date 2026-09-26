# -*- coding: utf-8 -*-
"""P0 闸门语义修复回归（2026-09-17）：

  · P0-b risk：无真实计划的参考几何不构成风控硬否决（也永不授权）；
  · P0-a stale_geometry：陈旧几何显式硬门 + 影子隔离守卫；
  · 测试隔离：pytest 下无显式 _shadow_path 不写生产影子账本（幽灵记录根因）；
  · P0-c cross_validation 降级提案已撤回（依据数据被测试夹具污染；无主源运行应 fail-closed）。

背景：GO-A 饥饿复核与当晚修正（docs/maintenance/2026-09-17-goa-starvation-recheck.md）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cross_validation import build_source_matrix, evaluate_cross_validation  # noqa: E402
from decision_loop import resolve_final_verdict  # noqa: E402
from decision_regime import classify_decision_regime  # noqa: E402
from risk_constitution_v2 import evaluate_risk  # noqa: E402
from shadow_calibration import geometry_guard  # noqa: E402


# ── P0-c：cross_validation 未运行 ≠ 冲突 ─────────────────────────────

def _crypto_engine(**over):
    engine = {
        "_binance_data_collected": True,
        "prices": {"primary": 100.0, "futures": 100.0},
    }
    engine.update(over)
    return engine


def test_hard_gate_not_run_stays_hard_fail_closed():
    """2026-09-17 复核定案：tv_main「未运行」维持硬拦（fail-closed）。

    曾拟「未运行≠冲突→降级」，但其依据数据（33 条）经查为测试夹具污染；
    且无主源运行的降级会让合成几何产出「人工方案」，已撤回。维持硬拦。
    """
    evaluation = evaluate_cross_validation(build_source_matrix(
        "BTCUSDT", _crypto_engine(),
        {"asset_is_crypto": True, "valid_code": 2, "conflict": False},
        pipeline_steps=["tv", "binance"],
    ))
    assert "tv_main" in evaluation["hard_blockers"]
    assert evaluation["state"] == "blocked"


def test_hard_gate_unavailable_still_hard_blocks():
    evaluation = evaluate_cross_validation(build_source_matrix(
        "BTCUSDT", _crypto_engine(_tv_live_status={"usable": False, "reason": "缓存过期"}),
        {"asset_is_crypto": True, "valid_code": 2, "conflict": False},
        pipeline_steps=["tv", "binance"],
    ))
    assert "tv_main" in evaluation["hard_blockers"]


# ── P0-b：参考几何不构成风控硬否决（也永不授权）──────────────────────

class _OkProtections:
    """保护规则全通过；避免用例依赖磁盘上的 protections 状态。"""

    def check_all(self, symbol, current_bar):
        return True, []


def _risk_inputs(rr: float = 0.6, **over):
    entry = 100.0
    stop = 98.0
    data = {
        "symbol": "BTCUSDT", "account_balance": 1000.0,
        "entry_price": entry, "stop_price": stop,
        "target_price": entry + (entry - stop) * rr,
        "atr": 2.0, "atr_pct": 0.02, "regime_multiplier": 1.0,
        "current_drawdown_pct": 0.0, "has_major_news": False,
        "volatility_24h_pct": 0.0, "current_bar": 0,
        "total_exposure_pct": 0.0, "corr_high": False,
        "protections": _OkProtections(),
    }
    data.update(over)
    return data


def test_reference_geometry_has_no_plan_level_violation_and_never_authorizes():
    out = evaluate_risk(_risk_inputs(0.6, plan_geometry=False))
    assert out["allowed"] is False
    assert out["plan_geometry"] is False
    assert out["violations"] == []
    assert any("参考几何" in r for r in out["reasons"])


def test_real_plan_keeps_rr_hard_veto():
    out = evaluate_risk(_risk_inputs(0.6))
    assert out["plan_geometry"] is True
    assert out["allowed"] is False
    assert any("连人工候选" in v for v in out["violations"])


# ── P0-b：decision_loop 层 —— 参考几何不硬门、不授权 ──────────────────

def _trend():
    return classify_decision_regime(
        adx=30, atr_ratio=1.0, ema_spread_atr=0.7,
        vwap_crosses_20=1, va_stay_ratio_20=0.2,
        displacement_atr=0.8, rvol=1.1,
    )


def _main(**over):
    data = {
        "grade": "A多", "direction": "long", "model_id": "fvg_pullback",
        "entry": 100.0, "stop": 98.0, "target": 105.0, "rr": 2.5,
        "mcp_fvg_quality_score": 82.0, "mcp_ob_quality_score": 70.0,
        "data_grade": "A", "snapshot_age_sec": 10.0,
        "location_valid": True, "trigger_confirmed": True, "bar_closed": True,
    }
    data.update(over)
    return data


def _dual(valid_code=2, conflict=False):
    return {"asset_is_crypto": True, "valid_code": valid_code, "conflict": conflict,
            "aligned": not conflict, "risk_code": 0}


def test_reference_geometry_risk_is_never_a_hard_gate_and_never_go_a():
    out = resolve_final_verdict(
        "BTCUSDT", _main(), _dual(), regime=_trend(),
        risk={"allowed": False, "plan_geometry": False, "violations": [], "risk_usd": 0.0},
        advanced={"gate": {"execute": True}},
    )
    assert "risk_constitution" not in out.blockers
    assert "risk_reference_geometry" in out.blockers
    assert any(w.startswith("risk_reference_geometry") for w in out.warnings)
    assert out.state == "WAIT" and out.executable is False


def test_stale_geometry_is_hard_no_go_and_clears_prices():
    out = resolve_final_verdict(
        "BTCUSDT", _main(stale_geometry=True, geometry_deviation_pct=16.1), _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}},
    )
    assert out.state == "NO-GO"
    assert "stale_geometry" in out.blockers
    assert out.entry is None and out.watch_entry is None


# ── P0-a：陈旧几何守卫（影子隔离）────────────────────────────────────

def test_geometry_guard_flags_ghost_geometry():
    deviation, stale = geometry_guard(63884.0, 76186.6)
    assert stale is True
    assert deviation is not None and 0.15 < deviation < 0.20
    deviation, stale = geometry_guard(76000.0, 76186.6)
    assert stale is False and deviation is not None and deviation < 0.01
    assert geometry_guard(0, 76186.6) == (None, False)
    assert geometry_guard(63884.0, 0) == (None, False)
    assert geometry_guard("bad", 100.0) == (None, False)


# ── P0-b 接线：几何来源必须在 setdefault 兜底之前判定（幽灵记录当晚修正）────

def _render(engine):
    import auto_card
    merged = {"bias": "偏空", "confidence_5": 3, "long_confidence": 0.2, "short_confidence": 0.62}
    meta = {"status": "B等待", "direction": "short", "model_id": "VWAP反抽", "data_grade": "A"}
    results = [{"name": "VWAP反抽", "direction": "short", "confidence": 0.7}]
    auto_card.render_card_locked("BTCUSDT", merged, results, meta, engine, grok={})
    return engine


def test_plan_geometry_flagged_only_for_real_source_geometry():
    """无 TV 三件套（price/st 兜底）→ plan_geometry=False；载荷自带三件套 → True。

    接线回归：来源标记必须采样于 setdefault 兜底之前，否则恒真、不构成拦截修复。
    """
    e1 = _render({"quality": "A", "prices": {"primary": 63884.0}, "_shadow_enabled": False})
    assert e1["_plan_geometry_from_source"] is False
    assert e1["_risk_v2"]["plan_geometry"] is False
    assert "risk_reference_geometry" in e1["_final_verdict"]["blockers"]
    e2 = _render({"quality": "A", "prices": {"primary": 63884.0}, "_shadow_enabled": False,
                  "_tv_main": {"entry": 63884.0, "stop": 64139.536, "target": 63372.928}})
    assert e2["_plan_geometry_from_source"] is True


def test_pytest_env_blocks_default_shadow_write_unless_explicit_path(monkeypatch, tmp_path):
    """测试隔离回归（幽灵记录根因）：pytest 下无显式 _shadow_path 不得写生产账本。"""
    import shadow_calibration
    calls = []
    monkeypatch.setattr(shadow_calibration, "append_shadow_signal",
                        lambda path, row: calls.append(str(path)) or True)
    _render({"quality": "A", "prices": {"primary": 63884.0}})
    assert calls == [], "pytest 无显式路径仍写了影子账本（隔离失效）"
    p2 = tmp_path / "signals.jsonl"
    _render({"quality": "A", "prices": {"primary": 63884.0}, "_shadow_path": p2})
    assert calls and calls[-1] == str(p2)


# ── P0-b 接线：路由计划的几何来源标记（2026-09-17 实跑回归）────────────

def _route_engine(plans):
    def _ohlcv(n=80):
        closes = [100 + i * 0.2 for i in range(n)]
        return {
            "opens": [c - 0.1 for c in closes], "highs": [c + 0.5 for c in closes],
            "lows": [c - 0.5 for c in closes], "closes": closes,
            "volumes": [100 + i % 4 for i in range(n)],
        }
    return {
        "futures_klines": {"15m": _ohlcv()},
        "account_balance": 100.0,
        "prices": {"primary": 115.8},
        "_shadow_enabled": False,
        "_candidate_plans": plans,
    }


def _route_main():
    return {
        "grade": "A多", "direction_text": "偏多", "entry": 115.8, "stop": 114.8,
        "target": 118.3, "mcp_fvg_quality_score": 80, "vwap": 114, "vah": 120, "val": 105,
    }


def _route_call(engine):
    import auto_card
    auto_card._resolve_card_final_verdict(
        "BTCUSDT", {"status": "A多", "direction": "long"}, engine,
        _route_main(), _dual(), {"stop": 114.8, "target": 118.3, "rr": 2.5, "atr": 1.0}, "无",
    )
    return engine


def test_route_plan_geometry_marker_gates_plan_level_checks():
    """路由计划只有自带完整三件套（geometry_from_result）才算真实计划几何。

    2026-09-17 实跑回归：生产 plans 的 entry/stop/target 会从 decision_main
    兜底回填（恒 >0），若只看数值，plan_geometry 恒真，兜底参考几何又触发
    计划级硬否决（「连人工候选都不给」误拦）。须以来源标记判定。
    """
    plans = [
        {"model_id": "value_rotation", "entry": 115.8, "stop": 114.8, "target": 119.0,
         "rr": 3.2, "quality": 95, "geometry_from_result": True},
        {"model_id": "fvg_pullback", "entry": 115.8, "stop": 114.8, "target": 118.3,
         "rr": 2.5, "quality": 80, "geometry_from_result": True},
    ]
    e_marked = _route_call(_route_engine([dict(p) for p in plans]))
    assert e_marked["_model_route"] is not None, "路由未选中，用例前提不成立"
    assert e_marked["_risk_v2"]["plan_geometry"] is True

    unmarked = [{k: v for k, v in p.items() if k != "geometry_from_result"} for p in plans]
    e_unmarked = _route_call(_route_engine(unmarked))
    assert e_unmarked["_risk_v2"]["plan_geometry"] is False
