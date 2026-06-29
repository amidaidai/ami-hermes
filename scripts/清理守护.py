#!/usr/bin/env python3
"""v1.0 数据清理守护 — 防止监控事件和快照无限膨胀。

由信号巡检 cron 调用，每次运行执行：
  1. monitor_events.json 只保留 7 天内非 notified 或最近 1000 条
  2. source_snapshots/ 按日归档，保留最近 7 天，删除超过 30 天的
  3. monitor.log 轮转，保留最后 3000 行
"""
from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path("D:/Hermes agent")
DATA_DIR = ROOT / "data"
EVENT_FILE = DATA_DIR / "monitor_events.json"
SNAPSHOT_DIR = DATA_DIR / "source_snapshots"
LOG_FILE = DATA_DIR / "monitor.log"
ARCHIVE_DIR = DATA_DIR / "snapshot_archive"

# 技能完整性护栏：技能根目录（no-agent cron 在桌面运行时执行，LOCALAPPDATA 可用）
SKILLS_ROOT = Path(
    os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))
) / "hermes" / "skills"
_LINE_NUM_PREFIX = re.compile(r"^\d+\|")

MAX_EVENTS = 1000
EVENT_RETENTION_DAYS = 7
SNAPSHOT_RETENTION_DAYS = 7
SNAPSHOT_MAX_AGE_DAYS = 30
LOG_MAX_LINES = 3000


def now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def parse_event_time(tstr: str) -> datetime | None:
    """Parse ISO time strings, return naive datetime."""
    if not tstr:
        return None
    tstr = str(tstr).strip()
    # Strip timezone: convert +08:00, Z, etc. to naive
    try:
        tstr = tstr.replace("Z", "+00:00")
        # Take the part before timezone offset
        idx = tstr.find("+")
        if idx > 0:
            tstr = tstr[:idx]
        # Trim excessive precision
        if "." in tstr and len(tstr) > 26:
            tstr = tstr[:26]
        return datetime.fromisoformat(tstr)
    except Exception:
        return None


def cleanup_events() -> int:
    """清理 monitor_events.json，返回删除条数."""
    if not EVENT_FILE.exists():
        return 0
    try:
        events = json.loads(EVENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if not isinstance(events, list):
        return 0
    original = len(events)
    # Use naive datetime for comparison with parsed event times
    cutoff = datetime.now() - timedelta(days=EVENT_RETENTION_DAYS)
    kept = []
    for e in events:
        t = parse_event_time(str(e.get("time", "")))
        notified = e.get("notified", False) or e.get("push_sent", False)
        # 保留：未通知的 或 7天内的
        if not notified:
            kept.append(e)
        elif t and t > cutoff:
            kept.append(e)
    # 如果还是太多，只保留最近 MAX_EVENTS 条
    if len(kept) > MAX_EVENTS:
        kept = kept[-MAX_EVENTS:]
    removed = original - len(kept)
    if removed > 0:
        EVENT_FILE.write_text(json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8")
    return removed


def cleanup_snapshots() -> tuple[int, int]:
    """清理 source_snapshots/ 目录，返回(归档数, 删除数)."""
    if not SNAPSHOT_DIR.exists():
        return 0, 0
    now_dt = now()
    archive_count = 0
    delete_count = 0
    for child in sorted(SNAPSHOT_DIR.iterdir()):
        if not child.is_dir():
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})", child.name)
        if not m:
            continue
        try:
            date = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=now_dt.tzinfo)
        except ValueError:
            continue
        age = (now_dt - date).days
        if age > SNAPSHOT_MAX_AGE_DAYS:
            try:
                shutil.rmtree(child)
                delete_count += 1
            except Exception:
                pass
        elif age > SNAPSHOT_RETENTION_DAYS:
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            archive_path = ARCHIVE_DIR / child.name
            if not (ARCHIVE_DIR / f"{child.name}.zip").exists():
                try:
                    shutil.make_archive(
                        str(archive_path),
                        "zip",
                        str(child.parent),
                        child.name,
                    )
                    archive_count += 1
                except Exception:
                    pass
            try:
                shutil.rmtree(child)
                delete_count += 1
            except Exception:
                pass
    return archive_count, delete_count


def cleanup_log() -> int:
    """轮转 monitor.log，保留最后 N 行."""
    if not LOG_FILE.exists():
        return 0
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return 0
    original = len(lines)
    if original <= LOG_MAX_LINES:
        return 0
    kept = lines[-LOG_MAX_LINES:]
    LOG_FILE.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return original - len(kept)


def check_skill_integrity() -> list[str]:
    """技能文件完整性护栏：扫描所有 SKILL.md/模板，检测行号污染 + frontmatter 损坏。
    返回问题描述列表（空=全部健康）。背景：2026-06-19 母版技能被行号污染导致跨渠道
    分析卡生成不了，此检查防止此类无声损坏复发。"""
    problems: list[str] = []
    if not SKILLS_ROOT.is_dir():
        return problems
    for p in SKILLS_ROOT.rglob("*.md"):
        if ".bak" in p.name or "corrupted" in str(p):
            continue
        # 1. 行号污染：行首 `数字|`（read_file 带行号输出被当内容回写）
        try:
            with open(p, encoding="utf-8") as f:
                first = f.readline()
        except (OSError, UnicodeDecodeError):
            continue
        if _LINE_NUM_PREFIX.match(first):
            problems.append(f"行号污染: {p.relative_to(SKILLS_ROOT)}")
            continue
        # 2. SKILL.md frontmatter 完整性
        if p.name == "SKILL.md":
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            if not lines or lines[0].strip() != "---":
                problems.append(f"frontmatter首行损坏: {p.relative_to(SKILLS_ROOT)}")
                continue
            end = next((i for i in range(1, min(len(lines), 150))
                        if lines[i].strip() == "---"), None)
            if end is None:
                problems.append(f"frontmatter无结束边界: {p.relative_to(SKILLS_ROOT)}")
    return problems


def main() -> None:
    ev_removed = cleanup_events()
    snap_archived, snap_deleted = cleanup_snapshots()
    log_trimmed = cleanup_log()
    skill_problems = check_skill_integrity()
    parts = []
    if ev_removed:
        parts.append(f"监控事件: 清理{ev_removed}条")
    if snap_archived:
        parts.append(f"快照归档: {snap_archived}天")
    if snap_deleted:
        parts.append(f"快照删除: {snap_deleted}天")
    if log_trimmed:
        parts.append(f"日志轮转: 精简{log_trimmed}行")
    if parts:
        print("[清理守护] " + " · ".join(parts))
    # 技能护栏：只在发现问题时报警（静默通过，不刷屏）
    if skill_problems:
        print(f"[技能护栏] ⚠ 发现 {len(skill_problems)} 个损坏技能文件：")
        for prob in skill_problems[:10]:
            print(f"  {prob}")
        print("修复：Python 逐行剥离行首 ^\\d+\\| 前缀，备份后写回，重跑验证。")


if __name__ == "__main__":
    main()
