#!/usr/bin/env python3
"""TV信号监控 cron wrapper v1.1 — 零输出静默模式。
   tv_signal_monitor.py 内部已处理 Telegram 推送，wrapper 不再重复输出。
   只有异常时才打印错误。
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "hermes" / "scripts" / "tv_signal_monitor.py"

if not SCRIPT.exists():
    print(f"ERROR: {SCRIPT} not found")
    sys.exit(1)

cp = subprocess.run(
    [sys.executable, str(SCRIPT)] + sys.argv[1:],
    cwd=str(ROOT),
    capture_output=True, text=True, timeout=30
)

# 只在异常时输出（tv_signal_monitor.py 内部已推 Telegram）
if cp.returncode != 0:
    print(f"TV信号监控异常(rc={cp.returncode}): {cp.stderr[:200]}" if cp.stderr else f"TV信号监控异常(rc={cp.returncode})")
    sys.exit(cp.returncode)

# 零输出 = 静默 = Telegram无消息（正常情况）
