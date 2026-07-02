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
    report = [f"每日私人仓库备份 · {now.strftime('%Y年%m月%d日%H：%M')}"]

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

    commit_code = None
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
        commit_state = "跳过" if not status_lines else ("成功" if "commit_code" in locals() and commit_code == 0 else "失败")
        status_text = "✅成功" if push_code == 0 else "⚠失败"
        mobile_report = [
            f"{status_text} · 每日系统备份 · {now.strftime('%Y年%m月%d日%H：%M')}",
            "",
            "表1 · 任务概况",
            "| 项目 | 数据 | 状态 |",
            "|:----|:----|:----|",
            f"| 任务 | 私仓备份 | {status_text} |",
            f"| 待提交 | `{len(status_lines)}`项 | {'有变更' if status_lines else '无变更'} |",
            f"| 忽略备份 | `{len(copied)}`项 | {'已复制' if copied else '无'} |",
            "",
            "表2 · Git结果",
            "| 模块 | 数据 | 状态 |",
            "|:----|:----|:----|",
            f"| 远端 | origin/main | 已检查 |",
            f"| 提交 | {commit_state} | {'已写入' if status_lines and commit_state == '成功' else '跳过/失败'} |",
            f"| 推送 | exit`{push_code}` | {'✅成功' if push_code == 0 else '⚠失败'} |",
            "",
            "表3 · 处理预案",
            "| 方向 | 触发 | 动作 |",
            "|:---:|:----|:----|",
            f"| {'○完成' if push_code == 0 else '×修复'} | push exit`{push_code}` | {'无需操作' if push_code == 0 else '查看日志'} |",
            f"| ⚠日志 | `{log_file.as_posix()}` | 已落盘 |",
            "| ↑下次 | 明日07：45 | 自动备份 |",
        ]
        print("\n".join(mobile_report))
    return 0 if push_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
