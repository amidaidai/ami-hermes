#!/usr/bin/env python3
"""事件日历 — Jin10 MCP + HTTP回退获取财经日历"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json, os, urllib.request
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))

# 重大事件关键词
MAJOR_EVENTS = [
    "FOMC", "美联储", "利率决议", "联邦基金利率",
    "非农", "NFP", "非农就业",
    "CPI", "消费者物价指数", "PPI", "生产者物价指数",
    "GDP", "GDP数据",
    "失业率", "失业金",
    "美联储主席", "鲍威尔", "Powell",
    "零售销售", "零售",
    "美联储会议纪要", "FOMC会议纪要",
]

# 公开日历API (Jin10免费接口)
CALENDAR_URLS = [
    "https://cdn.jin10.com/data_center/reports/calendar.json",
    "https://cdn.jin10.com/data_center/reports/calendar.json?_={}",
]


def fetch_calendar():
    """从公开API获取财经日历。"""
    import time
    for url in CALENDAR_URLS:
        try:
            req = urllib.request.Request(
                url.format(int(time.time())),
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.jin10.com/"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body
        except Exception:
            continue
    return None


def parse_events(calendar_data, days=3):
    """解析日历数据为事件列表。"""
    events = []
    if not calendar_data:
        return events
    
    now = datetime.now(TZ)
    
    # Jin10格式: {data: [{date, datas: [{time, country, title, impact, ...}]}]}
    if isinstance(calendar_data, dict):
        data = calendar_data.get("data", calendar_data.get("list", []))
        if isinstance(data, list):
            for day in data:
                date_str = day.get("date", "")
                items = day.get("datas", day.get("items", []))
                if isinstance(items, list):
                    for item in items:
                        time_str = item.get("time", "00:00")
                        title = item.get("title", item.get("name", ""))
                        impact = item.get("impact", item.get("star", 3))
                        
                        # 只保留高影响力(impact>=3)或重大事件
                        try:
                            impact = int(impact)
                        except (ValueError, TypeError):
                            impact = 3
                        
                        if impact >= 3 or any(kw in (title + " " + item.get("country", "")) for kw in MAJOR_EVENTS):
                            try:
                                event_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                                event_dt = event_dt.replace(tzinfo=TZ)
                            except ValueError:
                                continue
                            
                            events.append({
                                "name": title,
                                "time": event_dt.strftime("%Y-%m-%d %H:%M"),
                                "timestamp": int(event_dt.timestamp()),
                                "impact": impact,
                                "country": item.get("country", ""),
                                "previous": item.get("previous", ""),
                                "consensus": item.get("consensus", item.get("forecast", "")),
                            })
    
    # 排序
    events.sort(key=lambda e: e["timestamp"])
    return events


def is_blocked(events=None, buffer_minutes=30):
    """检测是否有重大事件在buffer_minutes内。"""
    if events is None:
        cal = fetch_calendar()
        events = parse_events(cal)
    
    now_ts = datetime.now(TZ).timestamp()
    
    for e in events:
        event_ts = e["timestamp"]
        remaining = event_ts - now_ts
        
        if 0 <= remaining <= buffer_minutes * 60:
            return {
                "blocked": True,
                "reason": f"重大事件: {e['name']} 在 {e['time']} ({int(remaining//60)}分钟后)",
                "event_name": e["name"],
                "event_time": e["time"],
                "minutes_remaining": int(remaining // 60),
                "impact": e["impact"],
            }
        # 事件已过但仍在窗口内(前30min)
        if -buffer_minutes * 60 <= remaining < 0:
            return {
                "blocked": True,
                "reason": f"事件进行中: {e['name']} ({int(-remaining//60)}分钟前)",
                "event_name": e["name"],
                "event_time": e["time"],
                "minutes_ago": int(-remaining // 60),
                "impact": e["impact"],
            }
    
    return {"blocked": False, "reason": "无冲突"}


def next_event(events=None):
    """返回最近事件信息。"""
    if events is None:
        cal = fetch_calendar()
        events = parse_events(cal)
    
    now_ts = datetime.now(TZ).timestamp()
    
    # 找到最近的未来事件
    upcoming = [e for e in events if e["timestamp"] > now_ts]
    if not upcoming:
        return None
    
    next_e = upcoming[0]
    remaining = (next_e["timestamp"] - now_ts) / 3600
    return {
        "name": next_e["name"],
        "time": next_e["time"],
        "hours_until": round(remaining, 1),
        "impact": next_e["impact"],
    }


def get_block_status():
    """完整事件状态。"""
    cal = fetch_calendar()
    events = parse_events(cal)
    blocked = is_blocked(events)
    nxt = next_event(events)
    
    return {
        "blocked": blocked["blocked"],
        "reason": blocked.get("reason", ""),
        "event_name": blocked.get("event_name", nxt.get("name", "") if nxt else ""),
        "next_event": f"{nxt['name']} @ {nxt['time']}" if nxt else "未知",
        "hours_until_next": nxt["hours_until"] if nxt else None,
        "events_today": len(events),
        "timestamp": datetime.now(TZ).strftime("%H:%M"),
    }


if __name__ == "__main__":
    status = get_block_status()
    print(f"事件阻塞: {status['blocked']}")
    print(f"原因: {status['reason']}")
    print(f"下个事件: {status['next_event']}")
    print(f"今日事件数: {status['events_today']}")
    if status.get("hours_until_next"):
        print(f"距下个事件: {status['hours_until_next']}h")
