#!/usr/bin/env python3
"""Daily backup of Tangxi Hermes configuration repo to the private remote.

Runs as a no-agent cron script from D:/Hermes agent. It commits tracked changes,
backs up selected ignored tool files into a tracked maintenance backup folder,
and pushes to origin.
"""
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
LOG_DIR = ROOT / "outputs" / "maintenance-logs"
BACKUP_DIR = ROOT / "hermes" / "scripts" / "repo-maintenance" / "backups"
IGNORED_TOOL_BACKUPS = [
    (ROOT / "tools" / "binance-mcp" / "server.py", BACKUP_DIR / "binance-mcp-server.py"),
]


def run(cmd: list[str], cwd: Path = ROOT, timeout: int = 600) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 999, repr(exc)


def compact(text: str, limit: int = 1000) -> str:
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    return text[-limit:] if len(text) > limit else text


def backup_ignored_tools() -> list[str]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    copied = []
    for src, dst in IGNORED_TOOL_BACKUPS:
        if src.exists():
            shutil.copy2(src, dst)
            copied.append(str(dst.relative_to(ROOT)))
    return copied


def main() -> int:
    now = datetime.now(TZ)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report = [f"每日私人仓库备份 · {now.strftime('%Y-%m-%d %H:%M:%S')}"]

    if not (ROOT / ".git").exists():
        report.append(f"状态：失败 · 非git仓库 {ROOT}")
        print("\n".join(report))
        return 1

    copied = backup_ignored_tools()
    if copied:
        report.append("忽略文件备份：" + "、".join(copied))

    code, remote = run(["git", "remote", "-v"], timeout=60)
    report.append("远端：" + compact(remote, 300))

    run(["git", "add", "-A"], timeout=120)
    code, status = run(["git", "status", "--short"], timeout=60)
    status_lines = [line for line in status.splitlines() if line.strip()]
    report.append(f"待提交：{len(status_lines)} 项")

    if not status_lines:
        report.append("提交：跳过 · 无改动")
    else:
        msg = f"chore: daily hermes backup {now.strftime('%Y-%m-%d')}"
        commit_code, commit_out = run(["git", "commit", "-m", msg], timeout=300)
        report.append(f"提交：{'成功' if commit_code == 0 else '失败'} · exit {commit_code}")
        if commit_code != 0:
            report.append(compact(commit_out, 900))
            print("\n".join(report))
            return 1

    push_code, push_out = run(["git", "push", "origin", "main"], timeout=600)
    log_file = LOG_DIR / f"private-backup-{now.strftime('%Y%m%d-%H%M%S')}.log"
    log_file.write_text(push_out, encoding="utf-8")
    report.append(f"推送：{'成功' if push_code == 0 else '失败'} · exit {push_code}")
    report.append(f"日志：{log_file}")
    if push_code != 0:
        report.append(compact(push_out, 900))

    # 维护类任务：只在真正发生提交/推送或失败时输出，避免每天“无改动”刷屏。
    if status_lines or push_code != 0 or copied:
        print("\n".join(report))
    return 0 if push_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
