#!/usr/bin/env python3
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
from __future__ import annotations
import json
import sys
import urllib.request
from collections import defaultdict

DEPTH_URL = "https://fapi.binance.com/fapi/v1/depth?symbol={sym}&limit=500"
_TIMEOUT = 10


def _fetch_depth(symbol: str) -> dict | None:
    url = DEPTH_URL.format(sym=symbol.upper())
    req = urllib.request.Request(url, headers={"User-Agent": "TangXi-DepthWall/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — 网络层兜底，调用方自行判 None
        sys.stderr.write(f"depth_wall fetch failed: {e}\n")
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


def wall_summary(symbol: str) -> str:
    """便捷入口：直接返回可嵌入分析卡的人读字符串。"""
    r = analyze_walls(symbol)
    return r.get("summary", "盘口不可用")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    result = analyze_walls(sym)
    print(json.dumps(result, ensure_ascii=False, indent=2))
