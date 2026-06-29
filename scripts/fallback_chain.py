#!/usr/bin/env python3
"""
数据源IP-ban回退链 v1.0
给所有数据采集器提供多源回退能力。
模式: 主源→备源1→备源2→本地缓存
"""
import json, sys, os, time
from datetime import datetime, timezone, timedelta
import urllib.request

TZ = timezone(timedelta(hours=8))
UA = "Hermes/1.0"
CACHE_DIR = os.path.expanduser("~/AppData/Local/hermes/data/cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _fetch_url(url: str, timeout: int = 10, headers: dict = None) -> tuple:
    """代理回退HTTP GET。返回 (data, None) 或 (None, error)。"""
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    
    for ph in [None, {}]:
        try:
            if ph is not None:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler(ph))
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(url, headers=h)
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read()), None
        except Exception as e:
            continue
    return None, f"All proxies failed for {url}"


def fallback_fetch(sources: list, cache_key: str = None, cache_ttl: int = 3600) -> dict:
    """
    多源回退获取。
    
    sources: [{"url": "...", "name": "primary", "timeout": 10, "headers": {...}}, ...]
    cache_key: 缓存文件名（不含目录）
    cache_ttl: 缓存有效期秒数
    
    返回: {"ok": bool, "data": dict, "source": str, "cached": bool}
    """
    # 先试缓存
    if cache_key:
        cache_fp = os.path.join(CACHE_DIR, cache_key)
        try:
            with open(cache_fp) as f:
                cached = json.load(f)
            age = time.time() - cached.get("_ts", 0)
            if age < cache_ttl:
                cached["_from_cache"] = True
                return {"ok": True, "data": cached, "source": "cache", "cached": True}
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    # 依次尝试各源
    last_error = None
    for src in sources:
        data, error = _fetch_url(
            src["url"],
            timeout=src.get("timeout", 10),
            headers=src.get("headers"),
        )
        if data is not None:
            # 保存缓存
            data["_ts"] = time.time()
            data["_source"] = src.get("name", "unknown")
            if cache_key:
                try:
                    with open(os.path.join(CACHE_DIR, cache_key), "w") as f:
                        json.dump(data, f)
                except Exception:
                    pass
            return {"ok": True, "data": data, "source": src.get("name", "unknown"), "cached": False}
        last_error = error
    
    # 全失败，返回过期缓存
    if cache_key:
        cache_fp = os.path.join(CACHE_DIR, cache_key)
        try:
            with open(cache_fp) as f:
                cached = json.load(f)
            return {"ok": True, "data": cached, "source": f"stale_cache({int(time.time()-cached.get('_ts',0))}s)", "cached": True, "stale": True}
        except Exception:
            pass
    
    return {"ok": False, "data": {}, "source": "none", "error": last_error}


# ═══════════════════════════════════════════
# 预置回退链（按数据源）
# ═══════════════════════════════════════════

def crypto_price_fallback(symbol: str = "BTCUSDT"):
    """加密价格回退: Binance → CoinGecko → cache"""
    sym_lower = symbol.lower().replace("usdt", "")
    return [
        {"name": "Binance", "url": f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", "timeout": 8},
        {"name": "CoinGecko", "url": f"https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", "timeout": 10},  # 简化
    ]


def gold_price_fallback():
    """黄金价格回退: Yahoo → gold-api → cache"""
    return [
        {"name": "Yahoo", "url": "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d", "timeout": 10},
        {"name": "gold-api", "url": "https://www.gold-api.com/api/XAU/USD", "timeout": 8},
    ]


def fx_rate_fallback(pair: str = "EURUSD"):
    """外汇汇率回退"""
    base = pair[:3]
    quote = pair[3:]
    return [
        {"name": "Yahoo", "url": f"https://query1.finance.yahoo.com/v8/finance/chart/{pair}=X?interval=1m&range=1d", "timeout": 10},
        {"name": "exchangerate", "url": f"https://open.er-api.com/v6/latest/{base}", "timeout": 8},
    ]


# ═══════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════

def safe_fetch_crypto(symbol: str = "BTCUSDT", cache_key: str = None, cache_ttl: int = 300) -> dict:
    """一键获取加密数据，自带回退"""
    if cache_key is None:
        cache_key = f"crypto_{symbol.lower()}.json"
    return fallback_fetch(
        crypto_price_fallback(symbol),
        cache_key=cache_key,
        cache_ttl=cache_ttl,
    )


def safe_fetch_gold(cache_ttl: int = 300) -> dict:
    """一键获取黄金数据"""
    return fallback_fetch(
        gold_price_fallback(),
        cache_key="gold_price.json",
        cache_ttl=cache_ttl,
    )


def safe_fetch_fx(pair: str = "EURUSD", cache_ttl: int = 600) -> dict:
    """一键获取外汇数据"""
    return fallback_fetch(
        fx_rate_fallback(pair),
        cache_key=f"fx_{pair.lower()}.json",
        cache_ttl=cache_ttl,
    )


if __name__ == "__main__":
    # 测试
    result = safe_fetch_crypto("BTCUSDT")
    print(f"BTC: ok={result['ok']}, source={result['source']}, cached={result.get('cached')}")
    result2 = safe_fetch_gold()
    print(f"Gold: ok={result2['ok']}, source={result2['source']}")
