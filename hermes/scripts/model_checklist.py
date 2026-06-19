#!/usr/bin/env python3
"""
棠溪 · 模型 Checklist 校验器 v1.0
输入：模型类型 + 方向 + 关键价格
输出：通用入口 + 模型特定 checklist 逐项勾选结果。
"""

import json, sys

# ═══════════════════════════════════════
# 通用入口检查（所有模型必过）
# P0: R:R 硬校验 — 不合格直接 X 禁做，不进入模型特定检查
# ═══════════════════════════════════════

COMMON_CHECKS = [
    {"id": "rr_hard", "label": "R:R≥1:2硬底线·不合格→X禁做", "fn": lambda ctx: ctx.get("rr", 0) >= 2.0, "fatal": True},
    {"id": "data_grade", "label": "数据等级≥B", "fn": lambda ctx: ctx.get("data_grade", "C") in ("A", "B")},
    {"id": "no_event_ban", "label": "无重大事件前30分钟禁做", "fn": lambda ctx: not ctx.get("event_ban", False)},
    {"id": "daily_loss", "label": "日损未达30U上限", "fn": lambda ctx: ctx.get("daily_loss", 0) < 30},
    {"id": "consecutive_loss", "label": "连续亏损<3笔", "fn": lambda ctx: ctx.get("consecutive_losses", 0) < 3},
    {"id": "price_distance", "label": "入场价离现价≤0.5ATR", "fn": lambda ctx: abs(ctx.get("entry", 0) - ctx.get("current_price", 0)) <= ctx.get("atr", 0) * 0.5},
    {"id": "htf_aligned", "label": "4h/1h与执行方向不冲突", "fn": lambda ctx: not ctx.get("htf_conflict", False)},
    {"id": "cvd_quality", "label": "CVD质量≥B·若C则自动降权半仓", "fn": lambda ctx: ctx.get("cvd_quality", "B") in ("A", "B")},
    {"id": "five_model_only", "label": "日内执行入口限定五类固定模型", "fn": lambda ctx: ctx.get("model_name", "") in ("VWAP反抽", "VAH回收", "VAL回收", "POC拒绝", "扫流动性回收", "突破接受")},
]

# ═══════════════════════════════════════
# 模型特定检查
# ═══════════════════════════════════════

MODEL_CHECKS = {
    "VWAP反抽": {
        "入场前": [
            ("4h/1h方向同向", lambda c: not c.get("htf_conflict", False)),
            ("价格≤0.5ATR离VWAP", lambda c: abs(c.get("current_price", 0) - c.get("vwap", 0)) <= c.get("atr", 0) * 0.5),
            ("前段趋势无衰竭", lambda c: not c.get("trend_exhaustion", False)),
            ("止损VWAP外侧,R:R≥1:2", lambda c: c.get("rr", 0) >= 2.0),
        ],
        "触发": [
            ("触碰VWAP后拒绝", lambda c: c.get("vwap_rejection", False)),
            ("5m/15m不重新接受VWAP", lambda c: c.get("no_vwap_accept", False)),
            ("Taker/CVD不冲突", lambda c: c.get("cvd_ok", False)),
        ],
        "确认": [
            ("顺向K线重启", lambda c: c.get("trend_resume", False)),
            ("反向衰竭", lambda c: c.get("exhaustion", False)),
            ("不破确认位", lambda c: c.get("level_held", False)),
        ],
    },
    "VAH回收": {
        "入场前": [
            ("价格打出VAH上方", lambda c: c.get("above_vah", False)),
            ("未形成接受", lambda c: not c.get("acceptance", False)),
            ("CVD未顺向放大", lambda c: not c.get("cvd_expanding", False)),
            ("止损扫出极值外,R:R≥1:2", lambda c: c.get("rr", 0) >= 2.0),
        ],
        "触发": [
            ("回到价值区内", lambda c: c.get("back_in_va", False)),
            ("5m/15m收线确认", lambda c: c.get("bar_confirmed", False)),
            ("扫出后不延续", lambda c: c.get("no_continuation", False)),
        ],
        "确认": [
            ("不再跌回区外", lambda c: c.get("holds_in_va", False)),
            ("CVD背离/转向", lambda c: c.get("cvd_turn", False)),
            ("目标≥POC", lambda c: c.get("target_visible", False)),
        ],
    },
    "VAL回收": {
        "入场前": [
            ("价格打出VAL下方", lambda c: c.get("below_val", False)),
            ("未形成接受", lambda c: not c.get("acceptance", False)),
            ("CVD未顺向放大", lambda c: not c.get("cvd_expanding", False)),
            ("止损扫出极值外,R:R≥1:2", lambda c: c.get("rr", 0) >= 2.0),
        ],
        "触发": [
            ("回到价值区内", lambda c: c.get("back_in_va", False)),
            ("5m/15m收线确认", lambda c: c.get("bar_confirmed", False)),
            ("扫出后不延续", lambda c: c.get("no_continuation", False)),
        ],
        "确认": [
            ("不再涨回区外", lambda c: c.get("holds_in_va", False)),
            ("CVD背离/转向", lambda c: c.get("cvd_turn", False)),
            ("目标≥POC", lambda c: c.get("target_visible", False)),
        ],
    },
    "POC拒绝": {
        "入场前": [
            ("价格在POC附近", lambda c: abs(c.get("current_price", 0) - c.get("poc", 0)) <= c.get("atr", 0) * 0.5),
            ("非强趋势单边", lambda c: not c.get("strong_trend", False)),
            ("拒绝空间明确", lambda c: c.get("rejection_space", False)),
            ("止损POC外侧,R:R≥1:2", lambda c: c.get("rr", 0) >= 2.0),
        ],
        "触发": [
            ("触碰POC后失败", lambda c: c.get("poc_fail", False)),
            ("拒绝K/反向成交", lambda c: c.get("rejection_bar", False)),
            ("POC未连续收复", lambda c: c.get("no_poc_reclaim", False)),
        ],
        "确认": [
            ("离开POC区域", lambda c: c.get("leaving_poc", False)),
            ("量支持反向", lambda c: c.get("volume_backing", False)),
            ("CVD不反向冲突", lambda c: c.get("cvd_ok", False)),
        ],
    },
    "扫流动性回收": {
        "入场前": [
            ("接近前高/前低/止损池", lambda c: c.get("near_liquidity", False)),
            ("高周期无强烈反向压制", lambda c: not c.get("htf_opposition", False)),
            ("扫出后主动成交衰竭", lambda c: c.get("sweep_exhaustion", False)),
            ("止损扫出极值外,R:R≥1:2", lambda c: c.get("rr", 0) >= 2.0),
        ],
        "触发": [
            ("刺破关键高/低", lambda c: c.get("wicked_through", False)),
            ("刺破后快速收回", lambda c: c.get("quick_reclaim", False)),
            ("5m/15m收在关键位内侧", lambda c: c.get("bar_inside", False)),
        ],
        "确认": [
            ("CVD背离/Taker追单失败", lambda c: c.get("cvd_divergence", False)),
            ("不二次跌破/突破扫点", lambda c: c.get("no_second_sweep", False)),
            ("反向结构突破", lambda c: c.get("reverse_structure", False)),
        ],
    },
    "突破接受": {
        "入场前": [
            ("接近VAH/VAL/VWAP/结构位", lambda c: c.get("near_structure", False)),
            ("高周期支持方向", lambda c: not c.get("htf_conflict", False)),
            ("突破前不衰竭", lambda c: not c.get("pre_break_exhaustion", False)),
            ("回踩至止损R:R≥1:2", lambda c: c.get("rr", 0) >= 2.0),
        ],
        "触发": [
            ("突破关键位", lambda c: c.get("broke_level", False)),
            ("5m/15m站稳外侧", lambda c: c.get("held_outside", False)),
            ("回踩不破", lambda c: c.get("retest_held", False)),
        ],
        "确认": [
            ("CVD/Taker顺向", lambda c: c.get("cvd_aligned", False)),
            ("OI增加不过挤", lambda c: c.get("oi_healthy", False)),
            ("回踩后二次启动", lambda c: c.get("second_leg", False)),
        ],
    },
}

def run_checklist(model_name, context):
    """运行完整checklist。fatally failed checks abort immediately with X禁做"""
    results = {
        "model": model_name,
        "common": [],
        "model_specific": {},
        "all_pass": True,
        "fatal_failure": None,
        "verdict": "PENDING",
    }
    
    # 通用入口
    for check in COMMON_CHECKS:
        passed = check["fn"](context)
        results["common"].append({"id": check["id"], "label": check["label"], "pass": passed, "fatal": check.get("fatal", False)})
        if not passed:
            results["all_pass"] = False
            if check.get("fatal"):
                results["fatal_failure"] = check["id"]
                results["verdict"] = "X禁做 · " + check["label"]
                return results  # 立即中止，不检查后续
    
    # 模型特定
    if model_name in MODEL_CHECKS:
        for phase, checks in MODEL_CHECKS[model_name].items():
            phase_results = []
            for label, fn in checks:
                passed = fn(context)
                phase_results.append({"label": label, "pass": passed})
                if not passed:
                    results["all_pass"] = False
            results["model_specific"][phase] = phase_results
    
    results["verdict"] = "全部通过 → 可执行" if results["all_pass"] else "未全部通过 → B等待或X禁做"
    return results

def format_checklist(results):
    """格式化输出"""
    lines = []
    
    # 致命判定
    if results.get("fatal_failure"):
        lines.append(f"⛔ {results['verdict']}")
        for c in results["common"]:
            if c["id"] == results["fatal_failure"]:
                lines.append(f"  ✗ {c['label']}  ← 致命·立即中止")
        return "\n".join(lines)
    
    # 通用
    common_pass = sum(1 for c in results["common"] if c["pass"])
    common_total = len(results["common"])
    lines.append(f"通用入口：{common_pass}/{common_total} {'✓' if common_pass == common_total else '✗'}")
    for c in results["common"]:
        lines.append(f"  {'☑' if c['pass'] else '☐'} {c['label']}")
    
    # 模型特定
    for phase, checks in results["model_specific"].items():
        phase_pass = sum(1 for c in checks if c["pass"])
        phase_total = len(checks)
        lines.append(f"{phase}：{phase_pass}/{phase_total} {'✓' if phase_pass == phase_total else '✗'}")
        for c in checks:
            lines.append(f"  {'☑' if c['pass'] else '☐'} {c['label']}")
    
    lines.append(f"\n总体：{results['verdict']}")
    
    return "\n".join(lines)

# ═══════════════════════════════════════
# 交互模式
# ═══════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="模型Checklist校验器")
    parser.add_argument("--model", required=True, help="模型类型")
    parser.add_argument("--context", default="{}", help="JSON上下文")
    args = parser.parse_args()
    
    ctx = json.loads(args.context)
    results = run_checklist(args.model, ctx)
    print(format_checklist(results))
    print("\n--- JSON ---")
    print(json.dumps(results, ensure_ascii=False, indent=2))
