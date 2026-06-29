#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -*- coding: utf-8 -*-
"""日间维护 v2.0 — 静默模式·仅异常时输出·cron超时120s内完成"""

import subprocess, sys
from pathlib import Path

PROJECT_ROOT = Path("D:/Hermes agent")
SCRIPTS = Path(__file__).resolve().parent
REPO_SCRIPTS = PROJECT_ROOT / "hermes" / "scripts" / "repo-maintenance"

STEPS = [
    ("Hermes升级", REPO_SCRIPTS / "daily_hermes_official_update.py", 20),
    ("仓库备份", REPO_SCRIPTS / "daily_private_repo_backup.py", 20),
    ("每日验证", SCRIPTS / "run_daily_validation.py", 30),
]

errors = []
for name, script, timeout in STEPS:
    if not script.exists():
        errors.append(f"⚠ {name}: 脚本缺失 {script.name}")
        continue
    try:
        cp = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, timeout=timeout,
        )
        if cp.returncode != 0:
            errors.append(f"⚠ {name}: rc={cp.returncode} {cp.stderr.strip()[:80]}")
    except subprocess.TimeoutExpired:
        errors.append(f"⚠ {name}: 超时({timeout}s)")
    except Exception as e:
        errors.append(f"⚠ {name}: {str(e)[:80]}")

if errors:
    print("\n".join(errors))
# 静默成功 — 零输出
