#!/usr/bin/env python3
"""棠溪风控宪法统一入口 v2。

回测、实盘和复盘均调用 evaluate_risk()。position_sizer 不再独立决定风险金额。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from risk_constitution import (
    RiskState,
    check_constitution,
    combined_risk_check,
    load_protections,
    load_risk_state,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "risk_constitution_v2.json"


def _config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate_risk(inputs: dict[str, Any]) -> dict[str, Any]:
    """单一风控入口；返回唯一可执行仓位和全部违规原因。"""
    cfg = _config()
    balance = max(0.0, _f(inputs.get("account_balance")))
    atr = max(0.0, _f(inputs.get("atr")))
    entry = _f(inputs.get("entry_price"))
    stop = _f(inputs.get("stop_price"))
    target = _f(inputs.get("target_price"))
    regime_divisor = _f(inputs.get("regime_multiplier"), 1.0)
    violations: list[str] = []

    if regime_divisor <= 0:
        return {
            "allowed": False, "risk_usd": 0.0, "position_size": 0.0,
            "risk_tier": "blocked", "stop_valid": False,
            "violations": ["体制禁做"], "protections_passed": False,
            "drawdown_multiplier": 0.0, "regime_multiplier": regime_divisor,
        }
    if balance <= 0 or atr <= 0 or entry <= 0 or stop <= 0 or target <= 0:
        violations.append("风控输入不完整")

    stop_distance = abs(entry - stop)
    stop_atr = stop_distance / atr if atr > 0 else 0.0
    stop_valid = cfg["min_stop_atr"] <= stop_atr <= cfg["max_stop_atr"]
    if atr > 0 and not stop_valid:
        violations.append(
            f"止损{stop_atr:.2f}×ATR不在{cfg['min_stop_atr']:.1f}-{cfg['max_stop_atr']:.1f}夹层"
        )

    base = combined_risk_check(
        account_balance=balance,
        atr_pct=max(0.0, _f(inputs.get("atr_pct"))),
        current_drawdown_pct=max(0.0, _f(inputs.get("current_drawdown_pct"))),
        max_risk_usd_abs=_f(cfg["max_risk_usd"]),
    )
    # 宪法单笔风险硬上限先于体制缩放；低波动不得把风险放大到1%以上。
    capped_base_risk = min(
        _f(base.get("risk_usd")),
        balance * _f(cfg["base_risk_pct"], 0.01),
        _f(cfg["max_risk_usd"]),
    )
    risk_usd = round(capped_base_risk / regime_divisor, 4)

    state = inputs.get("risk_state")
    if not isinstance(state, RiskState):
        state = load_risk_state()
    constitution = check_constitution(
        symbol=str(inputs.get("symbol") or ""),
        risk_usd=risk_usd,
        account_balance=balance,
        entry_price=entry or None,
        stop_price=stop or None,
        target1_price=target or None,
        atr_value=atr or None,
        state=state,
        volatility_24h_pct=max(0.0, _f(inputs.get("volatility_24h_pct"))),
        has_major_news=bool(inputs.get("has_major_news")),
    )
    violations.extend(str(v) for v in constitution.get("violations", []) if v)

    protections = inputs.get("protections") or load_protections()
    protections_passed, protection_violations = protections.check_all(
        str(inputs.get("symbol") or ""), int(_f(inputs.get("current_bar")))
    )
    violations.extend(str(v) for v in protection_violations if v)

    if bool(inputs.get("corr_high")):
        violations.append("新仓与现有持仓相关性过高")
    exposure = _f(inputs.get("total_exposure_pct"))
    if exposure > _f(cfg["max_total_exposure_pct"]):
        violations.append(f"组合总风险{exposure:.1f}%超过{cfg['max_total_exposure_pct']:.0f}%")

    violations = list(dict.fromkeys(violations))
    allowed = not violations and protections_passed and risk_usd > 0 and stop_distance > 0
    position_size = round(risk_usd / stop_distance, 8) if allowed else 0.0
    dd_mult = _f(base.get("drawdown_mult"), 1.0)
    if not allowed:
        tier = "blocked"
        risk_usd = 0.0
    elif dd_mult <= 0.5 or regime_divisor >= 2.0:
        tier = "half"
    elif dd_mult < 1.0 or regime_divisor > 1.0:
        tier = "light"
    else:
        tier = "normal"

    return {
        "allowed": allowed,
        "risk_usd": risk_usd,
        "position_size": position_size,
        "risk_tier": tier,
        "stop_valid": stop_valid,
        "violations": violations,
        "protections_passed": protections_passed,
        "drawdown_multiplier": dd_mult,
        "volatility_multiplier": _f(base.get("volatility_mult"), 1.0),
        "regime_multiplier": regime_divisor,
        "reason": base.get("reason", ""),
    }
