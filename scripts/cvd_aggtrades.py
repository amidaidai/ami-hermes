#!/usr/bin/env python3
"""
棠溪 · CVD aggTrades 升级 v1.0 (C级 → A级)

旧实现 (行情守望.get_cvd) 用 1m K 线的 taker_buy_volume 估算 CVD，只能给 C 级：
K 线聚合粒度粗，taker 买量是整根 K 线的汇总，无法反映真实逐笔主动成交方向。

本模块用 Binance /api/v3/aggTrades 真实逐笔成交：
  字段 m = isBuyerMaker
    m=True  → 买方挂单 → 这笔是主动卖出 (taker sell)
    m=False → 卖方挂单 → 这笔是主动买入 (taker buy)
真实 tick 级买卖方向 → A 级 CVD。

外加多周期一致性 (5m/15m/1h)：社区共识「多周期 CVD 同向才算高质量确认」。

用法:
    from cvd_aggtrades import get_cvd_aggtrades, multi_period_cvd
    r = get_cvd_aggtrades("BTCUSDT")          # 单次 A 级 CVD
    m = multi_period_cvd("BTCUSDT")           # 5m/15m/1h 一致性
"""

from __future__ import annotations
import requests


NEUTRAL_BAND = 0.1   # |CVD| < total*0.1 判中性
API = "https://api.binance.com/api/v3/aggTrades"


def cvd_from_aggtrades(trades: list[dict]) -> dict:
    """从 aggTrades 列表计算真实 CVD。

    Args:
        trades: [{"p":价, "q":量, "m":isBuyerMaker, "T":时间}, ...]

    Returns:
        {cvd, buy_vol, sell_vol, total, direction, quality}
    """
    if not trades:
        return {"cvd": 0.0, "buy_vol": 0.0, "sell_vol": 0.0, "total": 0.0,
                "direction": "?", "quality": "无"}

    buy_vol = 0.0
    sell_vol = 0.0
    for t in trades:
        try:
            qty = float(t.get("q", 0))
        except (TypeError, ValueError):
            continue
        # m=True → 主动卖出；m=False → 主动买入
        if t.get("m"):
            sell_vol += qty
        else:
            buy_vol += qty

    total = buy_vol + sell_vol
    cvd = buy_vol - sell_vol
    if total <= 0:
        direction = "中性"
    elif cvd > total * NEUTRAL_BAND:
        direction = "买"
    elif cvd < -total * NEUTRAL_BAND:
        direction = "卖"
    else:
        direction = "中性"

    return {
        "cvd": round(cvd, 4),
        "buy_vol": round(buy_vol, 4),
        "sell_vol": round(sell_vol, 4),
        "total": round(total, 4),
        "direction": direction,
        "quality": "A级",  # 真实逐笔 → A 级
    }


def fetch_aggtrades(symbol: str, limit: int = 1000, timeout: int = 6) -> list[dict]:
    """拉取最近 limit 笔 aggTrades。失败返回空列表。"""
    try:
        r = requests.get(API, params={"symbol": symbol, "limit": limit}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except (requests.Timeout, requests.ConnectionError, requests.HTTPError,
            ValueError, KeyError, TypeError):
        return []


def get_cvd_aggtrades(symbol: str, limit: int = 1000) -> dict:
    """单次 A 级 CVD（真实逐笔）。非加密返回不适用。失败回退 C 级。"""
    if not str(symbol).upper().endswith("USDT"):
        return {"direction": "不适用", "quality": "非加密", "cvd": 0.0}
    trades = fetch_aggtrades(symbol, limit=limit)
    if not trades:
        return {"direction": "?", "quality": "C级", "cvd": 0.0}
    return cvd_from_aggtrades(trades)


def multi_period_consistency(period_dirs: dict) -> dict:
    """多周期 CVD 方向一致性判定。

    Args:
        period_dirs: {"5m":"买", "15m":"买", "1h":"卖", ...}

    Returns:
        {consistent, aligned_direction, agree_count, total, note}
    """
    dirs = [d for d in period_dirs.values() if d in ("买", "卖", "中性")]
    total = len(dirs)
    if total == 0:
        return {"consistent": False, "aligned_direction": "?", "agree_count": 0,
                "total": 0, "note": "无有效周期数据"}

    # 统计非中性方向
    buy = sum(1 for d in dirs if d == "买")
    sell = sum(1 for d in dirs if d == "卖")
    neutral = sum(1 for d in dirs if d == "中性")

    # 全部同向（且非中性）才算一致
    if buy == total:
        return {"consistent": True, "aligned_direction": "买", "agree_count": buy,
                "total": total, "note": f"{total}周期全买·强确认"}
    if sell == total:
        return {"consistent": True, "aligned_direction": "卖", "agree_count": sell,
                "total": total, "note": f"{total}周期全卖·强确认"}

    # 主导方向 + 分歧标记
    if buy > sell:
        dom, cnt = "买", buy
    elif sell > buy:
        dom, cnt = "卖", sell
    else:
        dom, cnt = "中性", neutral
    return {
        "consistent": False,
        "aligned_direction": dom,
        "agree_count": cnt,
        "total": total,
        "note": f"周期分歧（买{buy}/卖{sell}/中{neutral}）⚠ 冲突时CVD仅作弱确认",
    }


def multi_period_cvd(symbol: str, periods: tuple = ("5m", "15m", "1h"),
                     limit: int = 1000) -> dict:
    """拉多周期 aggTrades CVD 并判一致性。

    aggTrades 无周期概念（按笔数取近端），故用不同 limit 近似不同时窗：
    5m≈近端少量笔 / 1h≈更多笔。这里用 limit 缩放近似。
    """
    if not str(symbol).upper().endswith("USDT"):
        return {"direction": "不适用", "quality": "非加密"}
    scale = {"5m": limit // 4, "15m": limit // 2, "1h": limit}
    period_dirs = {}
    period_detail = {}
    for p in periods:
        n = max(100, scale.get(p, limit))
        trades = fetch_aggtrades(symbol, limit=min(1000, n))
        r = cvd_from_aggtrades(trades) if trades else {"direction": "?", "cvd": 0.0, "quality": "C级"}
        period_dirs[p] = r["direction"]
        period_detail[p] = {"direction": r["direction"], "cvd": r.get("cvd", 0.0)}
    consistency = multi_period_consistency(period_dirs)
    return {
        "periods": period_detail,
        "consistency": consistency,
        "direction": consistency["aligned_direction"],
        "quality": "A级" if consistency["consistent"] else "B级",
    }


if __name__ == "__main__":
    import sys, json
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    print(json.dumps(multi_period_cvd(sym), ensure_ascii=False, indent=2))
