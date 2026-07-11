#!/usr/bin/env python3
from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -*- coding: utf-8 -*-
"""
depth_wall.py — 大额挂单墙分析器 (v1.0 · 2026-06-19)

用途：从 Binance 期货深度盘口聚合大额限价墙，识别可作"磁吸位/止损陷阱"的
价格簇。清算热力图(Coinglass)需付费key暂缺，本模块用真实可用的免费 depth
端点替代该维度——挂单墙本身就是主力挂单意图的直接证据。

数据源（2026-06-19 实测可用·免费无认证）：
  https://fapi.binance.com/fapi/v1/depth?symbol={SYM}&limit=500

设计：
  - 拉 500 档买卖盘
  - 按价格区间聚类（默认 0.1% 桶宽），找出名义价值最大的若干墙
  - 区分支撑墙（bid，下方磁吸/防守）和压力墙（ask，上方磁吸/天花板）
  - 输出人读字符串，可直接嵌入分析卡博弈段，不泄漏机器字段

注意：
  - 盘口墙是瞬时快照，会撤单/搬墙。只作博弈背景，不作硬触发。
  - XAU 无 Binance 盘口，本模块仅适用加密。XAU 走宏观替代维度。
  - 仅依赖标准库 urllib，零三方依赖，可在 no_agent cron 中调用。
"""
import json
import sys
import urllib.request
from collections import defaultdict

DEPTH_URLS = (
    "https://fapi.binance.com/fapi/v1/depth?symbol={sym}&limit=500",
    "https://api.binance.com/api/v3/depth?symbol={sym}&limit=500",
    "https://data-api.binance.vision/api/v3/depth?symbol={sym}&limit=500",
)
_TIMEOUT = 10


def _fetch_depth(symbol: str) -> dict | None:
    from binance_public import fapi_available, fetch_spot, fetch_url
    if fapi_available(timeout=2):
        payload = fetch_url(DEPTH_URLS[0].format(sym=symbol.upper()), timeout=_TIMEOUT)
        if isinstance(payload, dict) and payload.get("bids") and payload.get("asks"):
            payload.setdefault("_source", "Binance Futures")
            return payload
    payload = fetch_spot(
        "/api/v3/depth", {"symbol": symbol.upper(), "limit": 500}, timeout=_TIMEOUT,
    )
    if isinstance(payload, dict) and payload.get("bids") and payload.get("asks"):
        payload.setdefault("_source", "Binance Spot")
        return payload
    sys.stderr.write("depth_wall fetch failed: all Binance market-data hosts unavailable\n")
    return None


def _cluster(levels: list[list[str]], bucket_pct: float) -> list[dict]:
    """把档位按价格桶聚类，返回 [{price, qty, notional}] 按名义降序。"""
    if not levels:
        return []
    ref = float(levels[0][0])
    bucket = ref * bucket_pct
    if bucket <= 0:
        return []
    agg_qty: dict[float, float] = defaultdict(float)
    agg_px: dict[float, float] = {}
    for px_s, qty_s in levels:
        px = float(px_s)
        qty = float(qty_s)
        key = round(px / bucket)
        agg_qty[key] += qty
        # 用名义加权价格代表该桶
        agg_px.setdefault(key, px)
        agg_px[key] = (agg_px[key] + px) / 2
    out = []
    for key, qty in agg_qty.items():
        px = agg_px[key]
        out.append({"price": px, "qty": qty, "notional": px * qty})
    out.sort(key=lambda d: d["notional"], reverse=True)
    return out


def analyze_walls(symbol: str, bucket_pct: float = 0.001,
                  top_n: int = 3, min_notional_usd: float = 200_000) -> dict:
    """
    返回结构：
    {
      "ok": bool, "symbol": str, "mid": float,
      "support_walls": [{"price","qty","notional","dist_pct"}],
      "resist_walls":  [...],
      "summary": "人读字符串"
    }
    """
    raw = _fetch_depth(symbol)
    if not raw or "bids" not in raw or "asks" not in raw:
        return {"ok": False, "symbol": symbol, "summary": "盘口不可用"}

    bids = raw["bids"]
    asks = raw["asks"]
    if not bids or not asks:
        return {"ok": False, "symbol": symbol, "summary": "盘口为空"}

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    mid = (best_bid + best_ask) / 2

    sup = [w for w in _cluster(bids, bucket_pct) if w["notional"] >= min_notional_usd][:top_n]
    res = [w for w in _cluster(asks, bucket_pct) if w["notional"] >= min_notional_usd][:top_n]

    for w in sup:
        w["dist_pct"] = (w["price"] - mid) / mid * 100
    for w in res:
        w["dist_pct"] = (w["price"] - mid) / mid * 100

    def _fmt(walls: list[dict], label: str) -> str:
        if not walls:
            return f"{label}：无显著墙"
        parts = []
        for w in walls:
            mm = w["notional"] / 1_000_000
            parts.append(f"`{w['price']:,.1f}`（{mm:.1f}M·{w['dist_pct']:+.2f}%）")
        return f"{label}：" + " · ".join(parts)

    summary = _fmt(sup, "下方支撑墙") + " — " + _fmt(res, "上方压力墙")

    return {
        "ok": True,
        "symbol": symbol,
        "mid": mid,
        "support_walls": sup,
        "resist_walls": res,
        "summary": summary,
    }


def _fetch_binance_oi_history(symbol: str, period: str) -> list[dict] | None:
    from binance_public import fapi_available, fetch_url
    if not fapi_available(timeout=2):
        return None
    url = (f"https://fapi.binance.com/futures/data/openInterestHist"
           f"?symbol={symbol}&period={period}&limit=2")
    payload = fetch_url(url, timeout=_TIMEOUT)
    return payload if isinstance(payload, list) and len(payload) >= 2 else None


def _fetch_orion_ticker(symbol: str) -> dict | None:
    from binance_public import fetch_orion_ticker
    return fetch_orion_ticker(symbol)


def _regime_from_deltas(oi_d: float, px_d: float) -> tuple[str, str]:
    oi_up, oi_dn = oi_d > 0.1, oi_d < -0.1
    px_up, px_dn = px_d > 0.05, px_d < -0.05
    if oi_up and px_up:
        return "新多进场", "净多堆积·上方墙=获利了结磁吸·回调风险累积"
    if oi_up and px_dn:
        return "新空进场", "净空堆积·下方墙=止盈磁吸·反弹轧空风险累积"
    if oi_dn and px_up:
        return "空头平仓", "轧空回补·上行有续航·非新多驱动"
    if oi_dn and px_dn:
        return "多头平仓", "多头投降·下行有续航·非新空驱动"
    return "持仓平稳", "OI/价格无显著增量·无杠杆体制信号"


def oi_price_regime(symbol: str, period: str = "15m") -> dict:
    """OI增量×价格增量；直连Binance失败时降级Orion的Binance期货快照。"""
    sym = symbol.upper()
    if not sym.endswith("USDT"):
        sym = f"{sym}USDT"
    source = "Binance Futures"
    try:
        oi_hist = _fetch_binance_oi_history(sym, period)
        if oi_hist:
            oi_prev = float(oi_hist[0]["sumOpenInterest"])
            oi_now = float(oi_hist[-1]["sumOpenInterest"])
            px_prev = float(oi_hist[0]["sumOpenInterestValue"]) / oi_prev if oi_prev else 0
            px_now = float(oi_hist[-1]["sumOpenInterestValue"]) / oi_now if oi_now else 0
            oi_d = (oi_now - oi_prev) / oi_prev * 100 if oi_prev else 0.0
            px_d = (px_now - px_prev) / px_prev * 100 if px_prev else 0.0
        else:
            row = _fetch_orion_ticker(sym)
            if not row:
                return {"ok": False, "summary": "OI体制不可用", "source": "none"}
            tf_key = {"5m": "tf5m", "15m": "tf15m", "1h": "tf1h", "4h": "tf4h"}.get(period, "tf1h")
            tf = row.get(tf_key) if isinstance(row.get(tf_key), dict) else row.get("tf1h")
            if not isinstance(tf, dict):
                return {"ok": False, "summary": "Orion OI周期数据不可用", "source": "Orion/Binance"}
            oi_d = float(tf.get("oiChange") or 0)
            px_d = float(tf.get("changePercent") or 0)
            source = "Orion/Binance"
        regime, note = _regime_from_deltas(oi_d, px_d)
        summary = f"杠杆体制：{regime}（OI {oi_d:+.2f}% · 价 {px_d:+.2f}%）— {note}"
        return {"ok": True, "regime": regime, "oi_delta_pct": round(oi_d, 2),
                "price_delta_pct": round(px_d, 2), "summary": summary, "source": source}
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"oi_price_regime failed: {e}\n")
        return {"ok": False, "summary": "OI体制不可用", "source": "none"}

def wall_summary(symbol: str) -> str:
    """便捷入口：直接返回可嵌入分析卡的人读字符串。"""
    r = analyze_walls(symbol)
    return r.get("summary", "盘口不可用")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    result = analyze_walls(sym)
    print(json.dumps(result, ensure_ascii=False, indent=2))
