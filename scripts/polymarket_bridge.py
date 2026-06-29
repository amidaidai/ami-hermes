#!/usr/bin/env python3
"""
棠溪 · Polymarket 预测市场桥 v1.0
借鉴 TradingAgents: 零密钥预测市场作为宏观情绪辅助源。

Polymarket Gamma API (免费·公开·无需认证):
  GET https://gamma-api.polymarket.com/events?closed=false&limit=20

用于:
  1. XAU 宏观面: Fed 决策概率、衰退概率、地缘政治
  2. BTC 宏观面: 加密监管、ETF 通过概率
  3. 全局情绪: 选举、通胀、战争风险
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

UA = "Mozilla/5.0"
_TZ = timezone(timedelta(hours=8))

# 与我们交易相关的 Polymarket 标签/关键词
RELEVANT_TAGS = {
    "fed":            "Fed决策",
    "federal-reserve": "Fed决策",
    "interest-rate":  "Fed决策",
    "recession":      "衰退",
    "inflation":      "通胀",
    "cpi":            "通胀",
    "geopolitics":    "地缘",
    "war":            "地缘",
    "election":       "选举",
    "bitcoin":        "加密",
    "crypto":         "加密",
    "etf":            "加密ETF",
    "gold":           "黄金",
    "tariff":         "贸易",
    "trade-war":      "贸易",
    "china":          "中国",
    "oil":            "原油",
    "gdp":            "经济",
    "unemployment":   "就业",
    "jobs":           "就业",
}

CACHE_FILE = Path("data/polymarket_cache.json")
CACHE_TTL = timedelta(hours=1)


def _cache_is_fresh() -> bool:
    if not CACHE_FILE.exists():
        return False
    try:
        d = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(d.get("_cached_at", "2000-01-01T00:00:00Z"))
        return datetime.now(timezone.utc) - cached_at < CACHE_TTL
    except Exception:
        return False


def _fetch_markets() -> list[dict]:
    """从 Polymarket Gamma API 拉取开放式预测市场"""
    try:
        url = "https://gamma-api.polymarket.com/events?closed=false&limit=30"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            events = json.loads(resp.read())
            if isinstance(events, list):
                return events
            return []
    except Exception:
        return []


def _extract_markets(events: list[dict]) -> list[dict]:
    """从事件列表中提取归类后的高信号市场"""
    markets = []
    for ev in events:
        title = (ev.get("title") or "").lower()
        slug = (ev.get("slug") or "").lower()
        tags = [t.get("label", "").lower() for t in (ev.get("tags") or [])]
        text = f"{title} {slug} {' '.join(tags)}"

        # 归类
        category = None
        for keyword, cat_name in RELEVANT_TAGS.items():
            if keyword in text:
                category = cat_name
                break

        if not category:
            continue

        # 提取关键数据
        volume = float(ev.get("volume", 0) or 0)
        liquidity = float(ev.get("liquidity", 0) or 0)
        # 从 markets 中找 implied probability
        mkts = ev.get("markets", [])
        probs = []
        for m in mkts:
            outcomes = json.loads(m.get("outcomePrices", "[]") or "[]") if isinstance(m.get("outcomePrices"), str) else (m.get("outcomePrices") or [])
            for o in outcomes:
                try:
                    p = float(o)
                    if 0.01 < p < 0.99:  # 过滤极端值
                        probs.append(p)
                except (ValueError, TypeError):
                    pass

        # 闭合日期
        close_time = ev.get("closeTime") or ev.get("endDate") or ""
        try:
            close_dt = datetime.fromisoformat(close_time.replace("Z", "+00:00")) if close_time else None
            close_str = close_dt.strftime("%m-%d") if close_dt else "?"
        except Exception:
            close_str = "?"

        markets.append({
            "title": ev.get("title", "?"),
            "category": category,
            "volume": round(volume, 0),
            "liquidity": round(liquidity, 0),
            "prob_max": round(max(probs) * 100, 1) if probs else None,
            "close": close_str,
        })

    # 按 volume 排序，取 top 15
    markets.sort(key=lambda x: x["volume"], reverse=True)
    return markets[:15]


def get_polymarket_signal() -> dict:
    """返回结构化 Polymarket 宏观信号

    Returns:
        {
            "_cached_at": "ISO时间",
            "markets": [...],
            "sentiment": {
                "fed_hawkish": 0-100概率,
                "recession_risk": 0-100概率,
                "crypto_positive": text,
                "geo_tension": text,
                "summary": "一句话总结"
            }
        }
    """
    if _cache_is_fresh():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))

    events = _fetch_markets()
    markets = _extract_markets(events)

    # 简易情绪提取
    fed_probs = []
    recession_prob = None
    crypto_signal = ""
    geo_signal = ""

    for m in markets:
        cat = m["category"]
        title = m["title"].lower() if m["title"] else ""
        prob = m.get("prob_max")

        if cat == "Fed决策" and prob is not None:
            # 降息 vs 加息信号
            if "cut" in title or "lower" in title:
                fed_probs.append(("cut", prob))
            elif "hike" in title or "raise" in title:
                fed_probs.append(("hike", prob))
            elif "hold" in title or "pause" in title:
                fed_probs.append(("hold", prob))

        if cat == "衰退" and prob is not None and recession_prob is None:
            recession_prob = prob

        if cat == "加密" and not crypto_signal:
            crypto_signal = "乐观" if (prob or 0) > 60 else ("悲观" if (prob or 0) < 40 else "中性")
        if cat == "加密ETF" and not crypto_signal:
            crypto_signal = "ETF乐观" if (prob or 0) > 60 else ""

        if cat == "地缘" and not geo_signal:
            geo_signal = "紧张" if (prob or 0) > 50 else "缓和"

    # 构建情绪总结
    sentiment = {
        "fed_cut_prob": round(max([p for t, p in fed_probs if t == "cut"], default=0), 0) if fed_probs else None,
        "fed_hike_prob": round(max([p for t, p in fed_probs if t == "hike"], default=0), 0) if fed_probs else None,
        "recession_risk": round(recession_prob, 0) if recession_prob else None,
        "crypto_signal": crypto_signal or "无相关市场",
        "geo_signal": geo_signal or "无相关市场",
    }

    # 一句话总结
    parts = []
    if sentiment["recession_risk"] and sentiment["recession_risk"] > 50:
        parts.append(f"衰退概率{sentiment['recession_risk']}%偏高")
    if sentiment["fed_cut_prob"] and sentiment["fed_cut_prob"] > 50:
        parts.append(f"降息概率{sentiment['fed_cut_prob']}%")
    if crypto_signal:
        parts.append(f"加密情绪{crypto_signal}")
    if not parts:
        parts.append("Polymarket无明确信号")

    sentiment["summary"] = " · ".join(parts)

    result = {
        "_cached_at": datetime.now(timezone.utc).isoformat(),
        "markets": markets[:10],  # top 10 for context saving
        "sentiment": sentiment,
    }

    # 写缓存
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result


def polymarket_context_text() -> str:
    """返回可用在卡片 环境段 的 Polymarket 文本摘要"""
    try:
        data = get_polymarket_signal()
        s = data.get("sentiment", {})
        lines = []
        if s.get("recession_risk"):
            lines.append(f"衰退概率{s['recession_risk']}%")
        if s.get("fed_cut_prob") and s["fed_cut_prob"] > 30:
            lines.append(f"降息{s['fed_cut_prob']}%")
        if s.get("geo_signal") and s["geo_signal"] != "无相关市场":
            lines.append(f"地缘{s['geo_signal']}")
        if s.get("crypto_signal") and s["crypto_signal"] != "无相关市场":
            lines.append(f"加密{s['crypto_signal']}")
        if lines:
            return "Polymarket — " + " · ".join(lines)
        return "Polymarket — 无明确信号"
    except Exception:
        return "Polymarket — 获取失败"


# CLI 测试
if __name__ == "__main__":
    from pathlib import Path as _P
    import sys as _sys
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent / "hermes" / "scripts"))
    from polymarket_bridge import get_polymarket_line
    print("Polymarket桥已加载")
    print(get_polymarket_line())
    
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
    data = get_polymarket_signal()
    print(f"  Polymarket 信号")
    print(f"  ├─ 市场数: {len(data['markets'])}")
    print(f"  ├─ 衰退概率: {data['sentiment'].get('recession_risk', '?')}%")
    print(f"  ├─ Fed降息: {data['sentiment'].get('fed_cut_prob', '?')}%")
    print(f"  ├─ 加密情绪: {data['sentiment'].get('crypto_signal', '?')}")
    print(f"  ├─ 地缘: {data['sentiment'].get('geo_signal', '?')}")
    print(f"  └─ 总结: {data['sentiment'].get('summary', '?')}")
    print()
    print(f"  用于卡片: {polymarket_context_text()}")
