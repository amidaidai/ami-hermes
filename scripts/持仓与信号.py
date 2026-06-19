#!/usr/bin/env python3
"""持仓与信号 v1.2 — 合并持仓监测 + 信号巡检，5m 一次。
   · 持仓监测：有开平仓变化才输出
   · 信号巡检：心跳/健康/事件/降噪/智能更新
   · 时段：cron 控制 8-23点运行，23-8点睡觉静默
   空仓无变化时静默，两个脚本各自控制是否输出。
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

STEPS = [
    ("持仓监测", "持仓监测.py", 30),
    ("信号巡检", "信号巡检.py", 90),
]

for name, script, timeout in STEPS:
    try:
        cp = subprocess.run(
            [sys.executable, str(SCRIPTS / script)],
            capture_output=True, text=True, timeout=timeout,
        )
        out = cp.stdout.strip()
        if out:
            if len(STEPS) > 1:
                print(f"—— {name} ——")
            print(out)
        if cp.stderr.strip():
            print(f"[{name}] {cp.stderr.strip()}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"⚠ {name} 超时 ({timeout}s)")
    except Exception as e:
        print(f"⚠ {name} 失败: {e}")
