#!/usr/bin/env python3
"""
棠溪 · 多源数据采集器 v3.3
集成了所有免费+Key API的统一数据层

已接入:
  CoinMarketCap (Key)  → 加密排名/行情/全球指标
  Alpha Vantage (Key)  → 股票报价
  Twelve Data (Key)    → 技术指标 RSI/MACD
  CoinGecko (Free)     → 社区/市占率/汇率
  alternative.me (Free)→ 恐慌贪婪
  Binance MCP          → 加密衍生品
  金十 MCP             → 快讯/日历/XAU
"""

import json, time, os, urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
SECRETS = ROOT / "hermes" / "secrets"
DATA = ROOT / "data"
CACHE = DATA / "api_cache.json"
CACHE_TTL = 120  # 2分钟通用缓存

# ═══════════════════ Keys ═══════════════════
def _read_secret(name: str) -> str:
    try:
        return (SECRETS / name).read_text(encoding="utf-8").strip()
    except Exception:
        return ""

CMC_KEY = _read_secret("coinmarketcap_api_key.txt")
AV_KEY = _read_secret("alphavantage_api_key.txt")
TD_KEY = _read_secret("twelvedata_api_key.txt")
TUSHARE_TOKEN = _read_secret("tushare_token.txt")


def _fetch(url: str, headers: dict = None, timeout: int = 10) -> dict:
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _cached(key: str, fetcher, ttl: int = CACHE_TTL):
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    entry = cache.get(key, {})
    if entry and time.time() - entry.get("ts", 0) < ttl:
        return entry.get("data", {})
    try:
        data = fetcher()
        cache[key] = {"ts": time.time(), "data": data}
        DATA.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    except Exception as e:
        if entry:
            return entry.get("data", {})
        return {"_error": str(e)[:100]}


# ═══════════════════ CoinMarketCap ═══════════════════
def cmc_quote(symbol: str = "BTC") -> dict:
    """CMC实时行情"""
    def fetch():
        d = _fetch(
            f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?symbol={symbol}",
            headers={"X-CMC_PRO_API_KEY": CMC_KEY},
        )
        coin = d["data"][symbol]
        q = coin["quote"]["USD"]
        return {
            "price": q["price"],
            "market_cap": q["market_cap"],
            "volume_24h": q["volume_24h"],
            "percent_change_24h": q["percent_change_24h"],
            "percent_change_7d": q.get("percent_change_7d", 0),
            "rank": coin["cmc_rank"],
            "dominance": q.get("market_cap_dominance", 0),
            "last_updated": coin["last_updated"],
        }
    return _cached(f"cmc_{symbol}", fetch, ttl=120)


def cmc_global() -> dict:
    """CMC全球加密指标"""
    def fetch():
        d = _fetch(
            "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest",
            headers={"X-CMC_PRO_API_KEY": CMC_KEY},
        )
        m = d["data"]
        q = m["quote"]["USD"]
        return {
            "total_mc": q["total_market_cap"],
            "total_vol": q["total_volume_24h"],
            "btc_dominance": m["btc_dominance"],
            "eth_dominance": m["eth_dominance"],
            "active_cryptos": m["active_cryptocurrencies"],
            "mc_change_24h": q.get("total_market_cap_yesterday_percentage_change", 0),
        }
    return _cached("cmc_global", fetch)


def cmc_fear_greed() -> dict:
    """CMC恐慌贪婪 (替代alternative.me)"""
    def fetch():
        d = _fetch(
            "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest",
            headers={"X-CMC_PRO_API_KEY": CMC_KEY},
        )
        fg = d["data"]
        return {
            "value": fg["value"],
            "classification": fg.get("value_classification", fg.get("classification", "")),
            "timestamp": fg.get("timestamp", fg.get("update_time", "")),
        }
    return _cached("cmc_fg", fetch, ttl=600)


# ═══════════════════ Alpha Vantage ═══════════════════
def av_quote(symbol: str = "AAPL") -> dict:
    """Alpha Vantage 股票报价"""
    def fetch():
        d = _fetch(
            f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={AV_KEY}"
        )
        q = d.get("Global Quote", {})
        return {
            "price": float(q.get("05. price", 0)),
            "change": float(q.get("09. change", 0)),
            "change_pct": q.get("10. change percent", "0%"),
            "volume": int(q.get("06. volume", 0)),
            "high": float(q.get("03. high", 0)),
            "low": float(q.get("04. low", 0)),
            "open": float(q.get("02. open", 0)),
        }
    return _cached(f"av_{symbol}", fetch, ttl=120)


# ═══════════════════ Twelve Data ═══════════════════
def td_technical(symbol: str = "AAPL") -> dict:
    """Twelve Data 技术指标 (RSI/MACD/BB)"""
    def fetch():
        result = {}
        # RSI
        try:
            d = _fetch(
                f"https://api.twelvedata.com/rsi?symbol={symbol}&interval=1h&apikey={TD_KEY}"
            )
            result["rsi"] = float(d["values"][0]["rsi"])
        except Exception:
            result["rsi"] = None
        # MACD
        try:
            d = _fetch(
                f"https://api.twelvedata.com/macd?symbol={symbol}&interval=1h&apikey={TD_KEY}"
            )
            v = d["values"][0]
            result["macd"] = float(v["macd"])
            result["macd_signal"] = float(v["macd_signal"])
            result["macd_hist"] = float(v["macd_hist"])
        except Exception:
            result["macd"] = None
        return result
    return _cached(f"td_{symbol}", fetch, ttl=300)


def td_quote(symbol: str = "AAPL") -> dict:
    """Twelve Data 实时报价"""
    def fetch():
        d = _fetch(
            f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={TD_KEY}"
        )
        return {
            "price": float(d.get("close", 0)),
            "open": float(d.get("open", 0)),
            "high": float(d.get("high", 0)),
            "low": float(d.get("low", 0)),
            "volume": int(d.get("volume", 0)),
            "change": float(d.get("change", 0)),
            "change_pct": d.get("percent_change", 0),
        }
    return _cached(f"tdq_{symbol}", fetch, ttl=60)


# ═══════════════════ 汇总输出 ═══════════════════

# ═══════════════════ Massive.com ═══════════════════
MASSIVE_KEY = _read_secret("massive_api_key.txt")

def massive_aggs(symbol: str = "AAPL", asset: str = "stock") -> dict:
    """Massive 日线聚合数据 (免费层可用)"""
    try:
        from massive import RESTClient
        client = RESTClient(api_key=MASSIVE_KEY)
        ticker = symbol if asset == "stock" else f"X:{symbol}USD"
        result = client.get_aggs(ticker=ticker, multiplier=1, timespan="day", 
                                  from_="2026-06-17", to="2026-06-18", limit=2)
        if isinstance(result, list) and len(result) > 0:
            r = result[-1]
            return {
                "open": float(r.open), "high": float(r.high),
                "low": float(r.low), "close": float(r.close),
                "volume": float(r.volume), "vwap": float(r.vwap),
                "timestamp": r.timestamp,
            }
    except Exception as e:
        return {"_error": str(e)[:80]}
    return {}


def massive_futures_snapshot(ticker: str = "ES") -> dict:
    """期货快照 (免费层)"""
    try:
        from massive import RESTClient
        client = RESTClient(api_key=MASSIVE_KEY)
        result = list(client.get_futures_snapshot(ticker=ticker, limit=1))
        if result:
            return {"snapshot": str(result[0])[:200]}
    except Exception as e:
        return {"_error": str(e)[:80]}
    return {}

def gather_all(asset_class: str = "crypto", symbol: str = "BTC") -> dict:
    """
    统一采集入口
    asset_class: crypto | stock | forex | metal
    """
    result = {"symbol": symbol, "asset_class": asset_class, "time": datetime.now(TZ).isoformat()}
    
    if asset_class == "crypto":
        try:
            result["cmc"] = cmc_quote(symbol)
        except Exception as e:
            result["cmc"] = {"_error": str(e)[:80]}
        try:
            result["cmc_global"] = cmc_global()
        except Exception:
            pass
        try:
            result["fear_greed"] = cmc_fear_greed()
        except Exception:
            pass
    elif asset_class == "stock":
        try:
            result["av"] = av_quote(symbol)
        except Exception as e:
            result["av"] = {"_error": str(e)[:80]}
        try:
            result["td"] = td_quote(symbol)
        except Exception:
            pass
        try:
            result["td_tech"] = td_technical(symbol)
        except Exception:
            pass
    
    return result


# ═══════════════════ CLI ═══════════════════
if __name__ == "__main__":
    import sys
    a = sys.argv[1] if len(sys.argv) > 1 else "crypto"
    s = sys.argv[2] if len(sys.argv) > 2 else "BTC"
    
    if a == "cmc_global":
        print(json.dumps(cmc_global(), indent=2, ensure_ascii=False))
    elif a == "fg":
        print(json.dumps(cmc_fear_greed(), indent=2, ensure_ascii=False))
    else:
        data = gather_all(a, s)
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
