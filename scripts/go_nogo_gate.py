#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 v9.6 GO/NO-GO 硬闸门 — 下单前七问。

在分析卡输出后、实际下单前执行。任一红灯 = 禁止执行，给出明确原因。
社区对标：EdgeFlo 盘前7问、NautilusTrader pre-trade risk、Freqtrade Protections。
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta

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
    "portfolio_exposure": {
        "weight": 1,
        "description": "组合暴露",
        "pass_condition": "新仓与现有持仓相关≤0.7且组合风险≤15%",
        "red_light": "组合暴露过高，禁止加仓"
    },
}

def check_gate(symbol: str, engine_data: dict, meta: dict) -> dict:
    """执行GO/NO-GO七问，返回通过/拒绝和详情。

    Args:
        symbol: 品种代码 (BTCUSDT, XAUUSD, etc.)
        engine_data: auto_card采集的完整引擎数据
        meta: 分析元数据 (status, direction, rr_a, rr_b, etc.)

    Returns:
        {
            "go": bool,           # True=通过，False=禁止
            "score": int,         # 绿灯计数 0-7
            "max_score": 7,
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
    tv_data = engine_data.get("_tv_pine") or engine_data.get("tv", {})
    tv_active = bool(tv_data)
    tv_conflict = meta.get("gate_verdict", "").startswith("否决")
    if tv_active and not tv_conflict:
        gates["tv_live"] = {"status": "green", "reason": "TV SVP已读·方向一致"}
    elif tv_active:
        gates["tv_live"] = {"status": "red", "reason": f"TV方向冲突: {meta.get('gate_verdict','')}"}
        red_gates.append("tv_live")
        go = False
    else:
        gates["tv_live"] = {"status": "yellow", "reason": "TV数据未实时读取·降级观察"}
        yellow_gates.append("tv_live")

    # ── 门3: R:R底线 ──
    rr_a = float(meta.get("rr_a") or meta.get("rr1", 0) or 0)
    rr_b = float(meta.get("rr_b") or meta.get("rr2", 0) or 0)
    best_rr = max(rr_a, rr_b) if rr_a or rr_b else 0
    if best_rr >= 2.0:
        gates["rr_ratio"] = {"status": "green", "reason": f"最佳R:R 1:{best_rr:.1f}·≥1:2"}
    elif best_rr >= 1.5:
        gates["rr_ratio"] = {"status": "yellow", "reason": f"R:R 1:{best_rr:.1f}·低于1:2标准"}
        yellow_gates.append("rr_ratio")
    else:
        gates["rr_ratio"] = {"status": "red", "reason": GATE_RULES["rr_ratio"]["red_light"]}
        red_gates.append("rr_ratio")
        go = False

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
    if "通过" in str(prot_status):
        gates["protections"] = {"status": "green", "reason": "Protections全部通过"}
    elif "拦截" in str(prot_status):
        gates["protections"] = {"status": "red", "reason": prot_status}
        red_gates.append("protections")
        go = False
    else:
        gates["protections"] = {"status": "yellow", "reason": f"Protections未完整检测"}
        yellow_gates.append("protections")

    # ── 门6: 样本/WFO ──
    reviews_count = engine_data.get("_reviews_count", 0)
    wfo_efficiency = engine_data.get("_wfo_efficiency", 0)
    if reviews_count >= 20 and wfo_efficiency >= 0.5:
        gates["wfo_samples"] = {"status": "green", "reason": f"样本{reviews_count}·WFO效率{wfo_efficiency:.2f}"}
    elif reviews_count >= 20:
        gates["wfo_samples"] = {"status": "yellow", "reason": f"样本{reviews_count}但WFO效率{wfo_efficiency:.2f}<0.5"}
        yellow_gates.append("wfo_samples")
    else:
        gates["wfo_samples"] = {"status": "yellow", "reason": f"样本仅{reviews_count}<20·WFO置信不足"}
        yellow_gates.append("wfo_samples")

    # ── 门7: 组合暴露 ──
    corr_high = engine_data.get("_corr_high", False)
    total_exposure = engine_data.get("_total_exposure_pct", 0)
    if not corr_high and total_exposure <= 15:
        gates["portfolio_exposure"] = {"status": "green", "reason": f"相关≤0.7·暴露{total_exposure:.1f}%"}
    elif not corr_high:
        gates["portfolio_exposure"] = {"status": "yellow", "reason": f"暴露{total_exposure:.1f}%偏高"}
        yellow_gates.append("portfolio_exposure")
    else:
        gates["portfolio_exposure"] = {"status": "red", "reason": GATE_RULES["portfolio_exposure"]["red_light"]}
        red_gates.append("portfolio_exposure")
        go = False

    green_count = sum(1 for g in gates.values() if g["status"] == "green")
    yellow_count = len(yellow_gates)
    red_count = len(red_gates)
    
    verdict = (
        f"✅ GO · 绿灯{green_count}/7"
        if go
        else f"✗ NO-GO · 红灯{red_count}灯·{'/'.join(red_gates[:3])}"
    )

    return {
        "go": go,
        "score": green_count,
        "max_score": 7,
        "red_gates": red_gates,
        "yellow_gates": yellow_gates,
        "green_count": green_count,
        "red_count": red_count,
        "yellow_count": yellow_count,
        "gates": gates,
        "verdict": verdict,
        "timestamp": now,
    }


def gate_report_card(result: dict, symbol: str) -> str:
    """生成GO/NO-GO报告卡（追加到分析卡尾部）。"""
    if result["go"]:
        emoji = "✅"
        status_text = "GO · 允许执行"
    else:
        emoji = "✗"
        status_text = "NO-GO · 禁止执行"

    lines = [
        "",
        "### GO/NO-GO 下单闸门",
        "",
        f"{emoji} **{status_text}** · 绿灯{result['green_count']}/7",
        "",
        "| # | 闸门 | 状态 | 原因 |",
        "|---:|---|---|---|",
    ]
    
    gate_order = ["data_freshness", "tv_live", "rr_ratio", "event_window", 
                  "protections", "wfo_samples", "portfolio_exposure"]
    
    for i, gate_name in enumerate(gate_order, 1):
        g = result["gates"].get(gate_name, {})
        status = g.get("status", "—")
        reason = g.get("reason", "—")
        name = GATE_RULES.get(gate_name, {}).get("description", gate_name)
        
        emoji_map = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        status_emoji = emoji_map.get(status, "⚪")
        lines.append(f"| {i} | {status_emoji} {name} | {status.upper()} | {reason} |")
    
    lines.append("")
    lines.append(f"**裁决**: {result['verdict']}")
    if result["red_gates"]:
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
