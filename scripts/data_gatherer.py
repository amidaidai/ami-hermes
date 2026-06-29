#!/usr/bin/env python3
"""
棠溪 · 统一数据采集器 v3.1
变更：集成 browse.sh 技能 — CoinMarketCap全局指标+新闻、Cnyes金市新闻、Polymarket结构化预测
"""

import json, sys, time, hmac, hashlib, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# ─── 凭据加载（从 secrets 文件，不再硬编码） ───
import os as _os

def _load_json_secrets(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

_secrets = _load_json_secrets("D:/Hermes agent/hermes/secrets/binance.json")

API_KEY = _os.environ.get("BINANCE_API_KEY") or _secrets.get("api_key", "")
SECRET_KEY = _os.environ.get("BINANCE_SECRET_KEY") or _secrets.get("secret_key", "")

CG_KEY = _os.environ.get("CG_API_KEY", "") or "CG-tkuaqHxNbpTQ92HgpvEc4QXY"

def fetch(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def safe_fetch(url, headers=None, timeout=10, default=None):
    try:
        return fetch(url, headers, timeout)
    except Exception as e:
        return {"_error": str(e)[:120]}

def signed_futures(path, params_extra=""):
    """Binance 签名请求"""
    if not API_KEY or not SECRET_KEY:
        return {"_error": "Binance API keys not configured"}
    ts = int(time.time() * 1000)
    params = f"{params_extra}{'&' if params_extra else ''}timestamp={ts}"
    signature = hmac.new(SECRET_KEY.encode(), params.encode(), hashlib.sha256).hexdigest()
    url = f"https://fapi.binance.com{path}?{params}&signature={signature}"
    req = urllib.request.Request(url, headers={"X-MBX-APIKEY": API_KEY, "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)[:120]}

# ─── 快照容器 ───
snap = {
    "snapshot_time": datetime.now(TZ).isoformat(timespec="seconds"),
    "snapshot_ts": int(time.time()),
    "grades": {},
}

# ═══════════════════════════════════════
# 1. 价格 (Binance + CoinGecko)
# ═══════════════════════════════════════
bt = safe_fetch("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT")
bp = safe_fetch("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")

snap["binance_spot"] = {
    "price": float(bp.get("price", 0)) if isinstance(bp, dict) else None,
    "24h_high": float(bt.get("highPrice", 0)) if isinstance(bt, dict) else None,
    "24h_low": float(bt.get("lowPrice", 0)) if isinstance(bt, dict) else None,
    "24h_volume_btc": float(bt.get("volume", 0)) if isinstance(bt, dict) else None,
    "24h_change_pct": float(bt.get("priceChangePercent", 0)) if isinstance(bt, dict) else None,
}

cg = safe_fetch("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true",
    headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None)
snap["coingecko"] = {
    "price": cg.get("bitcoin", {}).get("usd") if isinstance(cg, dict) else None,
}

prices = [snap["binance_spot"]["price"], snap["coingecko"]["price"]]
prices = [p for p in prices if p is not None]
snap["price_consensus"] = {"sources": len(prices)}
if len(prices) >= 2:
    snap["price_consensus"]["max_deviation_pct"] = round((max(prices) - min(prices)) / min(prices) * 100, 3)

# ═══════════════════════════════════════
# 2. 衍生品 (Funding, OI, Basis)
# ═══════════════════════════════════════
fr = signed_futures("/fapi/v1/fundingRate", "symbol=BTCUSDT&limit=2")
snap["funding"] = {
    "current": float(fr[0]["fundingRate"]) if isinstance(fr, list) and fr else None,
    "previous": float(fr[1]["fundingRate"]) if isinstance(fr, list) and len(fr) > 1 else None,
    "history": [{"rate": float(d["fundingRate"]), "pct": f"{float(d['fundingRate'])*100:.4f}%"} for d in (fr if isinstance(fr, list) else [])[:5]],
}

oi = safe_fetch("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT")
snap["oi"] = {
    "btc": float(oi.get("openInterest", 0)) if isinstance(oi, dict) else None,
    "usd_nominal": float(oi.get("openInterest", 0)) * (snap["binance_spot"]["price"] or 0) if isinstance(oi, dict) else None,
}

basis = safe_fetch("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT")
snap["basis"] = {
    "mark": float(basis.get("markPrice", 0)) if isinstance(basis, dict) else None,
    "index": float(basis.get("indexPrice", 0)) if isinstance(basis, dict) else None,
    "premium_pct": round((float(basis["markPrice"]) / float(basis["indexPrice"]) - 1) * 100, 4) if isinstance(basis, dict) and basis.get("indexPrice") else None,
}

# ═══════════════════════════════════════
# 3. 大户多空比 + 全局多空比
# ═══════════════════════════════════════
ls = signed_futures("/futures/data/topLongShortAccountRatio", "symbol=BTCUSDT&period=5m&limit=2")
g_ls = signed_futures("/futures/data/globalLongShortAccountRatio", "symbol=BTCUSDT&period=5m&limit=2")

if isinstance(ls, list) and ls:
    latest = ls[-1]
    snap["long_short_top"] = {
        "long": round(float(latest["longAccount"]) * 100, 1),
        "short": round(float(latest["shortAccount"]) * 100, 1),
        "ratio": round(float(latest["longShortRatio"]), 2),
        "side": "long_dominant" if float(latest["longAccount"]) > 0.55 else "short_dominant" if float(latest["shortAccount"]) > 0.55 else "balanced",
        "quality": "A",
    }

if isinstance(g_ls, list) and g_ls:
    latest = g_ls[-1]
    snap["long_short_global"] = {
        "long": round(float(latest["longAccount"]) * 100, 1),
        "short": round(float(latest["shortAccount"]) * 100, 1),
        "ratio": round(float(latest["longShortRatio"]), 2),
        "side": "long_dominant" if float(latest["longAccount"]) > 0.52 else "short_dominant" if float(latest["shortAccount"]) > 0.52 else "balanced",
    }

# ═══════════════════════════════════════
# 4. Taker买卖量（期货，接近真实CVD）
# ═══════════════════════════════════════
taker = signed_futures("/futures/data/takerlongshortRatio", "symbol=BTCUSDT&period=5m&limit=3")
if isinstance(taker, list) and taker:
    latest = taker[-1]
    snap["taker_futures"] = {
        "buy_vol_btc": round(float(latest["buyVol"]), 2),
        "sell_vol_btc": round(float(latest["sellVol"]), 2),
        "ratio": round(float(latest["buySellRatio"]), 3),
        "direction": "buy" if float(latest["buySellRatio"]) > 1.1 else "sell" if float(latest["buySellRatio"]) < 0.9 else "neutral",
        "history": [{"buy": round(float(d["buyVol"]), 1), "sell": round(float(d["sellVol"]), 1), "ratio": round(float(d["buySellRatio"]), 2)} for d in taker],
        "quality": "B",
    }

# ═══════════════════════════════════════
# 5. 市场情绪 (恐慌贪婪指数)
# ═══════════════════════════════════════
fng = safe_fetch("https://api.alternative.me/fng/?limit=5")
snap["fear_greed"] = {"error": "unavailable"}
if isinstance(fng, dict) and fng.get("data"):
    items = fng["data"]
    snap["fear_greed"] = {
        "current": int(items[0]["value"]),
        "classification": items[0]["value_classification"],
        "trend_5d": [int(d["value"]) for d in items],
        "trend_text": "→".join(str(int(d["value"])) for d in items),
        "signal": "极度恐惧·历史底部区域" if int(items[0]["value"]) < 25 else "恐惧" if int(items[0]["value"]) < 45 else "中性" if int(items[0]["value"]) < 55 else "贪婪" if int(items[0]["value"]) < 75 else "极度贪婪",
    }

# ═══════════════════════════════════════
# 6. XAUUSD 价格 (三源：金十 + Yahoo GC=F + Yahoo MGC=F)
# ═══════════════════════════════════════
xau_prices = []

# 金十 Quote
xau_jin10 = safe_fetch("https://api.jin10.com/quote/XAUUSD", timeout=10)
if isinstance(xau_jin10, dict) and xau_jin10.get("close") and not xau_jin10.get("_error"):
    try:
        xau_prices.append({"source": "jin10", "price": float(xau_jin10["close"])})
    except Exception:
        pass

# Yahoo GC=F (黄金期货)
xau_gc = safe_fetch("https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=2d", timeout=10)
if isinstance(xau_gc, dict):
    try:
        meta = xau_gc.get("chart", {}).get("result", [{}])[0].get("meta", {})
        if meta.get("regularMarketPrice"):
            xau_prices.append({"source": "yahoo_gc", "price": float(meta["regularMarketPrice"])})
    except Exception:
        pass

# Yahoo MGC=F (微型黄金期货)
xau_mgc = safe_fetch("https://query1.finance.yahoo.com/v8/finance/chart/MGC=F?interval=1d&range=2d", timeout=10)
if isinstance(xau_mgc, dict):
    try:
        meta = xau_mgc.get("chart", {}).get("result", [{}])[0].get("meta", {})
        if meta.get("regularMarketPrice"):
            xau_prices.append({"source": "yahoo_mgc", "price": float(meta["regularMarketPrice"])})
    except Exception:
        pass

snap["xau"] = {
    "prices": xau_prices,
    "consensus_price": round(sum(p["price"] for p in xau_prices) / len(xau_prices), 2) if xau_prices else None,
    "sources": len(xau_prices),
    "quality": "A" if len(xau_prices) >= 3 else "B" if len(xau_prices) >= 2 else "C",
}

# ═══════════════════════════════════════
# 7. XAU 宏观上下文 (DXY/美债/TIP/白银/GLD)
# ═══════════════════════════════════════
snap["xau_macro"] = {}
xau_macro_map = {
    "dxy": "DX-Y.NYB",
    "eurusd": "EURUSD=X",
    "usdjpy": "USDJPY=X",
    "us10y": "^TNX",
    "us02y": "^IRX",
    "tip": "TIP",
    "tlt": "TLT",
    "gold_fut": "GC=F",
    "silver_fut": "SI=F",
    "gld": "GLD",
    "gdx": "GDX",
    "move": "^MOVE",
}
for key, symbol in xau_macro_map.items():
    data = safe_fetch(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d", timeout=10)
    if isinstance(data, dict):
        try:
            meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
            if meta.get("regularMarketPrice"):
                snap["xau_macro"][key] = {
                    "symbol": symbol,
                    "price": float(meta["regularMarketPrice"]),
                }
        except Exception:
            pass

# ═══════════════════════════════════════
# 8. 市场情绪扩展 (X情绪占位 + CoinMarketCap全局指标 + Polymarket)
# ═══════════════════════════════════════
snap["sentiment"] = {
    "x": {"status": "pending", "note": "X情绪需agent上下文·分析卡Step1b调x_search()取实时情绪·此处仅占位提醒"},
}

# ─── 8a. CoinMarketCap 全局指标 (替代旧 CoinDesk RSS) ───
# browse.sh skill: coinmarketcap.com/fetch-crypto-data
# 公开JSON API，无需认证
cmc_global = safe_fetch(
    "https://api.coinmarketcap.com/data-api/v3/global-metrics/quotes/latest?convert=USD",
    timeout=10
)
if isinstance(cmc_global, dict) and not cmc_global.get("_error"):
    d = cmc_global.get("data", {})
    q = d.get("quotes", [{}])[0] if d.get("quotes") else {}
    snap["sentiment"]["cmc_global"] = {
        "btc_dominance_pct": d.get("btcDominance"),
        "eth_dominance_pct": d.get("ethDominance"),
        "active_cryptocurrencies": d.get("activeCryptoCurrencies"),
        "total_market_cap": q.get("totalMarketCap"),
        "total_volume_24h": q.get("totalVolume24H"),
        "defi_market_cap": d.get("defiMarketCap"),
        "stablecoin_market_cap": d.get("stablecoinMarketCap"),
        "defi_volume_24h": d.get("defiVolume24h"),
        "derivatives_volume_24h": d.get("derivativesVolume24h"),
        "quality": "A",
    }

# ─── 8b. CoinMarketCap 最新加密新闻 (无认证) ───
cmc_news = safe_fetch(
    "https://api.coinmarketcap.com/content/v3/news?size=5",
    timeout=10
)
if isinstance(cmc_news, dict) and not cmc_news.get("_error"):
    articles = cmc_news.get("data", [])
    snap["sentiment"]["cmc_news"] = [
        {
            "title": a.get("meta", {}).get("title"),
            "source": a.get("meta", {}).get("sourceName"),
            "released_at": a.get("meta", {}).get("releasedAt"),
            "url": a.get("meta", {}).get("sourceUrl"),
        }
        for a in articles[:5] if a.get("meta")
    ]

# ─── 8c. Polymarket 金融市场预测 (替代旧简单占位) ───
# browse.sh skill: polymarket.com/polymarket-research
# Gamma API 公开无认证，搜索财经类活跃预测市场
pm = safe_fetch(
    "https://gamma-api.polymarket.com/public-search?q=crypto+bitcoin+gold+finance&limit_per_type=5&events_status=active",
    timeout=15
)
if isinstance(pm, dict) and not pm.get("_error"):
    evts = pm.get("events", [])
    snap["sentiment"]["polymarket"] = {
        "count": len(evts),
        "events": [
            {
                "title": e.get("title"),
                "slug": e.get("slug"),
                "volume": e.get("volume"),
                "end_date": e.get("endDate"),
                "markets": [
                    {
                        "question": m.get("question"),
                        "yes_prob": round(float(json.loads(m.get("outcomePrices", "[0.5]"))[0]), 4) if m.get("outcomePrices") else None,
                        "volume": m.get("volumeNum"),
                    }
                    for m in (e.get("markets") or [])
                ][:3],
            }
            for e in evts[:5]
        ],
        "quality": "B",
    }
else:
    # fallback: 原简单端点
    pm_fb = safe_fetch("https://gamma-api.polymarket.com/events?tag=finance&limit=5&closed=false", timeout=10)
    if isinstance(pm_fb, list) and pm_fb:
        snap["sentiment"]["polymarket"] = {
            "events": [{"title": e.get("title"), "slug": e.get("slug")} for e in pm_fb[:5]],
            "count": len(pm_fb),
            "quality": "C",
        }

# ═══════════════════════════════════════
# 8d. Cnyes 金市/宏观中文新闻 (浏览技能集成)
# browse.sh skill: cnyes.com/search-financial-news
# 公开API，搜索"黃金" = 金市新闻
# ═══════════════════════════════════════
snap["sentiment"]["cnyes_news"] = []
for kw in ["黃金 XAUUSD", "金價 美元", "聯準會 利率"]:
    kw_enc = urllib.parse.quote(kw)
    news_data = safe_fetch(
        f"https://api.cnyes.com/media/api/v1/search/news?q={kw_enc}&page=1",
        timeout=12
    )
    if isinstance(news_data, dict) and not news_data.get("_error"):
        items = news_data.get("items", {}).get("data", [])
        for item in items[:3]:
            import re as _re
            snap["sentiment"]["cnyes_news"].append({
                "query": kw,
                "newsId": item.get("newsId"),
                "title": _re.sub(r'</?mark>', '', item.get("title", "")),
                "published_at_taipei": item.get("publishAt"),
                "byline": item.get("signature"),
                "category": item.get("category", [{}])[0].get("name") if item.get("category") else None,
                "keywords": item.get("keyword", []),
                "url": f"https://news.cnyes.com/news/id/{item.get('newsId')}",
            })

# ═══════════════════════════════════════
# 9. 宏观关联 (Yahoo) — 原有保留
# ═══════════════════════════════════════
for symbol, key in [
    ("DX-Y.NYB", "dxy"), ("%5EVIX", "vix"), ("%5EGSPC", "spx"), ("%5ETNX", "us10y")
]:
    data = safe_fetch(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d")
    if isinstance(data, dict):
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        snap[key] = {"value": meta.get("regularMarketPrice")}

# ═══════════════════════════════════════
# 10. 综合可用性标记
# ═══════════════════════════════════════
snap["available"] = {
    "price": len(prices) >= 2,
    "funding": snap["funding"]["current"] is not None,
    "oi": snap["oi"]["btc"] is not None,
    "basis": snap["basis"]["premium_pct"] is not None,
    "long_short_top": "long" in snap.get("long_short_top", {}),
    "long_short_global": "long" in snap.get("long_short_global", {}),
    "taker_futures": "buy_vol_btc" in snap.get("taker_futures", {}),
    "xau": len(xau_prices) >= 2,
    "xau_macro": len(snap.get("xau_macro", {})) >= 5,
    "cnyes_news": len(snap.get("sentiment", {}).get("cnyes_news", [])) >= 3,
    "cmc_global": "btc_dominance_pct" in snap.get("sentiment", {}).get("cmc_global", {}),
    "sentiment_polymarket": isinstance(snap.get("sentiment", {}).get("polymarket"), dict),
    "macro": snap.get("dxy", {}).get("value") is not None,
    "liquidation": False,
    "cvd_a_grade": False,
}

# ═══════════════════════════════════════
# 10. 账户余额（从Binance实时获取）
# ═══════════════════════════════════════
try:
    acct = signed_futures("/fapi/v2/account", "")
    if isinstance(acct, dict) and acct.get("totalWalletBalance"):
        snap["account_balance"] = round(float(acct["totalWalletBalance"]), 2)
    else:
        snap["account_balance"] = None
except:
    snap["account_balance"] = None

all_available = sum(1 for v in snap["available"].values() if v)
total = len(snap["available"])
if all_available >= total - 1:
    snap["grades"]["overall"] = "A"
elif all_available >= total - 3:
    snap["grades"]["overall"] = "B"
else:
    snap["grades"]["overall"] = "C"

print(json.dumps(snap, indent=2, ensure_ascii=False, default=str))
