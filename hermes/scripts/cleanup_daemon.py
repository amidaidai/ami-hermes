#!/usr/bin/env python
"""清理守护 — 每6小时。清理过期日志、临时文件、状态缓存。"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

DATA = Path(__file__).resolve().parent.parent.parent / "data"
SCRIPTS = Path(__file__).resolve().parent

def cleanup():
    cleaned = []
    now = datetime.now(timezone.utc)
    
    # 清理7天前的旧卡文件（保留最近10个）
    card_files = sorted(DATA.glob("auto_card_*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
    for f in card_files[10:]:
        if now - datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) > timedelta(days=7):
            f.unlink(missing_ok=True)
            cleaned.append(f.name)
    
    # 清理30天前的旧JSONL日志（trade_plans保留）
    for pattern in ["prediction_log.jsonl", "price_alerts.jsonl"]:
        f = DATA / pattern
        if f.exists() and now - datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) > timedelta(days=30):
            f.unlink(missing_ok=True)
            cleaned.append(f.name)
    
    # 清理过期Protections状态（保留今天的）
    prot_file = DATA / "protections_state.json"
    if prot_file.exists():
        try:
            import json
            prot = json.loads(prot_file.read_text())
            last_time = prot.get("last_reset", "")
            if last_time:
                last = datetime.fromisoformat(last_time)
                if (now - last.replace(tzinfo=timezone.utc)).days > 1:
                    prot_file.unlink(missing_ok=True)
                    cleaned.append("protections_state.json (expired)")
        except:
            pass
    
    return cleaned

if __name__ == "__main__":
    silent = "--quiet" in sys.argv
    result = cleanup()
    if result and not silent:
        print(f"清理守护: 清理了 {len(result)} 个文件")
        for f in result:
            print(f"  🗑 {f}")
    elif not silent:
        print("清理守护: 无需清理")
