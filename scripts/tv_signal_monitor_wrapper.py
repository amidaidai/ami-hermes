#!/usr/bin/env python3
"""TV信号监控 cron wrapper v1.2 — 完全静默。

规则：
- 正常: stdout/stderr全吞，零输出
- 异常: 仅单行 "⚠ TV采集失败(rc=N): {reason}"
- 不输出诊断/修复过程/DMI表格到 Telegram

tv_signal_monitor.py 内部已负责：
- TV MCP连接
- DMI决策表读取
- 等级变化判定
- Telegram 推送（仅在等级AB变化时）
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import subprocess, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "hermes" / "scripts" / "tv_signal_monitor.py"

if not SCRIPT.exists():
    # 脚本不存在 → 单行错误
    print(f"⚠ TV脚本缺失")
    sys.exit(1)

try:
    cp = subprocess.run(
        [sys.executable, str(SCRIPT)] + sys.argv[1:],
        cwd=str(ROOT),
        capture_output=True, text=True, timeout=30
    )
except subprocess.TimeoutExpired:
    print(f"⚠ TV采集超时30s")
    sys.exit(1)

# 完全静默：脚本退出码 != 0 时只输出单行
if cp.returncode != 0:
    err = cp.stderr.strip()[:80] if cp.stderr else "未知"
    print(f"⚠ TV采集失败(rc={cp.returncode}): {err}")

# 正常: 零输出 = Telegram无消息
