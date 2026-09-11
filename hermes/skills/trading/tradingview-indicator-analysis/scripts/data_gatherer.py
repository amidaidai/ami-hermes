#!/usr/bin/env python3
"""
棠溪 · 统一数据采集器 v1.0
替换散落各处的 ad-hoc 数据拉取，单一脚本输出标准化数据快照。
输出：JSON 到 stdout，供分析卡和监控脚本消费。

数据源：Binance现货+合约 / CoinGecko / Yahoo(DXY/VIX/SPX/US10Y) / Bybit(费率交叉验证)
"""

import json, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

def fetch(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def safe_fetch(url, headers=None, timeout=10, default=None):
    try:
        return fetch(url, headers, timeout)
    except Exception as e:
        return {"_error": str(e)[:120]}

snap = {
    "snapshot_time": datetime.now(TZ).isoformat(timespec="seconds"),
    "snapshot_ts": int(time.time()),
    "grades": {},
}

# 1. Binance spot price
binance_ticker = safe_fetch("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT")
binance_price = safe_fetch("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
snap["binance_spot"] = {
    "price": float(binance_price.get("price", 0)) if isinstance(binance_price, dict) else None,
    "24h_high": float(binance_ticker.get("highPrice", 0)) if isinstance(binance_ticker, dict) else None,
    "24h_low": float(binance_ticker.get("lowPrice", 0)) if isinstance(binance_ticker, dict) else None,
    "24h_volume_btc": float(binance_ticker.get("volume", 0)) if isinstance(binance_ticker, dict) else None,
    "24h_change_pct": float(binance_ticker.get("priceChangePercent", 0)) if isinstance(binance_ticker, dict) else None,
}

# 2. CoinGecko
cg = safe_fetch("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true")
snap["coingecko"] = {
    "price": cg.get("bitcoin", {}).get("usd") if isinstance(cg, dict) else None,
    "24h_change_pct": cg.get("bitcoin", {}).get("usd_24h_change") if isinstance(cg, dict) else None,
}

# 3. Price consensus
prices = [snap["binance_spot"]["price"], snap["coingecko"]["price"]]
prices = [p for p in prices if p is not None]
if len(prices) >= 2:
    max_dev = (max(prices) - min(prices)) / min(prices) * 100
    snap["price_consensus"] = {"sources": len(prices), "max_deviation_pct": round(max_dev, 3)}
    snap["grades"]["price"] = "A" if max_dev <= 0.15 else "B" if max_dev <= 0.30 else "C"
elif len(prices) == 1:
    snap["price_consensus"] = {"sources": 1, "max_deviation_pct": None}
    snap["grades"]["price"] = "C"
else:
    snap["grades"]["price"] = "C"

# 4. Derivatives (Binance futures)
fr = safe_fetch("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1")
snap["funding"] = {
    "rate": float(fr[0]["fundingRate"]) if isinstance(fr, list) and fr else None,
    "direction": "negative" if isinstance(fr, list) and fr and float(fr[0]["fundingRate"]) < 0 else "positive",
}

oi = safe_fetch("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT")
snap["oi"] = {
    "btc": float(oi.get("openInterest", 0)) if isinstance(oi, dict) else None,
}

basis = safe_fetch("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT")
snap["basis"] = {
    "mark_price": float(basis.get("markPrice", 0)) if isinstance(basis, dict) else None,
    "index_price": float(basis.get("indexPrice", 0)) if isinstance(basis, dict) else None,
}

# 5. Bybit funding cross-check
bybit_fr = safe_fetch("https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1")
if isinstance(bybit_fr, dict) and bybit_fr.get("result", {}).get("list"):
    bybit_rate = float(bybit_fr["result"]["list"][0].get("fundingRate", 0))
    snap["funding"]["bybit_rate"] = bybit_rate
    snap["funding"]["exchange_consensus"] = "divergent" if (snap["funding"]["rate"] or 0) * bybit_rate < 0 else "consistent"

# 6. Taker (spot 100 trades)
trades = safe_fetch("https://api.binance.com/api/v3/trades?symbol=BTCUSDT&limit=100")
if isinstance(trades, list) and trades:
    buy_vol = sum(float(t["qty"]) for t in trades if not t.get("isBuyerMaker", True))
    sell_vol = sum(float(t["qty"]) for t in trades if t.get("isBuyerMaker", True))
    total = buy_vol + sell_vol
    snap["taker"] = {
        "source": "spot_100_trades", "quality": "C",
        "buy_vol_btc": round(buy_vol, 6), "sell_vol_btc": round(sell_vol, 6),
        "direction": "buy" if buy_vol > sell_vol * 1.1 else "sell" if sell_vol > buy_vol * 1.1 else "neutral",
    }

# 7. Macro (Yahoo)
for sym, key in [("DX-Y.NYB", "dxy"), ("%5EVIX", "vix"), ("%5EGSPC", "spx"), ("%5ETNX", "us10y")]:
    d = safe_fetch(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=2d")
    if isinstance(d, dict):
        snap[key] = {"value": d.get("chart", {}).get("result", [{}])[0].get("meta", {}).get("regularMarketPrice")}

# 8. Overall grade
price_g = snap["grades"].get("price", "C")
derivatives_ok = snap["funding"]["rate"] is not None and snap["oi"]["btc"] is not None
macro_ok = snap.get("dxy", {}).get("value") is not None
snap["grades"]["overall"] = "A" if price_g == "A" and derivatives_ok and macro_ok else "B" if price_g in ("A", "B") and derivatives_ok else "C"

snap["available"] = {
    "price": price_g in ("A", "B"), "derivatives": derivatives_ok,
    "taker": isinstance(snap.get("taker", {}).get("buy_vol_btc"), (int, float)),
    "macro": macro_ok, "liquidation": False, "long_short_ratio": False, "cvd_a_grade": False,
}

print(json.dumps(snap, indent=2, ensure_ascii=False, default=str))
