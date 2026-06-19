#!/usr/bin/env python3
"""v1.0 数据清理守护 — 防止监控事件和快照无限膨胀。

由信号巡检 cron 调用，每次运行执行：
  1. monitor_events.json 只保留 7 天内非 notified 或最近 1000 条
  2. source_snapshots/ 按日归档，保留最近 7 天，删除超过 30 天的
  3. monitor.log 轮转，保留最后 3000 行
"""
from __future__ import annotations

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


def main() -> None:
    ev_removed = cleanup_events()
    snap_archived, snap_deleted = cleanup_snapshots()
    log_trimmed = cleanup_log()
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


if __name__ == "__main__":
    main()
