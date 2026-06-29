#!/usr/bin/env python3
"""
棠溪 · CoinGecko 社区数据采集器 v1.0
免费 · 无需 API Key · 10-30次/分钟限速

输入：asset_class (crypto/metal/forex)
输出：社区情绪 + 全球加密指标 + 汇率
"""

import json, time, os, urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
TZ = timezone(timedelta(hours=8))
CACHE_FILE = Path("D:/Hermes agent/data/coingecko_cache.json")
CACHE_TTL = 300  # 5分钟缓存
CG_KEY = os.environ.get("CG_API_KEY", "") or "CG-tkuaqHxNbpTQ92HgpvEc4QXY"

def _fetch(url: str) -> dict:
    headers = {"User-Agent": UA}
    if CG_KEY and "coingecko.com" in url:
        headers["x-cg-pro-api-key"] = CG_KEY
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read()
        # Handle encoding issues
        for enc in ['utf-8', 'latin-1', 'cp1252']:
            try:
                return json.loads(raw.decode(enc))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        return json.loads(raw.decode('utf-8', errors='replace'))


def _cached(key: str, fetcher, ttl: int = CACHE_TTL) -> dict:
    """带缓存的抓取"""
    cache = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    entry = cache.get(key, {})
    if entry and time.time() - entry.get("ts", 0) < ttl:
        return entry.get("data", {})
    
    try:
        data = fetcher()
        cache[key] = {"ts": time.time(), "data": data}
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    except Exception as e:
        if entry:
            return entry.get("data", {})
        return {"_error": str(e)[:100]}


def get_global_crypto() -> dict:
    """全球加密市场指标"""
    def fetch():
        d = _fetch("https://api.coingecko.com/api/v3/global")
        data = d.get("data", {})
        mkt = data.get("market_cap_percentage", {})
        return {
            "btc_dominance": mkt.get("btc", 0),
            "eth_dominance": mkt.get("eth", 0),
            "total_mc_usd": data.get("total_market_cap", {}).get("usd", 0),
            "total_vol_usd": data.get("total_volume", {}).get("usd", 0),
            "mc_change_24h_pct": data.get("market_cap_change_percentage_24h_usd", 0),
            "active_cryptos": data.get("active_cryptocurrencies", 0),
        }
    return _cached("global", fetch)


def get_btc_community() -> dict:
    """BTC 社区数据"""
    def fetch():
        d = _fetch("https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&community_data=true&developer_data=false&market_data=false")
        c = d.get("community_data", {})
        s_up = d.get("sentiment_votes_up_percentage")
        s_down = d.get("sentiment_votes_down_percentage")
        return {
            "reddit_subscribers": c.get("reddit_subscribers", 0),
            "reddit_avg_posts_48h": c.get("reddit_average_posts_48h", 0),
            "reddit_avg_comments_48h": c.get("reddit_average_comments_48h", 0),
            "reddit_active_48h": c.get("reddit_accounts_active_48h", 0),
            "twitter_followers": c.get("twitter_followers", 0),
            "telegram_users": c.get("telegram_channel_user_count", 0),
            "sentiment_up_pct": s_up,
            "sentiment_down_pct": s_down,
        }
    return _cached("btc_community", fetch)


def get_forex_rates() -> dict:
    """外汇汇率 (via CoinGecko exchange_rates)"""
    def fetch():
        d = _fetch("https://api.coingecko.com/api/v3/exchange_rates")
        rates = d.get("rates", {})
        return {
            "EUR": rates.get("eur", {}).get("value"),
            "JPY": rates.get("jpy", {}).get("value"),
            "CNY": rates.get("cny", {}).get("value"),
            "GBP": rates.get("gbp", {}).get("value"),
            "XAU": rates.get("xau", {}).get("value"),  # 单位特殊·仅供参考
            "XAG": rates.get("xag", {}).get("value"),
        }
    return _cached("forex", fetch, ttl=600)  # 汇率10分钟缓存


def get_trending() -> list:
    """热门币种"""
    def fetch():
        d = _fetch("https://api.coingecko.com/api/v3/search/trending")
        coins = d.get("coins", [])
        return [{
            "name": c.get("item", {}).get("name"),
            "symbol": c.get("item", {}).get("symbol"),
            "rank": c.get("item", {}).get("market_cap_rank"),
            "score": c.get("item", {}).get("score"),
        } for c in coins[:5]]
    return _cached("trending", fetch, ttl=600)


def crypto_sentiment_summary() -> str:
    """加密情绪一句话总结"""
    try:
        fng = _fetch("https://api.alternative.me/fng/?limit=1")
        fg_val = int(fng["data"][0]["value"])
        fg_label = fng["data"][0]["value_classification"]
    except Exception:
        fg_val, fg_label = 50, "N/A"
    
    try:
        global_d = get_global_crypto()
        btc_d = global_d.get("btc_dominance", 0)
        mc_chg = global_d.get("mc_change_24h_pct", 0)
    except Exception:
        btc_d, mc_chg = 0, 0
    
    try:
        comm = get_btc_community()
        reddit = comm.get("reddit_avg_posts_48h", 0)
    except Exception:
        reddit = 0
    
    # 情绪倾向
    if fg_val <= 25:
        bias = "极度恐慌·反指偏多"
    elif fg_val <= 45:
        bias = "恐慌·谨慎偏多"
    elif fg_val <= 55:
        bias = "中性"
    elif fg_val <= 75:
        bias = "贪婪·谨慎偏空"
    else:
        bias = "极度贪婪·反指偏空"
    
    return f"恐慌贪婪{fg_val}({fg_label})·{bias} · BTC市占{btc_d:.1f}% · 总市值日变{mc_chg:+.1f}% · Reddit {reddit}帖/48h"



def get_btc_sentiment() -> dict:
    """BTC CoinGecko 情绪投票"""
    def fetch():
        d = _fetch("https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&community_data=false&developer_data=false&market_data=false")
        return {
            "sentiment_up_pct": d.get("sentiment_votes_up_percentage", 0),
            "sentiment_down_pct": d.get("sentiment_votes_down_percentage", 0),
            "watchlist_users": d.get("watchlist_portfolio_users", 0),
            "market_cap_rank": d.get("market_cap_rank", 0),
        }
    return _cached("btc_sentiment", fetch)


def get_category_heat() -> list:
    """CoinGecko 板块热度"""
    def fetch():
        cats = _fetch("https://api.coingecko.com/api/v3/coins/categories")
        return [{
            "name": c["name"],
            "mc_usd": c.get("market_cap", 0),
            "mc_change_24h": c.get("market_cap_change_24h", 0) or 0,
            "volume_24h": c.get("volume_24h", 0),
        } for c in cats[:5]]
    return _cached("cat_heat", fetch, ttl=600)


def get_reddit_sentiment():
    """Reddit 加密社区情绪 (免费·无需Key)"""
    try:
        headers = {"User-Agent": "python:棠溪-trading-bot:v1.0"}
        # r/Bitcoin
        req = urllib.request.Request("https://www.reddit.com/r/Bitcoin/about.json", headers=headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read()
            for enc in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    data = json.loads(raw.decode(enc)).get("data", {})
                    break
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            else:
                data = {}
        btc_subs = data.get("subscribers", 0)
        btc_active = data.get("active_user_count", 0)
    except Exception:
        btc_subs = btc_active = 0
    
    try:
        # r/CryptoCurrency hot posts
        req2 = urllib.request.Request("https://www.reddit.com/r/CryptoCurrency/hot.json?limit=5", headers=headers)
        with urllib.request.urlopen(req2, timeout=8) as r2:
            raw2 = r2.read()
            for enc in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    posts = json.loads(raw2.decode(enc)).get("data", {}).get("children", [])
                    break
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            else:
                posts = []
        hot_posts = [{
            "title": p["data"]["title"][:80],
            "score": p["data"]["score"],
            "comments": p["data"]["num_comments"],
        } for p in posts[:5]]
    except Exception:
        hot_posts = []
    
    return {
        "btc_subs": btc_subs,
        "btc_active": btc_active,
        "cc_hot_posts": hot_posts,
    }


def community_dashboard() -> str:
    """社区全景一句话+详情"""
    lines = []
    
    # CMC F&G
    try:
        fng = _fetch("https://api.alternative.me/fng/?limit=1")
        fg_v = int(fng["data"][0]["value"])
        fg_l = fng["data"][0]["value_classification"]
        lines.append(f"恐慌贪婪: {fg_v} ({fg_l})")
    except Exception:
        lines.append("恐慌贪婪: N/A")
    
    # CG Sentiment
    try:
        s = get_btc_sentiment()
        up = s.get("sentiment_up_pct", 0)
        lines.append(f"CG情绪: {up:.0f}%看多 · {s.get('watchlist_users',0):,}人关注BTC")
    except Exception:
        pass
    
    # CG Trending
    try:
        trending = _cached("trending_cache", 
            lambda: _fetch("https://api.coingecko.com/api/v3/search/trending"),
            ttl=600)
        top3 = [c["item"]["name"] for c in trending.get("coins", [])[:3]]
        lines.append(f"热门: {'·'.join(top3)}")
    except Exception:
        pass
    
    # Category
    try:
        cats = get_category_heat()
        best = max(cats, key=lambda x: x.get("mc_change_24h", -999) or -999)
        lines.append(f"板块: {best['name']} {best.get('mc_change_24h',0):+.1f}%")
    except Exception:
        pass
    
    return " · ".join(lines)

if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if action == "global":
        print(json.dumps(get_global_crypto(), indent=2, ensure_ascii=False))
    elif action == "btc_community":
        print(json.dumps(get_btc_community(), indent=2, ensure_ascii=False))
    elif action == "forex":
        print(json.dumps(get_forex_rates(), indent=2, ensure_ascii=False))
    elif action == "trending":
        print(json.dumps(get_trending(), indent=2, ensure_ascii=False))
    elif action == "sentiment":
        print(crypto_sentiment_summary())
    else:
        print("=== 全球加密 ===")
        print(json.dumps(get_global_crypto(), indent=2))
        print("\n=== BTC 社区 ===")
        print(json.dumps(get_btc_community(), indent=2))
        print("\n=== 外汇汇率 ===")
        print(json.dumps(get_forex_rates(), indent=2))
        print("\n=== 情绪一句话 ===")
        print(crypto_sentiment_summary())
