#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日学习·社区进化 — cron wrapper"""
import subprocess, sys
from pathlib import Path
ROOT = Path("D:/Hermes agent")
cp = subprocess.run([sys.executable, str(ROOT / "scripts" / "daily_learn.py"), "--push"], cwd=str(ROOT), capture_output=True, text=True, timeout=30)
if cp.returncode != 0:
    print(f"⚠ 每日学习失败: {cp.stderr[:120]}")
