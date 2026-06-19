#!/usr/bin/env python3
"""信号巡检 v4.0 — 事件转发、心跳检查、结构刷新提醒。"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from monitor_display import display_plan, format_level_block, lab, seq, situation_text

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
EVENT_FILE = DATA / "monitor_events.json"
LEVELS_FILE = DATA / "monitor_levels.json"
HEARTBEAT_FILE = DATA / "monitor_heartbeat.json"
REFRESH_FILE = DATA / "structure_refresh_requests.jsonl"
STATE_FILE = DATA / "monitor_state.json"
SYSTEM_EVENT_FILE = DATA / "system_events.jsonl"
GOVERNANCE_FILE = DATA / "strategy_governance.json"
RISK_FILE = DATA / "risk_state.json"

HEARTBEAT_STALE_SECONDS = 45
EXPECTED_PYTHON_CHAIN_MAX = 2
NOISE_SUMMARY_SECONDS = 3 * 3600
MACRO_REFRESH_SECONDS = 5 * 60
HEALTH_REFRESH_SECONDS = 10 * 60


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
    except Exception:
        return None


def risk_line(event: dict[str, Any]) -> str:
    gate = event.get("risk_gate") or {}
    if not gate:
        return "未记录"
    allowed = "允许" if gate.get("allowed") else "禁止"
    reasons = "；".join(gate.get("reasons", []))
    return f"{allowed} · {gate.get('tier', '未知')} · 最大风险 `{gate.get('max_risk_usd', 0)}U` · {reasons}"


def derivatives_line(event: dict[str, Any]) -> str:
    d = event.get("derivatives") or {}
    if not d:
        return "未记录"
    return d.get("interpretation") or "已记录"


def confidence_line(event: dict[str, Any]) -> str:
    """v9.7 置信格式：评分/13 → 公式 → 置信 n/5"""
    c = event.get("confidence") or {}
    if not c:
        return "未验证"
    score = c.get("score") or 0
    quality = c.get("quality") or "C"
    label = c.get("label") or "未验证"
    # 尝试 v9.7 格式
    conf_n = c.get("confidence_n")
    formula = c.get("formula")
    if conf_n and formula:
        return f"置信 {conf_n}/5 · {formula}"
    # 兼容旧格式
    spread = c.get("spread_pct")
    spread_txt = f" · 价差{spread:.3f}%" if isinstance(spread, (int, float)) else ""
    return f"{quality}级 · {score}% · {label}{spread_txt}"


def normalize_hit(price: float, hit: Any, index: int) -> str:
    if not isinstance(hit, dict):
        return ""
    return format_level_block(price, hit, index)


def pending_refresh_requests(limit: int = 3) -> list[dict[str, Any]]:
    if not REFRESH_FILE.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in REFRESH_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("status") == "pending":
            rows.append(row)
    return rows[-limit:]


def monitor_python_process_count() -> int:
    cmd = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -ieq 'python.exe' -and $_.CommandLine -like '*-u*D:/Hermes agent/scripts/*' } | "
        "Measure-Object | Select-Object -ExpandProperty Count"
    )
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=12).stdout.strip()
        return int(out or 0)
    except Exception:
        return -1



def recent_system_anomalies(limit: int = 5) -> list[dict[str, Any]]:
    if not SYSTEM_EVENT_FILE.exists():
        return []
    rows = []
    cutoff = datetime.now().astimezone().timestamp() - 15 * 60
    for line in SYSTEM_EVENT_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        ts = parse_dt(row.get("time"))
        if row.get("type") == "market_data_anomaly" and ts and ts.timestamp() >= cutoff:
            rows.append(row)
    return rows[-limit:]


def governance_findings() -> list[str]:
    findings: list[str] = []
    risk = read_json(RISK_FILE, {})
    if risk.get("requires_review") or int(risk.get("unreviewed_trade_count", 0) or 0) > 0:
        findings.append(f"存在未复盘成交：{risk.get('unreviewed_trade_count', 0)} 笔，下一笔最高轻仓")
    gov = read_json(GOVERNANCE_FILE, {})
    rules = gov.get("rules") or {}
    for name, row in rules.items():
        status = row.get("status")
        if status in {"retired", "testing"}:
            findings.append(f"模型治理：{name} · {status} · {row.get('decision', '等待样本')}")
    return findings[-5:]

def smart_update_targets(levels: dict[str, Any]) -> list[str]:
    targets: set[str] = set()
    for req in pending_refresh_requests(limit=20):
        if req.get("symbol"):
            targets.add(str(req["symbol"]))
    for symbol, block in (levels.get("symbols") or {}).items():
        active = [x for x in block.get("levels", []) if x.get("status", "active") == "active"]
        if block.get("needs_structure_refresh") or (block.get("monitor_enabled", True) and len(active) < 2):
            targets.add(symbol)
    return sorted(targets)


def run_smart_update(levels: dict[str, Any]) -> str:
    targets = smart_update_targets(levels)
    if not targets:
        return ""
    cmd = [sys.executable, str(SCRIPT_DIR / "智能更新结构.py"), *targets]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout.strip()
        return out or ("智能更新完成：" + "、".join(targets))
    except Exception as e:
        return f"智能更新失败：{e}"


def health_findings(levels: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    hb = read_json(HEARTBEAT_FILE, {})
    hb_time = parse_dt(hb.get("time"))
    if not hb_time:
        findings.append("主监控心跳缺失：需要重启 行情守望")
    else:
        age = (datetime.now().astimezone() - hb_time).total_seconds()
        if age > HEARTBEAT_STALE_SECONDS:
            findings.append(f"主监控心跳过旧：{age:.0f}s 未刷新")
    count = monitor_python_process_count()
    if count > EXPECTED_PYTHON_CHAIN_MAX:
        findings.append(f"疑似重复监控进程：python链 {count} 个")
    elif count < 1:
        findings.append("未发现主监控 python 进程")
    for symbol, block in (levels.get("symbols") or {}).items():
        active = [x for x in block.get("levels", []) if x.get("status", "active") == "active"]
        if block.get("needs_structure_refresh"):
            findings.append(f"{symbol} 需要刷新结构：{block.get('refresh_reason', '触发后旧结构降权')}")
        if block.get("monitor_enabled", True) and len(active) < 2:
            findings.append(f"{symbol} 活跃关键位不足：仅 {len(active)} 个")
    for req in pending_refresh_requests():
        findings.append(f"刷新队列：{req.get('symbol')} · {'；'.join(req.get('reasons', []))}")
    for row in recent_system_anomalies(limit=3):
        findings.append(f"数据异常：{row.get('symbol')} · {'；'.join(row.get('issues', []))}")
    findings.extend(governance_findings())
    return findings


def render_event(event: dict[str, Any], levels: dict[str, Any]) -> str:
    price = float(event.get("price", 0))
    symbol = event.get("symbol") or levels.get("symbol") or "BTCUSDT"
    plan_id = event.get("plan_id") or levels.get("plan_id") or "—"
    levels_hit = event.get("levels", [])
    cvd = event.get("cvd", "")
    cvd_quality = event.get("cvd_quality", "")
    tier = event.get("tier") or ("warning" if "breach" in event.get("type", "") else "info")
    heads = {"critical": "🔴 紧急 · {symbol} 关键位触发", "warning": "🔴 {symbol} 关键位触发", "info": "🟡 {symbol} 接近计划位", "invalidated": "🔵 {symbol} 计划失效", "expired": "🔵 {symbol} 监控位过期"}
    actions = {"critical": "立即按计划确认", "warning": "尽快看5m确认", "info": "可等待触发", "invalidated": "旧计划已失效，等新分析刷新", "expired": "旧监控位已过期，不再按旧计划执行"}
    head = heads.get(tier, heads["info"]).format(symbol=symbol)
    action = actions.get(tier, actions["info"])
    if event.get("risk_gate") and not event["risk_gate"].get("allowed", True):
        action = "风控禁止开新仓，只允许观察或管理已有仓位"
    cycle = event.get("analysis_cycle") or (levels.get("symbols", {}).get(symbol, {}).get("analysis_cycle")) or levels.get("analysis_cycle", "—")
    lines = [head]
    lines.append(f"① {lab('品种')}{symbol}")
    lines.append(f"② {lab('价格')}`{price:.0f}`")
    lines.append(f"③ {lab('置信')}{confidence_line(event)}")
    lines.append(f"④ {lab('计划')}{display_plan(plan_id, symbol)}")
    lines.append(f"⑤ {lab('现状')}{situation_text(tier)}")
    next_idx = 6
    if cvd and cvd != "unknown":
        suffix = f" · {cvd_quality}" if cvd_quality else ""
        lines.append(f"{seq(next_idx)} {lab('CVD')}{cvd}{suffix}")
        next_idx += 1
    if event.get("derivatives"):
        lines.append(f"{seq(next_idx)} {lab('衍生')}{derivatives_line(event)}")
        next_idx += 1
    if event.get("risk_gate"):
        lines.append(f"{seq(next_idx)} {lab('风控')}{risk_line(event)}")
        next_idx += 1
    if isinstance(levels_hit, list) and levels_hit:
        lines.append("—— 触发细节 ——")
        for i, hit in enumerate(levels_hit, start=next_idx):
            lines.append(normalize_hit(price, hit, i))
        next_idx += len(levels_hit)
    if event.get("refresh_request"):
        lines.append(f"{seq(next_idx)} {lab('刷新')}已加入结构刷新队列")
        next_idx += 1
    lines.append("—— 执行结论 ——")
    lines.append(f"{seq(next_idx)} {lab('周期')}{cycle}")
    lines.append(f"{lab('动作')}{action}")
    lines.append(f"{lab('提示')}说「分析 {symbol.replace('USDT', '')}」刷新完整卡")
    return "\n".join(lines)




def maybe_run_99_maintenance(state: dict[str, Any]) -> list[str]:
    now_ts = datetime.now().timestamp()
    outputs: list[str] = []
    last_macro = float(state.get("last黄金宏观刷新", 0) or 0)
    if now_ts - last_macro > MACRO_REFRESH_SECONDS:
        try:
            subprocess.run([sys.executable, str(SCRIPT_DIR / "黄金宏观.py")], capture_output=True, text=True, timeout=45)
            state["last黄金宏观刷新"] = now_ts
            outputs.append("黄金宏观层已刷新")
        except Exception as e:
            outputs.append(f"黄金宏观层刷新失败：{e}")
    last_health = float(state.get("last系统体检", 0) or 0)
    if now_ts - last_health > HEALTH_REFRESH_SECONDS:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        def _run_script(fname, timeout):
            subprocess.run([sys.executable, str(SCRIPT_DIR / fname)], capture_output=True, text=True, timeout=timeout)
        jobs = [("模型统计.py", 30), ("安全审计.py", 45)]
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {pool.submit(_run_script, f, t): f for f, t in jobs}
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        outputs.append(f"{futures[future]}失败：{e}")
            # 模型统计和安全审计完成后，再跑系统体检（依赖前两者输出）
            subprocess.run([sys.executable, str(SCRIPT_DIR / "系统体检.py")], capture_output=True, text=True, timeout=60)
            subprocess.run([sys.executable, str(SCRIPT_DIR / "清理守护.py")], capture_output=True, text=True, timeout=60)
            state["last系统体检"] = now_ts
            outputs.append("模型统计、安全审计、系统体检和清理守护已刷新")
        except Exception as e:
            outputs.append(f"系统体检失败：{e}")
    write_json(STATE_FILE, state)
    return outputs


def render_noise_summary(state: dict[str, Any]) -> str:
    rows = state.get("noise_history") or []
    now_ts = datetime.now().timestamp()
    recent = [x for x in rows if now_ts - float(x.get("time", 0)) < NOISE_SUMMARY_SECONDS]
    if not recent:
        return ""
    last = state.setdefault("last降噪摘要", {})
    if now_ts - float(last.get("time", 0)) < NOISE_SUMMARY_SECONDS:
        return ""
    by_symbol: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    for row in recent:
        by_symbol[str(row.get("symbol") or "未知")] = by_symbol.get(str(row.get("symbol") or "未知"), 0) + 1
        reason = str(row.get("reason") or "未记录")
        by_reason[reason] = by_reason.get(reason, 0) + 1
    symbol_txt = "；".join(f"{k} {v}个" for k, v in sorted(by_symbol.items()))
    reason_txt = "；".join(f"{k} {v}次" for k, v in sorted(by_reason.items(), key=lambda x: -x[1])[:3])
    last.update({"time": now_ts, "count": len(recent)})
    write_json(STATE_FILE, state)
    return "\n".join([
        "🔵 信号巡检 · 降噪摘要",
        f"① {lab('过滤')}近3小时过滤 `{len(recent)}` 个低确认事件",
        f"② {lab('品种')}{symbol_txt}",
        f"③ {lab('原因')}{reason_txt}",
        f"{lab('动作')}只保留强确认警报；需要细看可说「查降噪日志」",
    ])

def render_health(findings: list[str]) -> str:
    lines = ["🔵 信号巡检 · 系统健康提醒"]
    for idx, item in enumerate(findings, start=1):
        lines.append(f"{seq(idx)} {lab('问题')}{item}")
    lines.append(f"{lab('动作')}先处理 P0；必要时说「刷新结构」")
    return "\n".join(lines)


def render_update(output: str) -> str:
    return "\n".join(["🔵 信号巡检 · 智能更新", f"① {lab('结果')}{output}", f"{lab('动作')}已重算近端关键位，等待行情守望继续监控"])


def render_normal_status(levels: dict[str, Any]) -> str:
    symbols = levels.get("symbols") or {}
    enabled = [name for name, block in symbols.items() if isinstance(block, dict) and block.get("monitor_enabled", True) is not False]
    return "\n".join([
        "🟢 信号巡检 · 监控正常",
        f"① {lab('状态')}行情守望在线，暂无强确认告警",
        f"② {lab('品种')}{'、'.join(enabled) if enabled else '无'}",
        f"③ {lab('说明')}10s查价不等于10s推送；低位信/弱确认会记录不推送",
        f"{lab('动作')}若要看静默原因，说「查降噪日志」",
    ])


def main() -> None:
    levels = read_json(LEVELS_FILE, {})
    update_output = run_smart_update(levels)
    if update_output:
        levels = read_json(LEVELS_FILE, {})
    findings = health_findings(levels)
    events = read_json(EVENT_FILE, [])
    new_events = [e for e in events if isinstance(e, dict) and not e.get("notified", False)]
    if new_events:
        for e in events:
            if isinstance(e, dict):
                e["notified"] = True
        write_json(EVENT_FILE, events)
        # 推送所有新事件，不再只推第一条
        for evt in new_events:
            print(render_event(evt, levels))
        return
    if update_output:
        print(render_update(update_output))
        return
    state = read_json(STATE_FILE, {})
    maintenance = maybe_run_99_maintenance(state)
    if maintenance:
        findings.extend(maintenance)
    noise_summary = render_noise_summary(state)
    if noise_summary:
        print(noise_summary)
        return
    if findings:
        state = read_json(STATE_FILE, {})
        last = state.setdefault("last巡检提醒", {})
        key = "|".join(findings[:3])
        now_ts = datetime.now().timestamp()
        if last.get("key") != key or now_ts - float(last.get("time", 0)) > 900:
            last.update({"key": key, "time": now_ts})
            write_json(STATE_FILE, state)
            print(render_health(findings[:6]))
        return
    state = read_json(STATE_FILE, {})
    now_ts = datetime.now().timestamp()
    last_ok = float(state.get("last正常巡检提醒", 0) or 0)
    if now_ts - last_ok > 1800:
        state["last正常巡检提醒"] = now_ts
        write_json(STATE_FILE, state)
        print(render_normal_status(levels))


if __name__ == "__main__":
    main()
