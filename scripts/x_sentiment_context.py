#!/usr/bin/env python3
"""X/社交情绪 LLM 分析上下文采集脚本。

只采集结构化上下文，不直接做结论；stdout 注入 agent cron，让 LLM 结合 x_search 做中文交易解读。
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
UA = "Hermes/1.0 (+https://github.com/amidaidai/ami-hermes)"
ROOT = Path("D:/Hermes agent")
DATA_DIR = ROOT / "data"
HERMES_DATA = Path(os.path.expanduser("~/AppData/Local/hermes/data"))
HISTORY = DATA_DIR / "x_sentiment_history.jsonl"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "HYPEUSDT"]


def fetch_json(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def safe_fetch(name: str, fn, default):
    try:
        return fn()
    except Exception as exc:
        return {"error": f"{name}: {type(exc).__name__}: {str(exc)[:120]}", **default}


def fetch_fear_greed() -> dict:
    data = fetch_json("https://api.alternative.me/fng/?limit=1", 8)
    item = data.get("data", [{}])[0]
    return {
        "value": int(item.get("value", 50)),
        "classification": item.get("value_classification", "Neutral"),
        "timestamp": item.get("timestamp"),
    }


def fetch_trending() -> dict:
    data = fetch_json("https://api.coingecko.com/api/v3/search/trending", 10)
    rows = []
    for c in data.get("coins", [])[:10]:
        item = c.get("item", {})
        rows.append({
            "symbol": str(item.get("symbol", "?")).upper(),
            "name": item.get("name", "?"),
            "rank": item.get("market_cap_rank"),
            "score": item.get("score"),
            "price_btc": item.get("price_btc"),
        })
    return {"coins": rows}


def fetch_global() -> dict:
    data = fetch_json("https://api.coingecko.com/api/v3/global", 10).get("data", {})
    return {
        "market_cap_change_24h_pct": data.get("market_cap_change_percentage_24h_usd"),
        "btc_dominance": data.get("market_cap_percentage", {}).get("btc"),
        "eth_dominance": data.get("market_cap_percentage", {}).get("eth"),
        "active_cryptocurrencies": data.get("active_cryptocurrencies"),
    }


def fetch_binance_24h(symbol: str) -> dict:
    q = urllib.parse.urlencode({"symbol": symbol})
    data = fetch_json(f"https://api.binance.com/api/v3/ticker/24hr?{q}", 8)
    return {
        "symbol": symbol,
        "price": float(data.get("lastPrice", 0)),
        "chg_24h_pct": float(data.get("priceChangePercent", 0)),
        "quote_volume": float(data.get("quoteVolume", 0)),
        "high": float(data.get("highPrice", 0)),
        "low": float(data.get("lowPrice", 0)),
    }


def fetch_market_snapshot() -> list[dict]:
    rows = []
    for s in SYMBOLS:
        rows.append(safe_fetch(s, lambda sym=s: fetch_binance_24h(sym), {"symbol": s}))
    return rows


def load_orion_top() -> list[dict]:
    p = DATA_DIR / "orion_radar.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        rows = data.get("candidates", [])[:8]
        return [{
            "symbol": r.get("symbol"),
            "confidence": r.get("confidence"),
            "chg_1h": r.get("chg_1h"),
            "oi_chg": r.get("oi_chg"),
            "funding": r.get("funding"),
        } for r in rows]
    except Exception:
        return []


def append_history(snapshot: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HERMES_DATA.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    # keep last 500 lines
    try:
        lines = HISTORY.read_text(encoding="utf-8").splitlines()[-500:]
        HISTORY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass
    (DATA_DIR / "x_sentiment_context.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    (HERMES_DATA / "x_sentiment_context.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    now = datetime.now(TZ)
    fg = safe_fetch("fear_greed", fetch_fear_greed, {"value": 50, "classification": "Error"})
    trending = safe_fetch("coingecko_trending", fetch_trending, {"coins": []})
    glob = safe_fetch("coingecko_global", fetch_global, {})
    market = fetch_market_snapshot()
    orion = load_orion_top()

    snapshot = {
        "ts": now.isoformat(),
        "time_cn": now.strftime("%Y年%m月%d日%H：%M"),
        "fear_greed": fg,
        "coingecko_trending": trending.get("coins", []),
        "global_market": glob,
        "market_snapshot": market,
        "orion_candidates": orion,
        "suggested_x_queries": [
            "crypto market sentiment BTC ETH SOL",
            "Bitcoin ETF crypto bearish bullish",
            "Solana HYPE crypto narrative",
        ] + [f"{c.get('symbol','').replace('USDT','')} crypto sentiment" for c in orion[:3] if c.get("symbol")],
    }
    append_history(snapshot)

    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
