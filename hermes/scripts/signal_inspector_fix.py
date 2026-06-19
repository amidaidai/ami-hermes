#!/usr/bin/env python3
"""
棠溪 · 信号巡检误报修复 v1.0
原问题：信号巡检报告"未发现主监控python进程"时，可能是时序不同步造成的误报。
修复：两次连续检查都未发现进程才告警。
"""
import json, os, time
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DATA_DIR = "D:/Hermes agent/data"
STATE_FILE = os.path.join(DATA_DIR, "monitor_state.json")

def main():
    now = datetime.now(TZ).isoformat(timespec="seconds")
    
    # Load state
    state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
        except Exception:
            pass
    
    # Check process
    process_found = False
    try:
        import subprocess
        result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python*"], 
                               capture_output=True, text=True, shell=True)
        if "python" in result.stdout.lower():
            process_found = True
    except Exception:
        process_found = False
    
    # Two-strike rule
    prev_no_process = state.get("_no_process_count", 0)
    
    if not process_found:
        state["_no_process_count"] = prev_no_process + 1
        if state["_no_process_count"] >= 2:
            state["_last_alert"] = now
            state["_alert"] = "连续2次未发现python进程 · 建议检查"
            print(json.dumps({"alert": True, "message": state["_alert"]}))
        else:
            print(json.dumps({"alert": False, "message": f"第{state['_no_process_count']}次未发现进程·等待确认"}))
    else:
        state["_no_process_count"] = 0
        state["_last_found"] = now
        print(json.dumps({"alert": False, "message": "进程正常"}))
    
    # Save state
    state["_last_check"] = now
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
