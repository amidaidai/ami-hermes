#!/usr/bin/env python3
"""BTC/XAU 衍生品方向票批量采集（Binance）—— OI/费率/多空/Taker/Depth/24h。

用法: python scripts/binance_deriv_bundle.py [SYMBOL] [--json OUT]
直连超时自动走代理 127.0.0.1:7897。
"""
import sys, json, argparse, urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:/Hermes agent")
PROXY = "http://127.0.0.1:7897"
FAPI = "https://fapi.binance.com"
SPOT = "https://api.binance.com"


def _get(url, timeout=12):
    last = None
    for opener in (
        urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})),
        urllib.request.build_opener(),
    ):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
    raise last


def bundle(symbol="BTCUSDT"):
    out: dict = {"symbol": symbol, "bjt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    src = {}
    # 24h ticker
    try:
        t = _get(f"{FAPI}/fapi/v1/ticker/24hr?symbol={symbol}")
        out["price"] = float(t["lastPrice"])
        out["chg24h_pct"] = float(t["priceChangePercent"])
        out["high24h"], out["low24h"] = float(t["highPrice"]), float(t["lowPrice"])
        out["quote_vol24h"] = float(t["quoteVolume"])
        src["ticker"] = "live"
    except Exception as e:
        src["ticker"] = f"fail:{e}"
    # OI now + history
    try:
        oi = _get(f"{FAPI}/fapi/v1/openInterest?symbol={symbol}")
        out["oi_now"] = float(oi["openInterest"])
        h = _get(f"{FAPI}/futures/data/openInterestHist?symbol={symbol}&period=15m&limit=17")
        out["oi_hist_15m"] = [{"t": x["timestamp"], "oi": float(x["sumOpenInterest"]),
                               "notional": float(x["sumOpenInterestValue"])} for x in h]
        if len(h) >= 2:
            o0, o1 = float(h[-2]["sumOpenInterest"]), float(h[-1]["sumOpenInterest"])
            out["oi_chg_15m_pct"] = (o1 - o0) / o0 * 100
            oA = float(h[0]["sumOpenInterest"])
            out["oi_chg_4h_pct"] = (o1 - oA) / oA * 100
        src["oi"] = "live"
    except Exception as e:
        src["oi"] = f"fail:{e}"
    # funding
    try:
        fr = _get(f"{FAPI}/fapi/v1/premiumIndex?symbol={symbol}")
        out["funding_now_pct"] = float(fr["lastFundingRate"]) * 100
        out["mark"] = float(fr["markPrice"])
        fh = _get(f"{FAPI}/fapi/v1/fundingRate?symbol={symbol}&limit=8")
        out["funding_hist_pct"] = [round(float(x["fundingRate"]) * 100, 5) for x in fh]
        src["funding"] = "live"
    except Exception as e:
        src["funding"] = f"fail:{e}"
    # long/short ratios
    try:
        g = _get(f"{FAPI}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=15m&limit=8")
        out["global_ls"] = [round(float(x["longShortRatio"]), 3) for x in g]
        out["global_ls_now"] = out["global_ls"][-1] if out["global_ls"] else None
        src["global_ls"] = "live"
    except Exception as e:
        src["global_ls"] = f"fail:{e}"
    try:
        to = _get(f"{FAPI}/futures/data/topLongShortPositionRatio?symbol={symbol}&period=15m&limit=8")
        out["top_pos_ls"] = [round(float(x["longShortRatio"]), 3) for x in to]
        out["top_pos_ls_now"] = out["top_pos_ls"][-1] if out["top_pos_ls"] else None
        src["top_ls"] = "live"
    except Exception as e:
        src["top_ls"] = f"fail:{e}"
    try:
        ta = _get(f"{FAPI}/futures/data/takerlongshortRatio?symbol={symbol}&period=15m&limit=8")
        out["taker"] = [round(float(x["buySellRatio"]), 3) for x in ta]
        out["taker_now"] = out["taker"][-1] if out["taker"] else None
        src["taker"] = "live"
    except Exception as e:
        src["taker"] = f"fail:{e}"
    # depth (spot)
    try:
        d = _get(f"{SPOT}/api/v3/depth?symbol={symbol}&limit=20")
        bids = [(float(p), float(q)) for p, q in d["bids"]]
        asks = [(float(p), float(q)) for p, q in d["asks"]]
        out["bid_wall5"] = sum(p * q for p, q in bids[:5])
        out["ask_wall5"] = sum(p * q for p, q in asks[:5])
        out["depth_ratio"] = out["bid_wall5"] / out["ask_wall5"] if out["ask_wall5"] else None
        out["best_bid"], out["best_ask"] = bids[0][0], asks[0][0]
        src["depth"] = "live"
    except Exception as e:
        src["depth"] = f"fail:{e}"
    out["_src"] = src
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", default="BTCUSDT")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    b = bundle(a.symbol)
    op = Path(a.json) if a.json else ROOT / "outputs" / f"binance_{a.symbol}_{datetime.now():%Y%m%d_%H%M}.json"
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(b, ensure_ascii=False, indent=1))
    print(f"[saved] {op}")
