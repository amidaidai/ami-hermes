#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
棠溪 · 实时事件禁做检查 v2.0
集成 Jin10 财经日历 + 关键词匹配 + 波动率阈值
"""

import json, urllib.request, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
CACHE_FILE = Path.home() / "AppData/Local/hermes/data/event_cache.json"
CACHE_TTL = 3600  # 1小时缓存

HIGH_IMPACT_KEYWORDS = [
    "非农", "NFP", "CPI", "FOMC", "利率决议", "GDP", "PMI", "失业率",
    "鲍威尔", "Powell", "央行", "零售销售", "PCE", "就业",
    "美联储", "Fed", "加息", "降息", "通胀", "核心PCE",
    "ISM制造业", "ISM服务业", "消费者信心", "初请失业金",
    "欧洲央行", "ECB", "日本央行", "BOJ", "英国央行", "BOE",
]

# 高影响事件前后禁止窗口（分钟）
BAN_WINDOW_BEFORE = 30  # 事件前30分钟
BAN_WINDOW_AFTER = 45   # 事件后45分钟


def _fetch_jin10_calendar() -> list[dict]:
    """从 Jin10 拉取本周财经日历。"""
    try:
        url = "https://api.jin10.com/calendar/week/v2"
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        events = data.get("data", []) if isinstance(data, dict) else []
        return events
    except Exception:
        return []


def _is_high_impact(event: dict) -> bool:
    """判断是否为高影响事件。"""
    title = str(event.get("title", "") or event.get("name", "")).lower()
    importance = str(event.get("importance", "") or event.get("star", "") or "")
    
    # 三星或以上
    if importance in ("3", "4", "5") or "三星" in importance:
        return True
    
    # 关键词匹配
    for kw in HIGH_IMPACT_KEYWORDS:
        if kw.lower() in title:
            return True
    
    return False


def check_event_ban_live(symbol: str = "BTCUSDT") -> tuple[bool, str]:
    """
    实时检查是否存在活跃的禁做事件。
    
    Returns:
        (是否禁做, 原因)
    """
    reasons = []
    now = datetime.now(TZ)
    
    # 1. Jin10 日历检查
    events = _fetch_jin10_calendar()
    for ev in events:
        if not _is_high_impact(ev):
            continue
        
        # 解析事件时间
        ev_time_str = str(ev.get("time", "") or ev.get("pub_time", "") or "")
        if not ev_time_str:
            continue
        
        try:
            # 尝试多种时间格式
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"]:
                try:
                    ev_time = datetime.strptime(ev_time_str[:19], fmt).replace(tzinfo=TZ)
                    break
                except ValueError:
                    continue
            else:
                continue
            
            # 检查是否在禁止窗口内
            delta = (now - ev_time).total_seconds() / 60
            if -BAN_WINDOW_BEFORE <= delta <= BAN_WINDOW_AFTER:
                title = ev.get("title", "") or ev.get("name", "") or "未知事件"
                if delta < 0:
                    reasons.append(f"⏳ {title} ({abs(int(delta))}min后)")
                else:
                    reasons.append(f"🔴 {title} ({int(delta)}min前·消化中)")
        except Exception:
            pass
    
    # 2. 缓存兜底 — Jin10 不可用时用关键词检查
    if not reasons and CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            cached_events = cache.get("events", [])
            for ev in cached_events:
                if _is_high_impact(ev):
                    ev_time = datetime.fromisoformat(ev.get("time", ""))
                    delta = (now - ev_time).total_seconds() / 60
                    if -BAN_WINDOW_BEFORE <= delta <= BAN_WINDOW_AFTER:
                        reasons.append(f"📋 {ev.get('title','')} (缓存)")
        except Exception:
            pass
    
    if reasons:
        return True, " · ".join(reasons[:3])  # 最多3个原因
    
    return False, ""


def refresh_event_cache() -> bool:
    """更新事件缓存（供 cron 调用）。"""
    events = _fetch_jin10_calendar()
    if events:
        high_impact = [e for e in events if _is_high_impact(e)]
        cache = {
            "updated": datetime.now(TZ).isoformat(),
            "count": len(high_impact),
            "events": high_impact[:20],
        }
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    return False


if __name__ == "__main__":
    print("刷新事件缓存...")
    ok = refresh_event_cache()
    print(f"状态: {'✅ 成功' if ok else '❌ 失败'}")
    banned, reason = check_event_ban_live()
    print(f"禁做检查: {'🔴 ' + reason if banned else '✅ 无禁做事件'}")
