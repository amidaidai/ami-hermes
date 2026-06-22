#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
棠溪 · Polymarket 情绪桥 v1.0
从 Polymarket 获取 BTC/宏观预测市场数据 → 情绪加权因子
"""

import json, urllib.request, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
CACHE_FILE = Path.home() / "AppData/Local/hermes/data/polymarket_sentiment.json"


def _safe_fetch(url: str, timeout: int = 10) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def fetch_btc_markets() -> list[dict]:
    """获取 BTC 相关的 Polymarket 预测市场。"""
    result = _safe_fetch(
        "https://gamma-api.polymarket.com/public-search?q=bitcoin+btc+crypto&limit_per_type=5&events_status=active",
        timeout=12
    )
    if not result:
        return []
    
    markets = []
    for ev in result.get("events", [])[:5]:
        for m in ev.get("markets", [])[:2]:
            try:
                prices = json.loads(m.get("outcomePrices", "[0.5]"))
                markets.append({
                    "title": ev.get("title", ""),
                    "question": m.get("question", ""),
                    "yes_prob": round(float(prices[0]), 4) if prices else 0.5,
                    "volume": m.get("volumeNum", 0),
                    "end_date": ev.get("endDate", ""),
                })
            except Exception:
                pass
    return markets


def polymarket_sentiment_score() -> dict:
    """计算 Polymarket 情绪分数。"""
    markets = fetch_btc_markets()
    
    if not markets:
        return {"score": 0.5, "bias": "neutral", "label": "无Poly数据", "markets": []}
    
    # 简单平均：预测概率 > 0.55 = 偏多，< 0.45 = 偏空
    scores = [m["yes_prob"] for m in markets if m["yes_prob"] > 0]
    avg_score = sum(scores) / len(scores) if scores else 0.5
    
    if avg_score > 0.55:
        bias = "bullish"
        label = f"🟢 Poly偏多({avg_score:.0%})"
    elif avg_score < 0.45:
        bias = "bearish"
        label = f"🔴 Poly偏空({avg_score:.0%})"
    else:
        bias = "neutral"
        label = f"⚪ Poly中性({avg_score:.0%})"
    
    total_volume = sum(m.get("volume", 0) or 0 for m in markets)
    
    result = {
        "score": round(avg_score, 4),
        "bias": bias,
        "label": label,
        "markets_count": len(markets),
        "total_volume_usd": total_volume,
        "markets": markets,
        "timestamp": datetime.now(TZ).isoformat(),
    }
    
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return result


def get_polymarket_line() -> str:
    """一行 Polymarket 摘要。"""
    data = polymarket_sentiment_score()
    return f"Poly: {data['label']} · {data['markets_count']}场 · ${data['total_volume_usd']:.0f}"


if __name__ == "__main__":
    data = polymarket_sentiment_score()
    print(f"Poly情绪: {data['label']}")
    print(f"市场数: {data['markets_count']}")
    print(f"总交易量: ${data['total_volume_usd']:,.0f}")
    for m in data["markets"][:3]:
        print(f"  {m['question'][:60]} → {m['yes_prob']:.0%}")
