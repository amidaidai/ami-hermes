#!/usr/bin/env python3
"""系统体检 v1.1 — 汇总监控、复盘、治理、宏观、数据源和安全状态，给 9.9 成熟度评分。"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import trading_system as ts

OUT = ts.DATA_DIR / "system_health_score.json"


def exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def run_optional(script: str) -> None:
    try:
        subprocess.run([sys.executable, str(SCRIPT_DIR / script)], cwd=str(ts.ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
    except Exception:
        pass


def parse_time(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(text))
    except Exception:
        return None


def main() -> None:
    ts.ensure_files()
    # Refresh derived layers first; health score should inspect current state, not stale files.
    for script in ("黄金宏观.py", "模型统计.py", "安全审计.py"):
        run_optional(script)
    score = 100
    findings = []
    hb = ts.read_json(ts.DATA_DIR / "monitor_heartbeat.json", {})
    hb_time = parse_time(hb.get("time"))
    if hb.get("status") != "running":
        score -= 15; findings.append("行情守望心跳非运行")
    elif hb_time:
        age = (datetime.now().astimezone() - hb_time).total_seconds()
        if age > 45:
            score -= 10; findings.append(f"行情守望心跳过旧：{age:.0f}s")
    risk = ts.read_json(ts.RISK_FILE, {})
    if risk.get("requires_review"):
        score -= 10; findings.append("存在未复盘成交")
    gov = ts.read_json(ts.GOVERNANCE_FILE, {})
    if not gov.get("policy"):
        score -= 10; findings.append("策略治理缺失")
    snap = ts.read_json(ts.SOURCE_FILE, {})
    if not snap.get("history_path") or not Path(snap.get("history_path", "")).exists():
        score -= 10; findings.append("历史快照缺失")
    if snap.get("quality") == "C":
        score -= 3; findings.append("最新快照为C级，需注意单源/弱源")
    xau_macro = ts.read_json(ts.DATA_DIR / "xau_macro_context.json", {})
    if xau_macro.get("quality") != "A":
        score -= 4; findings.append("黄金宏观层非A级或未刷新")
    reviews = ts.load_jsonl(ts.REVIEW_LOG)
    if len(reviews) < 20:
        score -= 7; findings.append(f"真实复盘样本不足：{len(reviews)}/20")
    model_stats = ts.read_json(ts.DATA_DIR / "strategy_model_stats.json", {})
    if not model_stats.get("models"):
        score -= 4; findings.append("模型统计未生成或无模型")
    security = ts.read_json(ts.DATA_DIR / "security_audit.json", {})
    if security.get("enabled_high_power_toolsets"):
        score -= 3; findings.append("安全审计提示：default profile 权限面偏宽")
    levels = ts.read_json(ts.DATA_DIR / "monitor_levels.json", {})
    enabled = [s for s,b in (levels.get("symbols") or {}).items() if b.get("monitor_enabled", True) is not False]
    if set(enabled) != {"BTCUSDT", "XAUUSD"}:
        score -= 5; findings.append(f"主动监控品种非BTC/XAU：{enabled}")
    try:
        subprocess.check_call([sys.executable, "-m", "py_compile", str(SCRIPT_DIR / "行情守望.py"), str(SCRIPT_DIR / "信号巡检.py"), str(SCRIPT_DIR / "trading_system.py"), str(SCRIPT_DIR / "黄金宏观.py"), str(SCRIPT_DIR / "模型统计.py"), str(SCRIPT_DIR / "安全审计.py")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        score -= 15; findings.append("核心脚本编译失败")
    report = {"schema": "system_health_score_v1", "time": ts.now_iso(), "score": max(score, 0), "grade": "9.9架构" if score >= 90 else "待补强", "enabled_symbols": enabled, "findings": findings}
    ts.write_json(OUT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
