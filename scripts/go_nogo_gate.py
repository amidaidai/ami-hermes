#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 v9.6 GO/NO-GO 硬闸门 — 下单前八问。

在分析卡输出后、实际下单前执行。任一红灯 = 禁止执行，给出明确原因。
社区对标：EdgeFlo 盘前7问、NautilusTrader pre-trade risk、Freqtrade Protections；
v9.6 增加双指标共振闸门后为8问。
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import math

TZ = timezone(timedelta(hours=8))

# ── 闸门权重和红灯条件 ──
GATE_RULES = {
    "data_freshness": {
        "weight": 2,          # 权重分 (满分2)
        "description": "数据新鲜度",
        "pass_condition": "数据等级≥B且快照<1h",
        "red_light": "数据过期或质量低于B级，市价不足信，禁止执行"
    },
    "tv_live": {
        "weight": 2,
        "description": "TV现场确认",
        "pass_condition": "TV SVP行动格已读且方向一致",
        "red_light": "TV数据未实时读取或与信号方向冲突，禁止执行"
    },
    "rr_ratio": {
        "weight": 2,
        "description": "R:R底线",
        "pass_condition": "首选方向R:R≥1:2",
        "red_light": "R:R不足1:2，不满足社区最低标准，禁止执行"
    },
    "event_window": {
        "weight": 1,
        "description": "事件窗口",
        "pass_condition": "无重大数据/央行/FOMC/NFP窗口",
        "red_light": "重大数据窗口内，只观察不进场"
    },
    "protections": {
        "weight": 2,
        "description": "风控保护",
        "pass_condition": "所有Protections通过（止损冷却/回撤/冷却期）",
        "red_light": "Protections拦截，风控保护激活中，禁止执行"
    },
    "wfo_samples": {
        "weight": 1,
        "description": "样本/WFO",
        "pass_condition": "历史样本≥20且WFO效率≥0.5",
        "red_light": "历史样本不足或WFO未通过，降级观察"
    },
    "dual_indicator": {
        "weight": 2,
        "description": "双指标共振",
        "pass_condition": "SVP主方向与有效HALDRO同向或副指标不适用",
        "red_light": "SVP主驾驶与聚合有效HALDRO强冲突，禁止执行"
    },
    "portfolio_exposure": {
        "weight": 1,
        "description": "组合暴露",
        "pass_condition": "新仓与现有持仓相关≤0.7且组合风险≤15%",
        "red_light": "组合暴露过高，禁止加仓"
    },
}

FINAL_STATES = {"GO-A", "GO-B", "WAIT", "NO-GO"}

def _finite_rr(value) -> float:
    """Invalid, missing and non-finite diagnostic values fail closed."""
    if isinstance(value, bool):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def check_gate(symbol: str, engine_data: dict, meta: dict) -> dict:
    """执行GO/NO-GO八问，返回通过/拒绝和详情。

    Args:
        symbol: 品种代码 (BTCUSDT, XAUUSD, etc.)
        engine_data: auto_card采集的完整引擎数据
        meta: 分析元数据 (status, direction, rr_a, rr_b, etc.)

    Returns:
        {
            "go": bool,           # True=通过，False=禁止
            "score": int,         # 绿灯计数 0-8
            "max_score": 8,
            "red_gates": [str],   # 红灯门名称
            "yellow_gates": [str], # 黄灯门名称（警告但不拦截）
            "gates": {gate_name: {"status": "green"|"yellow"|"red", "reason": str}},
            "verdict": str,       # 一句话结论
            "timestamp": str,
        }
    """
    now = datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
    gates = {}
    red_gates = []
    yellow_gates = []
    go = True
    
    # ── 门1: 数据新鲜度 ──
    data_grade = meta.get("data_grade", "C")
    snapshot_age_h = engine_data.get("_snapshot_age_h", 24)
    if data_grade in ("A", "A-", "B") and snapshot_age_h < 1:
        gates["data_freshness"] = {"status": "green", "reason": f"数据{data_grade}级·{snapshot_age_h:.1f}h新鲜"}
    elif data_grade in ("A", "A-", "B"):
        gates["data_freshness"] = {"status": "yellow", "reason": f"数据{data_grade}级但{snapshot_age_h:.1f}h未刷新"}
        yellow_gates.append("data_freshness")
    else:
        gates["data_freshness"] = {"status": "red", "reason": GATE_RULES["data_freshness"]["red_light"]}
        red_gates.append("data_freshness")
        go = False

    # ── 门2: TV现场确认 ──
    tv_data = engine_data.get("_tv_pine") or engine_data.get("tv", {}) or engine_data.get("_tv_main") or {}
    tv_override = engine_data.get("_tv_override") or {}
    if not isinstance(tv_override, dict):
        tv_override = {}
    tv_status = engine_data.get("_tv_live_status") or engine_data.get("_tv_cache_status") or {}
    # 2026-09-13 审计修复：口径统一 —— _tv_live_status 是 TV 注入的最终结论，
    # _tv_cache_status 仅是其输入管道之一（如 dmi 缓存校验）。旧实现 cache 优先，
    # 会在 live 注入成功、历史管道失败时误报红灯（XAU 实测「品种不匹配」实例）。
    if not isinstance(tv_status, dict):
        tv_status = {}
    tv_status_known = isinstance(tv_status, dict) and "usable" in tv_status
    tv_direct_verified = bool(engine_data.get("_tv_direct_verified"))
    # A non-empty Pine/TV dictionary proves only that something was parsed. It
    # does not prove symbol identity, freshness, or a live chart witness.
    tv_verified = bool(tv_status.get("usable")) if tv_status_known else tv_direct_verified
    tv_active = tv_verified or bool(tv_data) or bool(tv_override.get("tv_active"))
    tv_grade = str(tv_override.get("tv_grade") or engine_data.get("_tv_main", {}).get("grade") or "")
    tv_block = str(meta.get("status", "")).startswith("X") or tv_grade.startswith("X")
    tv_required = str(symbol or "").upper().endswith("USDT") or "XAU" in str(symbol or "").upper()
    five_tf_required = bool(engine_data.get("_tv_five_tf_required"))
    five_tf_status = engine_data.get("_tv_five_tf_status") or {}
    five_tf_verified = isinstance(five_tf_status, dict) and bool(five_tf_status.get("usable"))
    if five_tf_required and not five_tf_verified:
        missing = ",".join(str(v) for v in (five_tf_status.get("missing") or [])) if isinstance(five_tf_status, dict) else ""
        reason = "Full缺少TV五周期证据"
        if missing:
            reason += f"·缺{missing}"
        gates["tv_live"] = {"status": "red", "reason": reason}
        red_gates.append("tv_live")
        go = False
    elif tv_status_known and not tv_verified:
        gates["tv_live"] = {"status": "red", "reason": f"TV缓存不可用·{tv_status.get('reason') or '未通过新鲜度/品种校验'}"}
        red_gates.append("tv_live")
        go = False
    elif tv_active and not tv_status_known and not tv_direct_verified:
        gates["tv_live"] = {"status": "red", "reason": "TV数据存在但缺少新鲜度/现场验证状态"}
        red_gates.append("tv_live")
        go = False
    elif tv_active and not tv_block:
        reason = "TV SVP已读"
        if tv_grade:
            reason += f"·{tv_grade}"
        if tv_verified:
            reason += "·缓存新鲜"
        gates["tv_live"] = {"status": "green", "reason": reason}
    elif tv_active:
        gates["tv_live"] = {"status": "red", "reason": f"TV禁做/结构冲突: {tv_grade or meta.get('status','')}"}
        red_gates.append("tv_live")
        go = False
    elif tv_required:
        gates["tv_live"] = {"status": "red", "reason": "加密/黄金缺少TV现场数据·禁止推断实时可用"}
        red_gates.append("tv_live")
        go = False
    else:
        gates["tv_live"] = {"status": "yellow", "reason": "TV数据未实时读取·降级观察"}
        yellow_gates.append("tv_live")

    # ── 门3: R:R底线 ──
    # st_a/st_b describe legacy opposite plans (auto_card:1737-1744).
    # A nonzero 0.547/0.566 was never replaced by rr_b through Python ``or``;
    # only a falsey/missing primary could trigger that historical fallback.
    # decision_loop recomputes canonical RR from selected execution geometry,
    # so consume that RR in EVERY final state, not only GO-A. Invalid explicit
    # values never borrow a legacy alias or the opposite plan.
    final_rr = engine_data.get("_final_verdict")
    rr_source = "meta.rr_a" if "rr_a" in meta else "meta.rr1"
    raw_rr = meta.get("rr_a") if "rr_a" in meta else meta.get("rr1")
    if isinstance(final_rr, dict) and "rr" in final_rr:
        raw_rr = final_rr["rr"]
        rr_source = "final_verdict.rr"
    rr_a = _finite_rr(raw_rr)
    rr_b = _finite_rr(meta.get("rr_b") if "rr_b" in meta else meta.get("rr2"))
    if rr_a > 0 and rr_a >= 2.0:
        gates["rr_ratio"] = {"status": "green", "reason": f"主线R:R 1:{rr_a:.1f}·≥1:2"}
    elif rr_a > 0:
        gates["rr_ratio"] = {"status": "red", "reason": f"{GATE_RULES['rr_ratio']['red_light']} 当前主线1:{rr_a:.1f}"}
        red_gates.append("rr_ratio")
        go = False
    else:
        _fallback_note = f"（反侧参考1:{rr_b:.1f}·不得用作放行依据）" if rr_b > 0 else ""
        gates["rr_ratio"] = {"status": "red", "reason": f"主推方向R:R缺失·禁止以反侧兜底{_fallback_note}"}
        red_gates.append("rr_ratio")
        go = False

    gates["rr_ratio"]["source"] = rr_source

    # ── 门4: 事件窗口 ──
    event_ban = engine_data.get("_banned_live") or meta.get("protections_status", "").startswith("拦截")
    event_reason = engine_data.get("_ban_reason") or ""
    kill_zone = engine_data.get("_kill_zone") or ""
    if not event_ban:
        gates["event_window"] = {"status": "green", "reason": f"无事件禁做·{kill_zone or '非主窗口'}"}
    elif "半仓" in str(event_reason):
        gates["event_window"] = {"status": "yellow", "reason": event_reason}
        yellow_gates.append("event_window")
    else:
        gates["event_window"] = {"status": "red", "reason": event_reason or GATE_RULES["event_window"]["red_light"]}
        red_gates.append("event_window")
        go = False

    # ── 门5: Protections ──
    prot_status = meta.get("protections_status", "未检测")
    prot_stale = bool(meta.get("protections_snapshot_stale"))
    if "通过" in str(prot_status):
        if prot_stale:
            # 2026-09-13 审计修复：快照陈旧时不得显示「全部通过」——
            # 可见降级（黄灯，不进硬拦截），快照日期如实标注。
            gates["protections"] = {
                "status": "yellow",
                "reason": f"无拦截记录·快照{meta.get('protections_snapshot', '?')}陈旧·未验证当前风控",
            }
            yellow_gates.append("protections")
        else:
            gates["protections"] = {"status": "green", "reason": "Protections全部通过"}
    elif "拦截" in str(prot_status):
        gates["protections"] = {"status": "red", "reason": prot_status}
        red_gates.append("protections")
        go = False
    else:
        gates["protections"] = {"status": "yellow", "reason": f"Protections未完整检测"}
        yellow_gates.append("protections")

    # ── 门6: 样本/WFO ──
    # 2026-09-13 审计修复：旧实现恒读默认值 0 → 卡面「样本仅0」是假值。
    # 真源 = shadow_calibration.shadow_sample_stats（auto_card 注入 engine_data）。
    reviews_count = engine_data.get("_reviews_count")
    wfo_efficiency = engine_data.get("_wfo_efficiency")
    shadow = engine_data.get("_shadow_stats") if isinstance(engine_data.get("_shadow_stats"), dict) else {}
    if reviews_count is None:
        gates["wfo_samples"] = {"status": "yellow", "reason": "影子样本未接入·本轮无法评估"}
        yellow_gates.append("wfo_samples")
    elif wfo_efficiency is None:
        if shadow:
            _stats_txt = (f"影子{shadow.get('total', '?')}·成熟{shadow.get('mature', '?')}"
                          f"·可评估{shadow.get('evaluable', '?')}")
            if int(shadow.get("evaluable", 0) or 0) <= 0:
                _stats_txt += "·缺订单模型"
        else:
            _stats_txt = f"样本{reviews_count}"
        gates["wfo_samples"] = {"status": "yellow", "reason": f"{_stats_txt}·WFO未计算"}
        yellow_gates.append("wfo_samples")
    elif reviews_count >= 20 and wfo_efficiency >= 0.5:
        gates["wfo_samples"] = {"status": "green", "reason": f"样本{reviews_count}·WFO效率{wfo_efficiency:.2f}"}
    elif reviews_count >= 20:
        gates["wfo_samples"] = {"status": "yellow", "reason": f"样本{reviews_count}但WFO效率{wfo_efficiency:.2f}<0.5"}
        yellow_gates.append("wfo_samples")
    else:
        gates["wfo_samples"] = {"status": "yellow", "reason": f"样本仅{reviews_count}<20·WFO置信不足"}
        yellow_gates.append("wfo_samples")

    # ── 门7: 双指标共振 ──
    dual = engine_data.get("_dual_indicator_verdict") or {}
    if not isinstance(dual, dict):
        dual = {}
    hard_conflict = dual.get("hard_conflict") if "hard_conflict" in dual else dual.get("conflict")
    valid_code = dual.get("valid_code", 2 if dual.get("usable") else 0)
    if hard_conflict:
        # 2026-09-13 审计修复：红灯理由优先取双指标裁决原文
        # （S3 场景给出「副S3冲突·CVD/OI背离」，比通稿更精确）。
        _red_reason = str(dual.get("direction_verdict") or "").strip()
        gates["dual_indicator"] = {"status": "red", "reason": _red_reason or GATE_RULES["dual_indicator"]["red_light"]}
        red_gates.append("dual_indicator")
        go = False
    elif dual.get("conflict") and valid_code == 1:
        gates["dual_indicator"] = {"status": "yellow", "reason": "HALDRO单源回退与SVP冲突·只等待不执行"}
        yellow_gates.append("dual_indicator")
    elif dual.get("usable") or not dual.get("asset_is_crypto", True):
        reason = dual.get("direction_verdict") or "主副指标已读"
        # 2026-09-13 审计修复：副指标有数据但未共振（不足/拥挤降级）时
        # 不得显示「共振 GREEN」——降为可见黄灯，不阻断执行授权链。
        _weak = str(reason)
        if _weak.startswith("副指标不足") or _weak.startswith("同向但拥挤"):
            gates["dual_indicator"] = {"status": "yellow", "reason": f"{reason}·未共振"}
            yellow_gates.append("dual_indicator")
        else:
            gates["dual_indicator"] = {"status": "green", "reason": reason}
    else:
        gates["dual_indicator"] = {"status": "yellow", "reason": "HALDRO副指标未读·降级确认型计划"}
        yellow_gates.append("dual_indicator")

    # ── 门8: 组合暴露 ──
    # 2026-09-13 审计修复：未接持仓数据时旧实现默认 0 → 显示「暴露0.0%」绿灯。
    # 无数据 → 黄灯「未评估」，不得把缺失显示为安全。
    corr_high = engine_data.get("_corr_high", False)
    _corr_known = "_corr_high" in engine_data and engine_data.get("_corr_high") is not None
    _exposure_raw = engine_data.get("_total_exposure_pct")
    total_exposure = None
    if _exposure_raw is not None:
        try:
            total_exposure = float(_exposure_raw)
        except (TypeError, ValueError):
            total_exposure = None
    if total_exposure is None:
        gates["portfolio_exposure"] = {"status": "yellow", "reason": "未接持仓·暴露未评估"}
        yellow_gates.append("portfolio_exposure")
    elif not corr_high and total_exposure <= 15:
        _corr_txt = "相关≤0.7·" if _corr_known else "相关未评估·"
        gates["portfolio_exposure"] = {"status": "green", "reason": f"{_corr_txt}暴露{total_exposure:.1f}%"}
    elif not corr_high:
        gates["portfolio_exposure"] = {"status": "yellow", "reason": f"暴露{total_exposure:.1f}%偏高"}
        yellow_gates.append("portfolio_exposure")
    else:
        gates["portfolio_exposure"] = {"status": "red", "reason": GATE_RULES["portfolio_exposure"]["red_light"]}
        red_gates.append("portfolio_exposure")
        go = False

    # FinalVerdict 是渲染/告警/仓位/执行的唯一真相源。旧八闸门只负责诊断，
    # 不能在 FinalVerdict=WAIT/NO-GO 时重新把计划判成可执行；反过来也不
    # 能用旧八问的红灯覆盖一个已经由 FinalVerdict 授权的结果。
    legacy_go = go
    diagnostic_red_gates = list(red_gates)
    diagnostic_yellow_gates = list(yellow_gates)
    final = engine_data.get("_final_verdict") or {}
    if not isinstance(final, dict):
        final = {}
    final_state = str(final.get("state") or "").upper()
    final_reason = str(final.get("reason") or "")
    if not final:
        # The diagnostic eight questions are never an execution authority.
        # Without a produced FinalVerdict, fail closed instead of returning
        # the legacy green state that older callers could mistake for approval.
        final_state = "NO-GO"
        final_reason = "FinalVerdict缺失·拒绝执行"
        red_gates.append("final_verdict")
        go = False
        execution_authorized = False
    elif final_state not in FINAL_STATES:
        final_state = "NO-GO"
        final_reason = "FinalVerdict状态非法·拒绝执行"
        red_gates.append("final_verdict")
        go = False
        execution_authorized = False
    else:
        # ``go`` is deliberately derived from FinalVerdict only. The legacy
        # eight-question result remains useful as a diagnostic table, but it
        # has no authority to grant or revoke execution.
        execution_authorized = final_state == "GO-A" and final.get("executable") is True
        go = execution_authorized
        if final_state == "GO-A" and not execution_authorized:
            red_gates.append("final_verdict")

    green_count = sum(1 for g in gates.values() if g["status"] == "green")
    yellow_count = len(yellow_gates)
    red_count = len(red_gates)
    
    if final_state == "WAIT":
        verdict = f"○ WAIT · {final_reason or '等待触发完成'} · 绿灯{green_count}/8"
    elif final_state == "GO-B":
        verdict = f"○ GO-B · 仅人工候选，不执行 · {final_reason or '等待确认'}"
    elif final_state == "NO-GO":
        verdict = f"✗ NO-GO · {final_reason or '/'.join(red_gates[:3])}"
    elif execution_authorized:
        verdict = f"✅ GO-A · FinalVerdict已授权 · 绿灯{green_count}/8"
    else:
        verdict = f"✗ NO-GO · FinalVerdict未授权 · 红灯{red_count}灯·{'/'.join(red_gates[:3])}"

    return {
        "go": go,
        "execution_authorized": execution_authorized,
        "legacy_go": legacy_go,
        "score": green_count,
        "max_score": 8,
        "red_gates": red_gates,
        "yellow_gates": yellow_gates,
        "diagnostic_red_gates": diagnostic_red_gates,
        "diagnostic_yellow_gates": diagnostic_yellow_gates,
        "green_count": green_count,
        "red_count": red_count,
        "yellow_count": yellow_count,
        "final_state": final_state or ("GO" if go else "NO-GO"),
        "final_reason": final_reason,
        "gates": gates,
        "verdict": verdict,
        "timestamp": now,
    }


def gate_report_card(result: dict, symbol: str) -> str:
    """生成GO/NO-GO报告卡（追加到分析卡尾部）。"""
    final_state = str(result.get("final_state") or "")
    if final_state == "WAIT":
        emoji = "○"
        status_text = "WAIT · 等待，不执行"
    elif final_state == "GO-B":
        emoji = "○"
        status_text = "GO-B · 仅人工候选，不执行"
    elif final_state == "GO-A" and result.get("execution_authorized", result["go"]):
        emoji = "✅"
        status_text = "GO-A · FinalVerdict授权"
    else:
        emoji = "✗"
        status_text = "NO-GO · 禁止执行"

    lines = [
        "",
        "### GO/NO-GO 下单闸门",
        "",
        f"{emoji} {symbol}：当前{status_text}，不自动下单；仅按FinalVerdict人工判断。",
        "",
        "| 闸门 | 状态 | 原因 |",
        "|:---|:---:|:---|",
    ]
    
    gate_order = ["data_freshness", "tv_live", "rr_ratio", "event_window",
                  "protections", "wfo_samples", "dual_indicator", "portfolio_exposure"]
    
    for gate_name in gate_order:
        g = result["gates"].get(gate_name, {})
        status = g.get("status", "—")
        reason = g.get("reason", "—")
        name = GATE_RULES.get(gate_name, {}).get("description", gate_name)
        
        emoji_map = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        status_emoji = emoji_map.get(status, "⚪")
        lines.append(f"| {status_emoji} {name} | {status.upper()} | {reason} |")
    
    lines.append("")
    lines.append(f"**裁决**: {result['verdict']}")
    if result.get("execution_authorized") and result.get("diagnostic_red_gates"):
        lines.append(
            "**诊断提示（不改变FinalVerdict授权）**: "
            + ", ".join(result["diagnostic_red_gates"])
        )
    elif result["red_gates"]:
        lines.append(f"**红灯**: {', '.join(result['red_gates'])}")
    if result["yellow_gates"]:
        lines.append(f"**黄灯**: {', '.join(result['yellow_gates'])}")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # Smoke test
    engine_data = {"_snapshot_age_h": 0.1, "_banned_live": False, "_reviews_count": 20, "_wfo_efficiency": 0.72}
    meta = {"data_grade": "A", "rr_a": 2.5, "rr_b": 1.8, "protections_status": "通过"}
    result = check_gate("BTCUSDT", engine_data, meta)
    print("GO?" if result["go"] else "NO-GO")
    for k, v in result["gates"].items():
        print(f"  {k}: {v['status']} - {v['reason']}")
    print()
    print(gate_report_card(result, "BTCUSDT"))
