#!/usr/bin/env python3
"""安全审计 v1.0 — 交易系统最小权限和自动化暴露面检查。"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import trading_system as ts

OUT = ts.DATA_DIR / "security_audit.json"

HIGH_POWER = {"terminal", "file", "browser", "computer_use", "discord_admin", "feishu_drive", "homeassistant", "cronjob"}


def run(cmd: list[str]) -> str:
    try:
        p = subprocess.run(cmd, cwd=str(ts.ROOT), text=True, encoding="utf-8", errors="ignore", capture_output=True, timeout=60)
        return (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return str(e)


def enabled_toolsets() -> list[str]:
    out = run([sys.executable, "-m", "hermes_cli.main", "tools", "list"])
    tools = []
    for line in out.splitlines():
        text = line.strip()
        if not text:
            continue
        lower = text.lower()
        if "enabled" in lower or "✓" in text or "[x]" in lower:
            name = text.split()[0].strip("-*✓[]")
            if name:
                tools.append(name)
    return sorted(set(tools))


def main() -> None:
    ts.ensure_files()
    toolsets = enabled_toolsets()
    high = sorted(t for t in toolsets if t in HIGH_POWER)
    findings = []
    score = 100
    if high:
        score -= min(20, len(high) * 3)
        findings.append("default profile 启用了高权限工具，建议后续拆 trading 专用 profile")
    cron = run([sys.executable, "-m", "hermes_cli.main", "cron", "list", "--all"])
    has_signal_job = ("持仓与信号" in cron or "信号巡检" in cron) and "no-agent" in cron
    if not has_signal_job:
        score -= 12
        findings.append("持仓与信号/信号巡检 cron 非 no-agent 或未发现")
    if not (ts.ROOT / "hermes" / "secrets").exists():
        score -= 5
        findings.append("未发现 hermes/secrets 目录")
    report = {
        "schema": "trading_security_audit_v1",
        "time": ts.now_iso(),
        "score": max(score, 0),
        "grade": "可运行但需隔离" if high else "最小权限较好",
        "enabled_high_power_toolsets": high,
        "findings": findings or ["未发现明显高风险配置"],
        "recommendations": [
            "新建 trading profile，仅保留 terminal/file/cron/messaging/finance MCP 必需能力",
            "交易 cron 保持 no-agent，避免联网内容直接驱动工具调用",
            "长期 skill/memory 更新必须人工确认，不从网页内容直接写入",
        ],
    }
    ts.write_json(OUT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
