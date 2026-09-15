# -*- coding: utf-8 -*-
"""R:R 分层契约：观察候选带（1.5–1.99）不得被硬否决。

2026-09-15 发现：同一个 R:R<2.0 事实在两处被定性相反 ——
  · `decision_loop.py` 记成 **等待类** `rr_ratio`（「WAIT 保留人工观察候选」）；
  · `risk_constitution.py` 检查2 记成 **violation → allowed=False → 硬门**
    `risk_constitution`。
后果：合同里白纸黑字的「1.5–1.99 = B/C 人工观察候选·不授权执行」整段被杀，
影子账本实测 46 个信号死在这一段，PLAN-B 的适用范围被掐掉一半。

本文件把分层钉死，同时守住最关键的安全不变量：
**R:R 在 [1.5, 2.0) 永远不可能变成 GO-A。**
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from risk_constitution import CONSTITUTION  # noqa: E402
from risk_constitution_v2 import evaluate_risk  # noqa: E402
from tv_indicator_contract import RR_BC_MIN, RR_HARD_MIN  # noqa: E402


class _OkProtections:
    """保护规则全通过；避免用例依赖磁盘上的 protections 状态。"""

    def check_all(self, symbol, current_bar):
        return True, []


def _inputs(rr: float, **over):
    entry = 100.0
    stop = 98.0
    target = entry + (entry - stop) * rr
    data = {
        "symbol": "BTCUSDT",
        "account_balance": 1000.0,
        "entry_price": entry,
        "stop_price": stop,
        "target_price": target,
        "atr": 2.0,                 # 止损=1×ATR，落在 0.5–2.5 夹层内
        "atr_pct": 0.02,
        "regime_multiplier": 1.0,
        "current_drawdown_pct": 0.0,
        "has_major_news": False,
        "volatility_24h_pct": 0.0,
        "current_bar": 0,
        "total_exposure_pct": 0.0,
        "corr_high": False,
        "protections": _OkProtections(),
    }
    data.update(over)
    return data


def _rr_violations(out):
    return [v for v in out["violations"] if "R:R" in str(v)]


def test_observe_band_is_not_a_violation():
    out = evaluate_risk(_inputs(1.8))
    assert _rr_violations(out) == [], out["violations"]
    assert out["observe_only_rr"] == pytest.approx(1.8, abs=1e-6)
    assert any("仅B/C人工观察候选" in r for r in out["reasons"]), out["reasons"]
    # 观察候选带允许继续走人工候选路径（风险额度可用），但绝不等于授权
    assert out["allowed"] is True


def test_below_observe_floor_is_still_vetoed():
    out = evaluate_risk(_inputs(1.2))
    assert _rr_violations(out), out["violations"]
    assert out["observe_only_rr"] is None
    assert out["allowed"] is False


def test_at_or_above_authorization_line_is_clean():
    out = evaluate_risk(_inputs(2.0))
    assert _rr_violations(out) == []
    assert out["observe_only_rr"] is None
    assert any("✓" in r and "R:R" in r for r in out["reasons"]), out["reasons"]


def test_no_more_self_contradictory_2_0_lt_2_0_message():
    """曾经 `:.1f` 把 1.96 印成 2.0，出现「R:R 2.0:1 < 2.0:1 底线」。"""
    for rr in (1.96, 1.99, 2.04):
        out = evaluate_risk(_inputs(rr))
        for v in _rr_violations(out):
            assert "2.0:1 < 2.0:1" not in str(v), v


def test_thresholds_match_the_contract_module():
    """宪法阈值必须与 tv_indicator_contract 的分层一致，不能再各写一套。"""
    assert CONSTITUTION["REQUIRED_RR_RATIO"] == RR_HARD_MIN == 2.0
    assert CONSTITUTION["OBSERVE_RR_RATIO"] == RR_BC_MIN == 1.5


def test_observe_band_can_never_authorize_execution():
    """最关键的安全不变量：R:R 在 [1.5,2.0) 走完整决策闭环也到不了 GO-A。"""
    from decision_loop import resolve_final_verdict
    from decision_regime import classify_decision_regime

    regime = classify_decision_regime(
        adx=30, atr_ratio=1.0, ema_spread_atr=0.7, vwap_crosses_20=1,
        va_stay_ratio_20=0.2, displacement_atr=0.8, rvol=1.1,
    )
    risk = evaluate_risk(_inputs(1.8))
    main = {
        "grade": "A多", "direction": "long", "model_id": "fvg_pullback",
        "entry": 100.0, "stop": 98.0, "target": 103.6, "rr": 1.8,
        "mcp_fvg_quality_score": 82.0, "mcp_ob_quality_score": 70.0,
        "risk_label": "风控",
        "data_grade": "A", "snapshot_age_sec": 10.0,
        "location_valid": True, "trigger_confirmed": True, "bar_closed": True,
    }
    dual = {"asset_is_crypto": True, "valid_code": 2, "conflict": False,
            "aligned": True, "risk_code": 0}
    out = resolve_final_verdict(
        "BTCUSDT", main, dual, regime=regime, risk=risk,
        advanced={"direction": "long", "gate": {"execute": True}},
    )
    assert out.executable is False, "R:R<2 竟然拿到执行权"
    assert out.state != "GO-A", out.state
    assert out.entry is None and out.stop is None and out.target is None
    assert "rr_ratio" in out.blockers
    # 有方案也只能是人工方案，且明确非授权
    if out.plan is not None:
        assert out.plan["authorized"] is False
