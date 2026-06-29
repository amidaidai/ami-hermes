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
FMP_KEY = _read_secret("fmp_api_key.txt")
MASSIVE_KEY = _read_secret("massive_api_key.txt")
CG_KEY = _read_secret("coingecko_api_key.txt") or os.environ.get("CG_API_KEY", "") or "CG-tkuaqHxNbpTQ92HgpvEc4QXY"


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


# ═══════════════════ CoinGecko (Free · FinanceKit替代) ═══════════════════

CG_BASE = "https://api.coingecko.com/api/v3"


def cg_top_coins(n: int = 10) -> dict:
    """Top N 加密排名 + BTC/ETH 市占率变化 → 板块轮动检测"""
    def fetch():
        d = _fetch(f"{CG_BASE}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={n}&page=1&sparkline=false&price_change_percentage=1h,24h,7d",
            headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None)
        coins = []
        btc_dom_shift = 0
        for c in d:
            coins.append({
                "symbol": c["symbol"].upper(),
                "name": c["name"],
                "price": c["current_price"],
                "mc_rank": c.get("market_cap_rank"),
                "change_1h": c.get("price_change_percentage_1h_in_currency", 0),
                "change_24h": c.get("price_change_percentage_24h", 0),
                "change_7d": c.get("price_change_percentage_7d_in_currency", 0),
                "mc": c.get("market_cap", 0),
            })
            if c["symbol"].upper() == "BTC":
                btc_dom_shift = c.get("price_change_percentage_24h", 0)
        # Sector rotation signal: if BTC << alt avg → alt season
        alt_changes = [c["change_24h"] for c in coins if c["symbol"] not in ("BTC", "ETH", "USDT", "USDC")]
        avg_alt = sum(alt_changes) / len(alt_changes) if alt_changes else 0
        btc_change = next((c["change_24h"] for c in coins if c["symbol"] == "BTC"), 0)
        rotation = "BTC主导" if btc_change > avg_alt + 1 else "山寨季" if avg_alt > btc_change + 3 else "同步"
        return {
            "top_coins": coins,
            "btc_change_24h": btc_change,
            "avg_alt_change_24h": round(avg_alt, 2),
            "rotation": rotation,
            "coin_count": len(coins),
        }
    return _cached("cg_top", fetch, ttl=300)


def cg_trending() -> dict:
    """CoinGecko trending → 山寨热点检测"""
    def fetch():
        d = _fetch(f"{CG_BASE}/search/trending",
            headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None)
        coins = d.get("coins", [])[:7]
        items = []
        for c in coins:
            item = c.get("item", {})
            items.append({
                "symbol": item.get("symbol", "").upper(),
                "name": item.get("name", ""),
                "mc_rank": item.get("market_cap_rank"),
                "score": item.get("score", 0),
            })
        return {"trending": items, "count": len(items)}
    return _cached("cg_trend", fetch, ttl=600)


# ═══════════════════ CoinGecko Pro 新增端点 ═══════════════════

def cg_coin_detail(coin_id: str = "bitcoin") -> dict:
    """CoinGecko Pro 币种详情 — 流动性评分/社区/开发者数据"""
    def fetch():
        d = _fetch(
            f"{CG_BASE}/coins/{coin_id}?localization=false&tickers=false&community_data=true&developer_data=true&market_data=true",
            headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None,
        )
        md = d.get("market_data", {})
        cd = d.get("community_data", {})
        dd = d.get("developer_data", {})
        return {
            "name": d.get("name", ""),
            "symbol": d.get("symbol", "").upper(),
            "liquidity_score": md.get("liquidity_score"),
            "market_cap_fdv_ratio": md.get("market_cap_fdv_ratio"),
            "total_value_locked": md.get("total_value_locked"),
            "community_score": cd.get("community_score"),
            "twitter_followers": cd.get("twitter_followers"),
            "reddit_subscribers": cd.get("reddit_subscribers"),
            "dev_score": dd.get("score"),
            "github_stars": dd.get("stars"),
            "github_commits_4w": dd.get("commit_count_4_weeks"),
            "sentiment_votes_up_pct": d.get("sentiment_votes_up_percentage"),
            "sentiment_votes_down_pct": d.get("sentiment_votes_down_percentage"),
            "coingecko_score": d.get("coingecko_score"),
            "coingecko_rank": d.get("coingecko_rank"),
        }
    return _cached(f"cg_detail_{coin_id}", fetch, ttl=600)


def cg_categories() -> dict:
    """CoinGecko 板块/分类涨幅 — 轮动检测"""
    def fetch():
        d = _fetch(
            f"{CG_BASE}/coins/categories",
            headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None,
        )
        cats = []
        for c in d[:20]:
            cats.append({
                "name": c.get("name"),
                "change_24h": c.get("market_cap_change_24h"),
                "mc": c.get("market_cap"),
                "vol_24h": c.get("volume_24h"),
                "top_coins": c.get("top_3_coins", []),
            })
        # Sort by 24h change to detect rotation
        cats.sort(key=lambda x: x.get("change_24h", 0) or 0, reverse=True)
        top_cat = cats[0]["name"] if cats else ""
        bottom_cat = cats[-1]["name"] if cats else ""
        return {
            "categories": cats,
            "top_performer": top_cat,
            "bottom_performer": bottom_cat,
            "rotation_signal": f"资金流向: {top_cat} / 流出: {bottom_cat}" if cats else "N/A",
        }
    return _cached("cg_categories", fetch, ttl=600)


def cg_exchange_volumes(coin_id: str = "bitcoin") -> dict:
    """CoinGecko Pro 交易所成交量明细 — BTC 流动性验证"""
    def fetch():
        d = _fetch(
            f"{CG_BASE}/coins/{coin_id}/tickers?order=volume_desc&depth=true",
            headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None,
        )
        tickers = d.get("tickers", [])
        # Aggregate by exchange
        ex_map = {}
        for t in tickers[:50]:
            ex_name = t.get("market", {}).get("name", "Unknown")
            vol = t.get("converted_volume", {}).get("usd", 0) or 0
            ts = t.get("trust_score", "")
            if ex_name not in ex_map:
                ex_map[ex_name] = {"volume_usd": 0, "trust": ts, "pairs": 0}
            ex_map[ex_name]["volume_usd"] += vol
            ex_map[ex_name]["pairs"] += 1
        # Top exchanges by volume
        top_ex = sorted(ex_map.items(), key=lambda x: x[1]["volume_usd"], reverse=True)[:10]
        total_vol = sum(v["volume_usd"] for _, v in top_ex)
        exchanges = [{"exchange": n, "vol_24h_usd": v["volume_usd"],
                       "vol_share_pct": round(v["volume_usd"]/total_vol*100, 1) if total_vol else 0,
                       "trust": v["trust"], "pairs": v["pairs"]} for n, v in top_ex]
        # Flag low-trust exchanges (>10% volume on red/orange trust)
        low_trust_vol = sum(e["vol_share_pct"] for e in exchanges
                            if e["trust"] in ("red", "orange"))
        return {
            "exchanges": exchanges,
            "total_vol_24h": total_vol,
            "low_trust_vol_pct": round(low_trust_vol, 1),
            "volume_health": "✅" if low_trust_vol < 15 else "⚠" if low_trust_vol < 30 else "🚩",
        }
    return _cached(f"cg_exvol_{coin_id}", fetch, ttl=600)


# ═══════════════════ 市场概览 (SPX/VIX · FMP) ═══════════════════

def macro_overview() -> dict:
    """SPX + VIX + US10Y + DXY + Gold — 宏观快照"""
    def fetch():
        result = {}
        symbols = ["^GSPC", "^VIX", "^TNX", "DX-Y.NYB", "GC=F"]
        labels = {"^GSPC": "spx", "^VIX": "vix", "^TNX": "us10y", "DX-Y.NYB": "dxy", "GC=F": "gold_fut"}
        for sym in symbols:
            try:
                d = _fetch(
                    f"https://financialmodelingprep.com/api/v3/quote/{sym}?apikey={FMP_KEY}"
                )
                if isinstance(d, list) and d:
                    q = d[0]
                    result[labels[sym]] = {
                        "price": float(q.get("price", 0)),
                        "change_pct": q.get("changesPercentage", 0),
                        "change": float(q.get("change", 0)),
                    }
            except Exception:
                pass
        # 宏观情绪分类
        vix_val = result.get("vix", {}).get("price", 20)
        spx_chg = result.get("spx", {}).get("change_pct", 0)
        if vix_val > 30:
            sentiment = "恐慌 (Risk-off)"
        elif vix_val > 22:
            sentiment = "谨慎 (Risk-off 偏)"
        elif spx_chg < -1:
            sentiment = "避险 (Risk-off)"
        elif spx_chg > 1 and vix_val < 18:
            sentiment = "乐观 (Risk-on)"
        else:
            sentiment = "中性"
        result["sentiment"] = sentiment
        result["vix_level"] = vix_val
        return result
    return _cached("macro", fetch, ttl=300)


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

def massive_aggs(symbol: str = "AAPL", asset: str = "stock") -> dict:
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


# ═══════════════════ FMP (Financial Modeling Prep) ═══════════════════
def fmp_quote(symbol: str = "AAPL") -> dict:
    """FMP 股票/ETF 实时行情"""
    def fetch():
        d = _fetch(
            f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={FMP_KEY}"
        )
        if isinstance(d, list) and d:
            q = d[0]
            return {
                "price": float(q.get("price", 0)),
                "change": float(q.get("change", 0)),
                "change_pct": q.get("changesPercentage", 0),
                "volume": int(q.get("volume", 0)),
                "high": float(q.get("dayHigh", 0)),
                "low": float(q.get("dayLow", 0)),
                "open": float(q.get("open", 0)),
                "prev_close": float(q.get("previousClose", 0)),
                "market_cap": q.get("marketCap", 0),
                "pe": q.get("pe", None),
            }
        return {}
    return _cached(f"fmp_{symbol}", fetch, ttl=120)


def fmp_forex(pair: str = "EURUSD") -> dict:
    """FMP 外汇实时行情"""
    def fetch():
        d = _fetch(
            f"https://financialmodelingprep.com/api/v3/quote/{pair}?apikey={FMP_KEY}"
        )
        if isinstance(d, list) and d:
            q = d[0]
            return {
                "price": float(q.get("price", 0)),
                "change": float(q.get("change", 0)),
                "change_pct": q.get("changesPercentage", 0),
                "high": float(q.get("dayHigh", 0)),
                "low": float(q.get("dayLow", 0)),
            }
        return {}
    return _cached(f"fmpfx_{pair}", fetch, ttl=60)

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
        try:
            result["cg_top"] = cg_top_coins(10)
        except Exception:
            pass
        try:
            result["cg_trending"] = cg_trending()
        except Exception:
            pass
        try:
            result["cg_detail"] = cg_coin_detail("bitcoin" if symbol.upper() == "BTC" else symbol.lower())
        except Exception:
            pass
        try:
            result["cg_categories"] = cg_categories()
        except Exception:
            pass
        try:
            result["macro"] = macro_overview()
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
