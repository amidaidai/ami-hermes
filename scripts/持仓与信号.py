#!/usr/bin/env python3
"""持仓与信号 v1.3 — 合并持仓监测 + 信号巡检，5m 一次。
   · 有变化才输出，静默时零消息（减少Telegram刷屏）
   · cron控制8-23点运行
"""
import subprocess, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

STEPS = [
    ("pos", "持仓监测.py", 30),
    ("sig", "信号巡检.py", 90),
]

outputs = []
for name, script, timeout in STEPS:
    try:
        cp = subprocess.run(
            [sys.executable, str(SCRIPTS / script)],
            capture_output=True, text=True, timeout=timeout,
        )
        out = cp.stdout.strip()
        if out:
            outputs.append(out)
        if cp.stderr.strip():
            print(f"⚠ {name}: {cp.stderr.strip()[:120]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"⚠ {name} 超时({timeout}s)", file=sys.stderr)
    except Exception as e:
        print(f"⚠ {name}: {e}", file=sys.stderr)

if outputs:
    print("\n".join(outputs))
# 静默时零输出 = Telegram无消息
