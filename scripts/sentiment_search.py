#!/usr/bin/env python3
"""棠溪 · 热点搜索模块 v1.0

核心函数：sentiment_line(symbol) -> str
数据源：web_search（Brave 回退）
"""

import sys, json, os
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

TZ = timezone(timedelta(hours=8))

def sentiment_line(symbol: str) -> str:
    """搜索品种热点事件，返回一行摘要"""
    sym = symbol.upper().replace(".P", "").replace("USDT", "").replace("USD", "")
    now_str = datetime.now(TZ).strftime("%H:%M")
    
    # 品种关键词映射
    kw_map = {
        "BTC":  "Bitcoin BTC crypto",
        "ETH":  "Ethereum ETH crypto",
        "XAU":  "gold XAUUSD precious metal",
        "AAPL": "AAPL Apple stock",
        "TSLA": "TSLA Tesla stock",
        "EUR":  "EURUSD euro",
        "GBP":  "GBPUSD pound",
        "JPY":  "USDJPY yen",
        "ES":   "S&P 500 futures",
    }
    kw = kw_map.get(sym, f"{sym} price")
    
    try:
        from hermes_tools import web_search
        r = web_search(query=f"{kw} news today 2026", limit=3)
        results = r.get("data", {}).get("web", [])
        if not results:
            return f"📡 {sym}热点：暂无热点·{now_str}"
        
        # 提取标题
        titles = []
        for item in results[:3]:
            t = item.get("title", "")
            if t:
                titles.append(t[:35])
        
        if titles:
            return f"📡 {sym}热点：{'|'.join(titles)}·{now_str}"
        return f"📡 {sym}热点：暂无热点·{now_str}"
    except ImportError:
        # 无 hermes_tools → 用 urllib fallback
        try:
            import urllib.request
            url = f"https://news.google.com/rss/search?q={quote_plus(kw)}&hl=en-US&gl=US&ceid=US:en"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read().decode("utf-8", errors="replace")
            import re
            titles = re.findall(r"<title>(.*?)</title>", data)[:3]
            if titles:
                return f"📡 {sym}热点：{'|'.join(t[:30] for t in titles)}·{now_str}"
            return f"📡 {sym}热点：暂无热点·{now_str}"
        except Exception:
            return f"📡 {sym}热点：搜索暂不可用·{now_str}"
    except Exception:
        return f"📡 {sym}热点：搜索暂不可用·{now_str}"
