#!/usr/bin/env python3
"""Daily Hermes official update maintenance task.

Runs as a no-agent cron script. It is intentionally conservative:
- records local Hermes source git state first
- asks Hermes updater to make its own backup
- never hard-resets local edits
- prints only a compact report for Telegram delivery
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
HERMES_HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / "AppData" / "Local" / "hermes")
SOURCE = HERMES_HOME / "hermes-agent"
LOG_DIR = HERMES_HOME / "maintenance-logs"


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 999, repr(exc)


def compact(text: str, limit: int = 1200) -> str:
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    return text[-limit:] if len(text) > limit else text


def main() -> int:
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report: list[str] = [f"每日Hermes官方升级 · {now}"]

    if not SOURCE.exists():
        report.append(f"状态：跳过 · 官方源码目录不存在 {SOURCE}")
        print("\n".join(report))
        return 0

    git_state = ""
    if (SOURCE / ".git").exists():
        code, git_state = run(["git", "status", "--short"], SOURCE, timeout=60)
        report.append(f"源码：git目录 · 本地改动 {len([x for x in git_state.splitlines() if x.strip()])} 项")
        (LOG_DIR / f"hermes-update-git-status-{datetime.now(TZ).strftime('%Y%m%d')}.txt").write_text(git_state, encoding="utf-8")
    else:
        report.append("源码：非git目录 · 仅执行 hermes update")

    check_code, check_out = run(["python", "-m", "hermes_cli.main", "update", "--check"], timeout=300)
    report.append(f"检查：exit {check_code}")
    if check_out:
        report.append(compact(check_out, 600))

    update_code, update_out = run(["python", "-m", "hermes_cli.main", "update", "--yes", "--backup"], timeout=1200)
    log_file = LOG_DIR / f"hermes-update-{datetime.now(TZ).strftime('%Y%m%d-%H%M%S')}.log"
    log_file.write_text(update_out, encoding="utf-8")
    report.append(f"升级：{'成功' if update_code == 0 else '失败'} · exit {update_code}")
    report.append(f"日志：{log_file}")
    if update_code != 0:
        report.append(compact(update_out, 900))

    print("\n".join(report))
    return 0 if update_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
