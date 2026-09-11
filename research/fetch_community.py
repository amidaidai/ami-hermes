from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from fetch_sources import fetch, slug

URLS = [
    # TradingView community / PineCoders
    "https://www.tradingview.com/script/CRKW4dvv-Cumulative-Volume-Delta-Candles-Aggregated-Lite/",
    "https://www.tradingview.com/script/qiqehv0U-Open-Interest-Aggregated-Lite/",
    "https://www.tradingview.com/script/mFzdS8hv-Footprint-Lookback-Order-Flow/",
    "https://www.tradingview.com/script/eZnsyK2g-Orderflow-Suite-martineye15/",
    "https://www.tradingview.com/script/5xom3FAB-Quantum-Liquidity-Map-VP-VWAP-CVD-Confluence-NikaQuant/",
    "https://www.tradingview.com/script/qBUHu6aW-Mirage-Liquidity-Sweep-Pro-WillyAlgoTrader/",
    "https://www.tradingview.com/script/KyAPOOvy-Delta-Flow/",
    "https://www.tradingview.com/script/7EI5Bhe0-Open-Interest-Bubbles-BackQuant/",
    "https://www.tradingview.com/script/W1YpYcOI-Higher-timeframe-requests/",
    "https://www.tradingview.com/script/RyafCWPs-Trade-Execution-Desk-JOAT/",
    # Reddit discussion evidence (hypothesis only)
    "https://www.reddit.com/r/TradingView/comments/1m3wwns/do_not_rely_on_tradingviews_volume_profiles/",
    "https://www.reddit.com/r/FuturesTrading/comments/1miv4t7/does_volume_delta_work_for_you/",
    "https://www.reddit.com/r/OrderFlow_Trading/comments/1pdzgmq/stop_overloading_your_charts_this_is_what_you/",
    # Professional platform education
    "https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy",
    "https://bookmap.com/blog/breakout-or-fakeout-the-3-point-checklist-for-confirmation",
    "https://atas.net/blog/how-to-read-footprint/",
    # Exchange API semantics
    "https://bybit-exchange.github.io/docs/v5/market/open-interest",
    "https://bybit-exchange.github.io/docs/v5/websocket/public/trade",
    "https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation",
    "https://bybit-exchange.github.io/docs/v5/market/long-short-ratio",
    "https://www.okx.com/docs-v5/en/#public-data-rest-api-get-open-interest",
]


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "raw_community"
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }
    )
    index: list[dict] = []
    for i, url in enumerate(URLS, 1):
        try:
            result = fetch(url, session)
            stem = slug(url)
            (out_dir / f"{stem}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / f"{stem}.txt").write_text(result["text"], encoding="utf-8")
            index.append({k: result[k] for k in result if k != "text"})
            print(f"OK {i}/{len(URLS)} {result['status']} {url} chars={len(result['text'])}")
        except Exception as exc:
            index.append({"requested_url": url, "error": repr(exc), "retrieved_utc": datetime.now(timezone.utc).isoformat()})
            print(f"ERR {i}/{len(URLS)} {url}: {exc}", file=sys.stderr)
        time.sleep(0.6)
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all("error" not in x for x in index) else 1


if __name__ == "__main__":
    raise SystemExit(main())
