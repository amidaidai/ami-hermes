#!/usr/bin/env python3
"""棠溪统一决策闭环 vNext。

所有渲染、警报和执行层只消费 FinalVerdict，避免原始SVP等级与HALDRO冲突
仍保留可执行订单。该模块是纯函数，供实盘、回测与影子校准共用。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from decision_regime import DecisionRegime


@dataclass(frozen=True)
class FinalVerdict:
    state: str                         # GO-A / GO-B / WAIT / NO-GO
    executable: bool
    side: str                          # long / short / neutral
    grade: str
    model_id: str
    entry: float | None
    stop: float | None
    target: float | None
    rr: float
    risk_usd: float
    blockers: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    gates: dict[str, dict[str, str]] = field(default_factory=dict)
    reason: str = ""
    watch_side: str = "neutral"
    watch_entry: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace("−", "-").replace("%", ""))
    except (TypeError, ValueError):
        return default


def _side(main: dict[str, Any]) -> str:
    raw = str(main.get("direction") or main.get("direction_text") or main.get("grade") or "").lower()
    if raw in ("long", "buy", "多") or "多" in raw:
        return "long"
    if raw in ("short", "sell", "空") or "空" in raw:
        return "short"
    return "neutral"


def _model_id(main: dict[str, Any]) -> str:
    raw = str(main.get("model_id") or main.get("model") or "").strip().lower()
    aliases = {
        "vwap反抽": "vwap_pullback",
        "vwap回踩": "vwap_pullback",
        "fvg回踩": "fvg_pullback",
        "ob回踩": "ob_pullback",
        "poc拒绝": "poc_rejection",
        "vah/val回收": "value_rotation",
        "突破接受": "breakout_acceptance",
        "扫流动性回收": "liquidity_sweep",
    }
    normalized = aliases.get(raw, raw)
    if normalized in ("", "无", "none", "unknown", "model_wait"):
        fvg_q = _number(main.get("mcp_fvg_quality_score"), 0.0)
        ob_q = _number(main.get("mcp_ob_quality_score"), 0.0)
        if fvg_q >= 55 and fvg_q >= ob_q:
            return "fvg_pullback"
        if ob_q >= 55:
            return "ob_pullback"
        return "unknown"
    return normalized


def _zone_quality(main: dict[str, Any], model_id: str) -> float | None:
    key = None
    if "fvg" in model_id:
        key = "mcp_fvg_quality_score"
    elif model_id.startswith("ob") or "ob_" in model_id:
        key = "mcp_ob_quality_score"
    if not key or main.get(key) in (None, "", "—", "--"):
        return None
    return _number(main.get(key), 0.0)


def resolve_final_verdict(
    symbol: str,
    main: dict[str, Any],
    dual: dict[str, Any] | None,
    *,
    regime: DecisionRegime | None = None,
    risk: dict[str, Any] | None = None,
) -> FinalVerdict:
    """把SVP候选、HALDRO、体制和风控合并为唯一可执行裁决。"""
    dual = dual or {}
    risk = risk or {}
    grade = str(main.get("grade") or "C等待")
    side = _side(main)
    model_id = _model_id(main)
    entry = _number(main.get("entry") or main.get("mcp_entry_price"), 0.0) or None
    stop = _number(main.get("stop") or main.get("mcp_stop_price"), 0.0) or None
    target = _number(main.get("target") or main.get("mcp_target_price"), 0.0) or None
    rr = _number(main.get("rr") or main.get("rr_ratio"), 0.0)
    if rr <= 0 and entry and stop and target and abs(entry - stop) > 0:
        rr = abs(target - entry) / abs(entry - stop)

    hard: list[str] = []
    wait: list[str] = []
    warnings: list[str] = []

    data_grade = str(main.get("data_grade") or "A")
    snapshot_age_sec = _number(main.get("snapshot_age_sec"), 0.0)
    if data_grade not in ("A", "A-", "B") or snapshot_age_sec > 60:
        hard.append("data")
    if bool(main.get("mtf_conflict")):
        hard.append("background")
    if main.get("location_valid") is False:
        wait.append("location")
    if main.get("trigger_confirmed") is False:
        wait.append("trigger")

    is_crypto = bool(dual.get("asset_is_crypto", str(symbol).upper().endswith("USDT")))
    valid_code = int(_number(dual.get("valid_code"), 0.0))
    conflict = bool(dual.get("conflict"))
    weak_haldro = False
    if is_crypto:
        if valid_code <= 0:
            wait.append("haldro_invalid")
            warnings.append("haldro_invalid")
            conflict = False  # 无效数据不得制造方向冲突
        elif valid_code == 1:
            weak_haldro = True
            warnings.append("haldro_fallback")
            if conflict:
                wait.append("haldro_fallback_conflict")
                warnings.append("haldro_fallback_conflict")
        elif conflict:
            hard.append("dual_indicator")

    if regime is not None:
        if regime.position_multiplier <= 0:
            hard.append("regime_blocked")
        elif model_id not in ("unknown", *regime.allowed_models):
            hard.append("regime_model")
        if regime.exhausted and model_id in ("breakout_acceptance", "direct_chase"):
            hard.append("exhaustion_chase")

    quality = _zone_quality(main, model_id)
    if quality is not None and quality < 55:
        wait.append("zone_quality")

    is_a = grade.startswith("A")
    is_bc = grade.startswith(("B", "C反"))
    min_rr = 2.0 if is_a else 1.5 if is_bc else 2.0
    if rr < min_rr:
        wait.append("rr_ratio")
    if side == "neutral" or grade.startswith(("X", "C等待")):
        wait.append("no_direction")

    risk_usd = _number(risk.get("risk_usd"), 0.0)
    if risk and not bool(risk.get("allowed", False)):
        hard.append("risk_constitution")
        warnings.extend(str(v) for v in risk.get("violations", []) if v)

    hard = list(dict.fromkeys(hard))
    wait = list(dict.fromkeys(wait))
    warnings = list(dict.fromkeys(warnings))
    all_blockers = tuple(hard + wait)

    if hard:
        state = "NO-GO"
        executable = False
    elif wait:
        state = "WAIT"
        executable = False
    elif is_a and not weak_haldro:
        state = "GO-A"
        executable = True
    elif is_a or is_bc:
        state = "GO-B"
        executable = True
    else:
        state = "WAIT"
        executable = False

    if not executable:
        final_side = "neutral"
        final_entry = final_stop = final_target = None
        final_grade = "X禁做" if state == "NO-GO" else "C等待"
    else:
        final_side = side
        final_entry, final_stop, final_target = entry, stop, target
        final_grade = grade if state == "GO-A" else ("B多" if side == "long" else "B空")

    reason = (
        "硬闸门：" + "/".join(hard)
        if hard else "等待：" + "/".join(wait)
        if wait else "全部硬闸门通过"
    )
    gate = lambda status, why: {"status": status, "reason": why}
    regime_blocked = any(item in hard for item in ("regime_blocked", "regime_model", "exhaustion_chase"))
    orderflow_yellow = any(item.startswith("haldro_") for item in warnings)
    gates = {
        "data": gate("red" if "data" in hard else "green", "数据过期/降级" if "data" in hard else "数据新鲜"),
        "background": gate("red" if "background" in hard else "green", "多周期硬冲突" if "background" in hard else "上级背景允许"),
        "regime": gate("red" if regime_blocked else "green", "模型不适配当前体制" if regime_blocked else "体制允许模型"),
        "location": gate("yellow" if any(item in wait for item in ("location", "zone_quality")) else "green", "位置/区域质量不足" if any(item in wait for item in ("location", "zone_quality")) else "位置有效"),
        "trigger": gate("yellow" if any(item in wait for item in ("trigger", "no_direction")) else "green", "等待闭柱触发" if any(item in wait for item in ("trigger", "no_direction")) else "触发确认"),
        "orderflow": gate("red" if "dual_indicator" in hard else "yellow" if orderflow_yellow else "green", "主副强冲突" if "dual_indicator" in hard else "副驾驶弱/回退" if orderflow_yellow else "订单流允许"),
        "rr": gate("yellow" if "rr_ratio" in wait else "green", "R:R不足" if "rr_ratio" in wait else "R:R通过"),
        "risk": gate("red" if "risk_constitution" in hard else "green", "风控宪法拦截" if "risk_constitution" in hard else "风控通过"),
    }
    return FinalVerdict(
        state=state,
        executable=executable,
        side=final_side,
        grade=final_grade,
        model_id=model_id,
        entry=final_entry,
        stop=final_stop,
        target=final_target,
        rr=round(rr, 3),
        risk_usd=round(risk_usd, 4),
        blockers=all_blockers,
        warnings=tuple(warnings),
        gates=gates,
        reason=reason,
        watch_side=side,
        watch_entry=entry,
    )
