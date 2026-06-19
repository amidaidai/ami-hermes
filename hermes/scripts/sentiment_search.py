#!/usr/bin/env python3
"""
棠溪 · 情绪搜索引擎 v2.1
Brave Search API (2000次/月) → DDGS (备用) → 社区数据 (兜底)
"""

import json, time, re, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
CACHE_FILE = Path("D:/Hermes agent/data/sentiment_cache.json")
CACHE_TTL = 600
SECRETS_DIR = Path("D:/Hermes agent/hermes/secrets")
UA = "Mozilla/5.0"

def _read_secret(name):
    try:
        return (SECRETS_DIR / name).read_text(encoding="utf-8").strip()
    except:
        return ""

def _brave_search(query, max_results=5):
    """Brave Search API"""
    try:
        key = _read_secret("brave_api_key.txt")
        if not key:
            return []
        url = "https://api.search.brave.com/res/v1/web/search?q=" + urllib.parse.quote(query) + "&count=" + str(max_results)
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "X-Subscription-Token": key,
            "User-Agent": UA,
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        web = data.get("web", {}).get("results", [])
        return [{"title": w["title"], "body": w.get("description", "")[:200], "url": w.get("url", "")} for w in web]
    except:
        return []

def _ddgs_search(query, max_results=5):
    """DDGS备用"""
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        return [{"title": r["title"], "body": r.get("body", "")[:200]} for r in results]
    except:
        return []

def _extract_sentiment(texts):
    """从搜索结果提取情绪关键词"""
    combined = " ".join([t.get("title", "") + " " + t.get("body", "") for t in texts]).lower()
    
    bullish = ["bullish", "rally", "surge", "breakout", "buy", "accumulation",
               "\u770b\u6da8", "\u53cd\u5f39", "\u7a81\u7834", "\u591a\u5934", "\u4e70\u5165", "\u4e0a\u6da8", "\u725b\u5e02"]
    bearish = ["bearish", "crash", "dump", "breakdown", "sell", "distribution", 
               "\u770b\u8dcc", "\u66b4\u8dcc", "\u5d29\u76d8", "\u7a7a\u5934", "\u5356\u51fa", "\u4e0b\u8dcc", "\u718a\u5e02"]
    neutral = ["consolidation", "range", "sideways", "uncertainty",
               "\u9707\u8361", "\u76d8\u6574", "\u6a2a\u76d8", "\u89c2\u671b"]
    
    bull_count = sum(1 for w in bullish if w in combined)
    bear_count = sum(1 for w in bearish if w in combined)
    
    direction = "\u504f\u591a" if bull_count > bear_count + 2 else "\u504f\u7a7a" if bear_count > bull_count + 2 else "\u5206\u6b67" if bull_count > 0 and bear_count > 0 else "\u4e2d\u6027"
    strength = "\u5f3a" if bull_count + bear_count >= 8 else "\u4e2d" if bull_count + bear_count >= 4 else "\u5f31"
    
    hot_words = []
    for title in [t.get("title", "") for t in texts[:3]]:
        words = re.findall(r'[\w\u4e00-\u9fff]+', title)
        hot_words.extend([w for w in words if len(w) > 2][:3])
    
    return {
        "direction": direction, "strength": strength,
        "bull_signals": bull_count, "bear_signals": bear_count,
        "hot_words": list(set(hot_words))[:5], "source_count": len(texts),
    }

def search_sentiment(symbol):
    """搜索情绪（带缓存）"""
    cache = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except:
            pass
    
    key = f"{symbol}_{int(time.time() // CACHE_TTL)}"
    if key in cache:
        return cache[key]
    
    if "XAU" in symbol.upper():
        query = "XAUUSD gold price sentiment analysis"
    elif "BTC" in symbol.upper():
        query = "BTC bitcoin crypto sentiment market"
    elif "ETH" in symbol.upper():
        query = "ETH ethereum crypto sentiment"
    else:
        query = f"{symbol} market sentiment"
    
    texts = _brave_search(query, 5)
    source = "Brave"
    if not texts:
        texts = _ddgs_search(query, 5)
        source = "DDGS"
    if not texts:
        sentiment = {"direction": "\u672a\u83b7\u53d6", "strength": "\u5f31", "bull_signals": 0, "bear_signals": 0, "hot_words": [], "source_count": 0, "source": "\u65e0\u53ef\u7528\u641c\u7d22\u6e90"}
        cache[key] = sentiment
        return sentiment
    
    sentiment = _extract_sentiment(texts)
    sentiment["query"] = query
    sentiment["time"] = datetime.now(TZ).isoformat()
    sentiment["source"] = source
    cache[key] = sentiment
    if len(cache) > 20:
        for k in sorted(cache)[:len(cache)-20]:
            del cache[k]
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return sentiment

def sentiment_line(symbol):
    s = search_sentiment(symbol)
    d = s.get("direction", "\u4e2d\u6027")
    st = s.get("strength", "\u5f31")
    hot = "\u00b7".join(s.get("hot_words", [])[:3]) or "\u65e0\u70ed\u8bcd"
    return f"{s.get('source','?')}: {d}\u00b7\u5f3a\u5ea6{st}\u00b7\u70ed\u8bcd[{hot}]\u00b7\u591a{s.get('bull_signals',0)}\u7a7a{s.get('bear_signals',0)}\u4fe1\u53f7"

if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    print(f"=== {sym} ===")
    s = search_sentiment(sym)
    print(json.dumps(s, indent=2, ensure_ascii=False))
    print(f"\n{sentiment_line(sym)}")
