#!/usr/bin/env python3
"""棠溪统一决策闭环 vNext。

所有渲染、警报和执行层只消费 FinalVerdict，避免原始SVP等级与HALDRO冲突
仍保留可执行订单。该模块是纯函数，供实盘、回测与影子校准共用。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from typing import Any

from decision_regime import DecisionRegime
from tv_indicator_contract import SVP_AUTHORIZATION_LABEL, SVP_FORBIDDEN_LABELS


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
    decision_id: str = ""
    watch_stop: float | None = None
    watch_target: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(str(value).replace("−", "-").replace("%", ""))
        return number if math.isfinite(number) else default
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


def _svp_requires_wait(main: dict[str, Any]) -> bool:
    """Treat SVP's explicit waiting language as a decision contract.

    The action grid is human-readable, but legacy callers may still pass an
    A-grade alongside an unclosed candle or a conflict. Those states must not
    be upgraded into an executable order by a stale numeric grade.
    """
    fields = (
        "conclusion", "结论", "treatment", "action", "路径", "path",
        "direction", "direction_text", "现位", "risk", "风控",
    )
    text = " ".join(str(main.get(field) or "") for field in fields)
    return any(token in text for token in (
        "⚠冲突", "未收线", "等收线", "等解除", "C等待", "观望",
    ))


def _geometry_ok(side: str, entry: float | None, stop: float | None, target: float | None) -> bool:
    if entry is None or stop is None or target is None:
        return False
    if side == "long":
        return stop < entry < target
    if side == "short":
        return stop > entry > target
    return False


def _watch_tuple(main: dict[str, Any], side: str,
                 entry: float | None, stop: float | None, target: float | None):
    """Observation prices for human judgement — never an execution order.

    The panel's 「风控·观察」 row is the only source of review prices, so its
    candidate triple wins over the raw one.  Both must be a complete, positive
    triple; a partial tuple yields None instead of a half order.  Geometry is
    re-verified by the renderer before anything reaches the card.
    """
    if side == "neutral":
        return None
    candidate = tuple(_number(main.get("candidate_" + key), 0.0)
                      for key in ("entry", "stop", "target"))
    if all(value > 0 for value in candidate):
        return (side, *candidate)
    if entry is None or stop is None or target is None:
        return None
    if min(entry, stop, target) <= 0:
        return None
    return (side, entry, stop, target)


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
    advanced: dict[str, Any] | None = None,
) -> FinalVerdict:
    """把SVP候选、HALDRO、体制和风控合并为唯一可执行裁决。"""
    # Hash the original evidence, before defaults/normalization. JSON key order
    # and dataclass tuple/list round trips do not change replay identity.
    # Callers own the versioned snapshot; no clock, randomness or live reads.
    identity_payload = {
        "symbol": symbol, "main": main, "dual": dual,
        "regime": asdict(regime) if regime is not None else None,
        "risk": risk, "advanced": advanced,
    }
    decision_id = hashlib.sha256(json.dumps(
        identity_payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    dual = dual or {}
    risk = risk or {}
    advanced = advanced or {}
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
    # Match the source-snapshot boundary: macro/cross-source context is valid
    # for one hour, while TV/action-grid freshness is enforced separately.
    if data_grade not in ("A", "A-", "B") or snapshot_age_sec > 3600:
        hard.append("data")
    # X禁做 硬阻断（2026-08-31 硬化：旧逻辑X会走WAIT被覆盖成C等待，丢失禁止语义）
    if grade.startswith("X"):
        hard.append("x_forbidden")
        warnings.append("x_forbidden")
    if bool(main.get("mtf_conflict")):
        hard.append("background")
    # TV cache status is produced by the data boundary.  Once a caller has
    # explicitly marked the snapshot unusable, stale/invalid TV data must be
    # a hard blocker rather than a decorative warning.
    if main.get("tv_live_verified") is False:
        hard.append("tv_live")
    if main.get("tv_five_tf_required") and main.get("tv_five_tf_verified") is not True:
        hard.append("tv_five_tf")
    cross_source_hard = main.get("cross_source_hard_blockers")
    if isinstance(cross_source_hard, (list, tuple)) and cross_source_hard:
        hard.append("cross_source")
    cross_source_warnings = main.get("cross_source_warnings")
    if isinstance(cross_source_warnings, (list, tuple)):
        warnings.extend(f"cross_source:{item}" for item in cross_source_warnings if item)
    if main.get("location_valid") is not True:
        wait.append("location")
    if main.get("trigger_confirmed") is not True:
        wait.append("trigger")
    if main.get("bar_closed") is not True:
        wait.append("bar_closed")
    if _svp_requires_wait(main):
        wait.append("svp_wait_language")

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

    # Non-crypto callers may omit the HALDRO contract entirely (N/A).
    # When applicable or explicitly supplied, alignment must be proven, not
    # inferred from the absence of a hard conflict or from a truthy value.
    if (is_crypto or "aligned" in dual) and dual.get("aligned") is not True:
        wait.append("dual_alignment")

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
    min_rr = 2.0  # P0-3 (2026-08-31): R:R 硬底线统一 1:2，删除 B 级 1.5 豁免
    execution_complete = all(value is not None for value in (entry, stop, target))
    execution_geometry_valid = False
    if entry is not None and stop is not None and target is not None:
        execution_geometry_valid = (
            (side == "long" and stop < entry < target)
            or (side == "short" and stop > entry > target)
        )
        if execution_geometry_valid:
            # The execution source owns the actual geometry.  Never trust a
            # claimed upstream RR when Entry/Stop/Target imply a different value.
            stop_distance = abs(entry - stop)
            if stop_distance > 0:
                rr = abs(target - entry) / stop_distance
    if is_a and not execution_complete:
        # A numeric grade/R:R is not enough to authorize execution.  Keep the
        # result in WAIT so the single execution source itself cannot leak a
        # GO-A with an incomplete Entry/Stop/Target contract.
        wait.append("execution_contract")
    elif is_a and not execution_geometry_valid:
        wait.append("execution_contract")
    if rr < min_rr:
        wait.append("rr_ratio")
    if side == "neutral" or grade.startswith(("X", "C等待")):
        wait.append("no_direction")
    # P0-1 (2026-08-31): B/C反 一律视为等待触发，不产生自动执行权（GO-B 取消）
    if is_bc:
        wait.append("b_wait")

    # ── SVP 授权闸（2026-09-11 定版指标）──────────────────────────────
    # 定版行动格里「风控」行标签是 SVP 唯一的执行授权出口，四种形态语义不同：
    #   风控         → 授权（仍须 A 级 + 三件套完整 + 几何有效才 GO-A）
    #   风控·观察    → 只有观察价（pendingPlan）→ 未授权，价格只进人工候选
    #   风控·未授权  → 副指标 S3 冲突 → 未授权，价格只进人工候选
    #   禁做·不出价  → 结构禁做（setupX）→ 硬阻断，连候选价都不出
    # 标签一旦出现在载荷里，任何数字等级都不得把它升级成可执行；
    # 键缺失 = 旧载荷/无 TV 行动格，保持向后兼容（不引入新阻断）。
    svp_authorized: bool | None = None
    if "risk_label" in main:
        risk_label = str(main.get("risk_label") or "").strip()
        svp_authorized = risk_label == SVP_AUTHORIZATION_LABEL
        if not svp_authorized:
            if risk_label in SVP_FORBIDDEN_LABELS:
                hard.append("svp_authorization")
            else:
                wait.append("svp_authorization")

    risk_usd = _number(risk.get("risk_usd"), 0.0)
    if risk and not bool(risk.get("allowed", False)):
        hard.append("risk_constitution")
        warnings.extend(str(v) for v in risk.get("violations", []) if v)
    if risk and risk_usd <= 0:
        hard.append("risk_constitution")
        warnings.append("risk_usd_invalid")

    # Advanced order-flow/meta-label checks are decision gates, not merely
    # explanatory card text.  Only an explicit denial is actionable here;
    # missing/legacy data remains handled by the ordinary dual-indicator gate.
    advanced_gate = advanced.get("gate") if isinstance(advanced, dict) else None
    if isinstance(advanced_gate, dict) and advanced_gate.get("execute") is False:
        hard.append("advanced_confluence")
        gate_reason = str(advanced_gate.get("reason") or "高级订单流门控否决")
        warnings.append(f"advanced_confluence:{gate_reason}")
    # A gate computed for another side cannot authorize this candidate.
    # Omitted direction remains compatible with legacy directionless gates;
    # an explicitly supplied null/unknown/alias is not a matching side.
    if isinstance(advanced, dict) and "direction" in advanced and advanced["direction"] != side:
        wait.append("advanced_direction")

    # Fail closed at the authority boundary. Legacy callers may omit evidence
    # while constructing non-A observation records. Missing evidence on an A
    # candidate remains a hard blocker even when strict boolean checks wait.
    if is_a:
        evidence_fields = (
            "data_grade", "snapshot_age_sec", "location_valid", "trigger_confirmed", "bar_closed",
        )
        if any(field not in main for field in evidence_fields):
            hard.append("decision_evidence")
    if is_a and not hard and not wait:
        if regime is None:
            hard.append("regime_missing")
        if not risk:
            hard.append("risk_constitution")
            warnings.append("risk_missing")
        if not isinstance(advanced_gate, dict) or advanced_gate.get("execute") is not True:
            wait.append("advanced_pending")

    hard = list(dict.fromkeys(hard))
    wait = list(dict.fromkeys(wait))
    warnings = list(dict.fromkeys(warnings))
    all_blockers = tuple(hard + wait)

    if hard:
        state = "NO-GO"
        executable = False
    elif wait or is_bc:
        # P0-1 (2026-08-31): B/C反 一律 WAIT 不执行——等触发/确认，无自动授权；
        # 候选价经 watch_side/watch_entry 保留供人工判断。
        state = "WAIT"
        executable = False
    elif is_a and not weak_haldro:
        state = "GO-A"
        executable = True
    else:
        state = "WAIT"
        executable = False

    if not executable:
        final_side = "neutral"
        final_entry = final_stop = final_target = None
        if state == "NO-GO":
            final_grade = "X禁做"
        elif is_bc:
            # 保留 B多/B空/C反多/C反空 供渲染层显示“等触发+候选”，不覆盖成 C等待
            final_grade = grade
            wait = list(dict.fromkeys([*wait, "b_wait"]))
        else:
            final_grade = "C等待"
    else:
        final_side = side
        final_entry, final_stop, final_target = entry, stop, target
        final_grade = grade

    reason = (
        "硬闸门：" + "/".join(hard)
        if hard else "等待：" + "/".join(wait)
        if wait else "全部硬闸门通过"
    )
    # Observation prices for human judgement only.  A hard veto must not leak a
    # candidate disguised as observation, and a partial tuple is not a plan.
    watch_side, watch_entry, watch_stop, watch_target = "neutral", None, None, None
    if state != "NO-GO":
        watch = _watch_tuple(main, side, entry, stop, target)
        if watch is not None:
            watch_side, watch_entry, watch_stop, watch_target = watch
    gate = lambda status, why: {"status": status, "reason": why}
    regime_blocked = any(item in hard for item in ("regime_missing", "regime_blocked", "regime_model", "exhaustion_chase"))
    orderflow_yellow = any(item in wait for item in ("dual_alignment", "advanced_direction")) or any(item.startswith("haldro_") for item in warnings)
    gates = {
        "data": gate("red" if any(item in hard for item in ("data", "decision_evidence")) else "green", "数据过期/证据缺失" if any(item in hard for item in ("data", "decision_evidence")) else "数据新鲜"),
        "background": gate("red" if "background" in hard else "green", "多周期硬冲突" if "background" in hard else "上级背景允许"),
        "regime": gate("red" if regime_blocked else "green", "模型不适配当前体制" if regime_blocked else "体制允许模型"),
        "location": gate("yellow" if any(item in wait for item in ("location", "zone_quality")) else "green", "位置/区域质量不足" if any(item in wait for item in ("location", "zone_quality")) else "位置有效"),
        "trigger": gate("yellow" if any(item in wait for item in ("trigger", "bar_closed", "no_direction")) else "green", "等待闭柱触发" if any(item in wait for item in ("trigger", "bar_closed", "no_direction")) else "触发确认"),
        "orderflow": gate(
            "red" if "dual_indicator" in hard or "advanced_confluence" in hard else "yellow" if orderflow_yellow else "green",
            "主副强冲突" if "dual_indicator" in hard else "高级订单流门控否决" if "advanced_confluence" in hard else "高级订单流方向不匹配" if "advanced_direction" in wait else "主副未确认同向" if "dual_alignment" in wait else "副驾驶弱/回退" if orderflow_yellow else "订单流允许",
        ),
        "rr": gate("yellow" if "rr_ratio" in wait else "green", "R:R不足" if "rr_ratio" in wait else "R:R通过"),
        "risk": gate(
            "red" if "risk_constitution" in hard or "svp_authorization" in hard
            else "yellow" if "svp_authorization" in all_blockers
            else "green",
            "风控宪法拦截" if "risk_constitution" in hard
            else "SVP未授权执行" if "svp_authorization" in all_blockers
            else "风控通过",
        ),
    }
    if main.get("tv_five_tf_required"):
        gates["tv_five_tf"] = gate(
            "green" if "tv_five_tf" not in hard else "red",
            "TV五周期通过" if "tv_five_tf" not in hard else "TV五周期缺失/过期/身份不符",
        )
    if main.get("cross_validation") is not None or isinstance(cross_source_hard, (list, tuple)):
        gates["cross_source"] = gate(
            "red" if "cross_source" in hard else "yellow" if cross_source_warnings else "green",
            "核心来源失效" if "cross_source" in hard else "可选来源降级" if cross_source_warnings else "来源矩阵通过",
        )
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
        watch_side=watch_side,
        watch_entry=watch_entry,
        watch_stop=watch_stop,
        watch_target=watch_target,
        decision_id=decision_id,
    )
