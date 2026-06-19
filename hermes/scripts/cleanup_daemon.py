#!/usr/bin/env python3
"""
棠溪 · 事件清理守护 v1.0 (独立 cron · 不依赖信号巡检)
每天凌晨 4:00 运行，清理过期事件/日志，防止 monitor_events.json 膨胀
"""
import json, os, time
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DATA_DIR = "D:/Hermes agent/data"

MAX_EVENTS = 500
MAX_AGE_DAYS = 7
MAX_LOG_SIZE_MB = 10

def main():
    now = datetime.now(TZ)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    
    changes = []
    
    # 1. 清理 monitor_events.json
    events_file = os.path.join(DATA_DIR, "monitor_events.json")
    if os.path.exists(events_file):
        try:
            with open(events_file, "r") as f:
                data = json.load(f)
            events = data.get("events", [])
            original_count = len(events)
            
            # 去旧事件
            new_events = []
            for e in events:
                try:
                    t = datetime.fromisoformat(e.get("time", "2000-01-01"))
                    if t > cutoff:
                        new_events.append(e)
                except Exception:
                    new_events.append(e)
            
            # 只保留最近 MAX_EVENTS
            if len(new_events) > MAX_EVENTS:
                new_events = new_events[-MAX_EVENTS:]
            
            data["events"] = new_events
            data["_last_cleanup"] = now.isoformat(timespec="seconds")
            data["_cleaned"] = original_count - len(new_events)
            
            with open(events_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            changes.append(f"monitor_events: {original_count} → {len(new_events)} (-{original_count - len(new_events)})")
        except Exception as e:
            changes.append(f"monitor_events: error - {e}")
    
    # 2. 清理大日志文件
    for fname in ["noise_history.json", "monitor_log.txt"]:
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            if size_mb > MAX_LOG_SIZE_MB:
                # Truncate by keeping last 1000 lines
                try:
                    with open(fpath, "r") as f:
                        lines = f.readlines()
                    with open(fpath, "w") as f:
                        f.writelines(lines[-1000:])
                    changes.append(f"{fname}: {size_mb:.1f}MB → truncated")
                except Exception as e:
                    changes.append(f"{fname}: error - {e}")
    
    # 3. 清理旧的 source_snapshots
    snap_dir = os.path.join(DATA_DIR, "source_snapshots")
    if os.path.isdir(snap_dir):
        for date_dir in os.listdir(snap_dir):
            dpath = os.path.join(snap_dir, date_dir)
            if os.path.isdir(dpath):
                try:
                    d = datetime.strptime(date_dir, "%Y-%m-%d")
                    if d < cutoff:
                        import shutil
                        shutil.rmtree(dpath)
                        changes.append(f"source_snapshots/{date_dir}: removed")
                except ValueError:
                    pass
    
    result = {
        "time": now.isoformat(timespec="seconds"),
        "changes": changes,
        "summary": "\n".join(changes) if changes else "No cleanup needed"
    }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
