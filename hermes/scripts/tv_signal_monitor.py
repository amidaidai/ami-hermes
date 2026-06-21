#!/usr/bin/env python3
"""TV DMI信号监控 — 判断是否需要推送卡片到Telegram。

用法:
  由hermes cron agent调用。agent先读TV MCP数据传入。
  
  python tv_signal_monitor.py --tv-grade "A多" --cvd-val -3099 --cvd-slope -222 [--symbol BTCUSDT]

分级逻辑:
  - A多/A空 → 必须推送（优先机会）
  - B多/B空 + 价在关键位 → 推送（候补机会）
  - C反多/C反空 → 不推送（反转等确认）
  - X/C等待 → 不推送（无机会或冲突）
"""

import sys, json, os
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
ROOT = Path(os.environ.get("HERMES_ROOT", "D:/Hermes agent"))
DATA = ROOT / "data"
SCRIPTS = ROOT / "hermes" / "scripts"
sys.path.insert(0, str(SCRIPTS))

STATE_FILE = DATA / "tv_signal_state.json"

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {"last_push_grade": "", "last_push_time": "", "push_count_today": 0, "date": ""}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))

def should_push(grade: str, state: dict) -> tuple[bool, str]:
    """判断是否应该推送。返回(是否推送, 原因)。"""
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")
    
    # 重置每日计数
    if state.get("date") != today:
        state["push_count_today"] = 0
        state["date"] = today
    
    # A级: 必推
    if grade.startswith("A多") or grade.startswith("A空"):
        # 防重复: 同一等级30分钟内不重复推
        last_time = state.get("last_push_time", "")
        if last_time:
            try:
                last_dt = datetime.fromisoformat(last_time)
                if (now - last_dt).total_seconds() < 1800 and state.get("last_push_grade") == grade:
                    return False, f"A级但30分钟内已推过{grade}"
            except:
                pass
        # 每日A级最多推6次
        if state.get("push_count_today", 0) >= 6:
            return False, "A级但今日推送已达上限6次"
        return True, f"A级机会·推送"
    
    # B级: 只在价格锚定关键位时推
    if grade.startswith("B多") or grade.startswith("B空"):
        # B级每日最多推3次
        if state.get("push_count_today", 0) >= 3:
            return False, "B级但今日推送已达上限3次"
        # 需要检查是否在关键位附近
        return "CHECK_KEY_LEVEL", "B级需检查关键位"
    
    # C反/C等待/X: 不推
    return False, f"{grade}级·无推送机会"

def check_key_level_proximity(symbol: str) -> bool:
    """检查价格是否在关键位附近（复用auto_card的关键位逻辑）。"""
    try:
        from auto_card import _find_nearest_key_level
        # 从最近的card读取price和klines
        card = DATA / f"auto_card_{symbol}.md"
        if not card.exists():
            return False
        content = card.read_text()
        # 简单解析：看是否有"← 价踩在这"（距离<0.5%）或"← 距"（较近）
        for line in content.split('\n'):
            if '← 价踩在这' in line:
                return True
            if '← 距' in line:
                # 提取距离
                import re
                m = re.search(r'距([\d.]+)点', line)
                if m:
                    dist = float(m.group(1))
                    # BTC: <300点算附近; XAU: <15点算附近
                    threshold = 300 if "BTC" in symbol else 15
                    if dist < threshold:
                        return True
        return False
    except:
        return False

if __name__ == "__main__":
    grade = ""
    symbol = "BTCUSDT"
    for i, arg in enumerate(sys.argv):
        if arg == "--tv-grade" and i + 1 < len(sys.argv):
            grade = sys.argv[i + 1]
        elif arg == "--symbol" and i + 1 < len(sys.argv):
            symbol = sys.argv[i + 1]
    
    if not grade:
        print("USAGE: python tv_signal_monitor.py --tv-grade <grade> [--symbol BTCUSDT]")
        sys.exit(1)
    
    state = load_state()
    push, reason = should_push(grade, state)
    
    if push == "CHECK_KEY_LEVEL":
        if check_key_level_proximity(symbol):
            push = True
            reason = "B级+关键位锚定·推送"
        else:
            push = False
            reason = "B级但不在关键位·跳过"
    
    # 输出JSON结果给agent读取
    result = {
        "push": bool(push) if push != "CHECK_KEY_LEVEL" else False,
        "grade": grade,
        "reason": reason,
        "time": datetime.now(TZ).isoformat(),
    }
    
    if push and push != "CHECK_KEY_LEVEL":
        state["last_push_grade"] = grade
        state["last_push_time"] = result["time"]
        state["push_count_today"] = state.get("push_count_today", 0) + 1
        save_state(state)
    
    print(json.dumps(result, ensure_ascii=False))
