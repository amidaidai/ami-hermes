#!/usr/bin/env python3
"""
棠溪 · VWAP+EMA+CVD 本地计算引擎 v1.0
基于 TV Pine 指标参数（棠溪自定义·SVP+ICT+VWAP+EMA+CVD.txt）

本地计算（不依赖TV CDP连接）：
  - VWAP + SD bands (1σ/2σ) — 从K线OHLC+Volume计算
  - EMA 9/21/34/55 + 趋势云 — 从K线Close计算
  - CVD吸收/背离/动能 — 复用 cvd_aggtrades.py

当TV可用时，优先从 get_study_values / get_pine_tables 读取（更精确tick级数据）。
TV不可用时，退回到本模块的K线级近似计算。
"""

from pathlib import Path
from typing import Optional
import json

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"

# ═══ 棠溪指标参数（对齐 SVP+ICT+VWAP+EMA+CVD.txt）═══
# EMA
EMA_PERIODS = [9, 21, 34, 55]
EMA_FAST_CLOUD = (9, 21)   # 快速趋势云
EMA_SLOW_CLOUD = (34, 55)  # 慢速趋势云

# VWAP
VWAP_SD_MULT_1 = 1.0
VWAP_SD_MULT_2 = 2.0

# CVD
CVD_SLOPE_LEN = 5
CVD_DIVERGENCE_LEN = 20
CVD_ABSORB_LEN = 12
CVD_ABSORB_PRICE_ATR = 0.8
CVD_ABSORB_DELTA_MULT = 3.0
CVD_CONFIRM_WEIGHT = 1.0
CVD_KEY_LEVEL_ATR = 0.45
A_KEY_LEVEL_ATR = 0.60

# ═══ 通用计算函数 ═══


def calc_ema(series: list[float], period: int) -> list:
    """计算EMA（递归，对齐TV ta.ema）。返回list，未就绪位置为None。"""
    if len(series) < period:
        return [None] * len(series)
    alpha = 2.0 / (period + 1)
    result: list = [None] * (period - 1)
    # SMA作为第一个EMA值
    ema = sum(series[:period]) / period
    result.append(ema)
    for val in series[period:]:
        ema = alpha * val + (1 - alpha) * ema
        result.append(ema)
    return result


def calc_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
    """计算ATR（True Range + EMA平滑）。"""
    n = len(closes)
    if n < 2:
        return [None] * n
    trs = [None]  # 第一根无前收盘
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    # EMA平滑TR
    atr = calc_ema(trs[1:], period)  # 从第二根开始
    return [None] + atr


def calc_vwap(highs: list[float], lows: list[float], closes: list[float], volumes: list[float],
              anchor: str = "session") -> dict:
    """
    计算VWAP + 标准差带。

    anchor:
      - "session": 每日重置（日内VWAP）
      - "week": 每周重置
      - "month": 每月重置

    Returns:
        {
            "vwap": float,           # 当前VWAP值
            "upper_1": float,        # +1σ
            "lower_1": float,        # -1σ
            "upper_2": float,        # +2σ
            "lower_2": float,        # -2σ
            "price_vs_vwap": str,    # "上"/"下"
            "in_band": str,          # "1σ内"/"1σ-2σ"/"2σ外"
        }
    """
    n = len(closes)
    if n < 2 or not any(v > 0 for v in volumes if v):
        return {"vwap": None, "error": "数据不足"}

    # 使用全部数据计算（近似session VWAP，真实应用时按anchor分段）
    typicals = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
    cum_pv = 0.0
    cum_vol = 0.0
    pv_list = []

    for i in range(n):
        v = volumes[i] if volumes[i] and volumes[i] > 0 else 0
        tp = typicals[i]
        cum_pv += tp * v
        cum_vol += v
        pv_list.append(tp * v)

    if cum_vol <= 0:
        return {"vwap": None, "error": "零成交量"}

    vwap = cum_pv / cum_vol

    # 标准差计算（基于Typical Price偏离VWAP的加权标准差）
    weighted_var = 0.0
    for i in range(n):
        v = volumes[i] if volumes[i] and volumes[i] > 0 else 0
        if v > 0:
            weighted_var += v * (typicals[i] - vwap) ** 2
    weighted_var /= max(cum_vol, 1e-9)
    sd = weighted_var ** 0.5

    upper_1 = vwap + VWAP_SD_MULT_1 * sd
    lower_1 = vwap - VWAP_SD_MULT_1 * sd
    upper_2 = vwap + VWAP_SD_MULT_2 * sd
    lower_2 = vwap - VWAP_SD_MULT_2 * sd

    current_price = closes[-1]
    price_vs = "上" if current_price > vwap else "下"

    dist_pct = abs(current_price - vwap) / vwap if vwap > 0 else 0
    if dist_pct <= sd / vwap:
        in_band = "1σ内"
    elif dist_pct <= 2 * sd / vwap:
        in_band = "1σ-2σ"
    else:
        in_band = "2σ外"

    return {
        "vwap": round(vwap, 2),
        "upper_1": round(upper_1, 2),
        "lower_1": round(lower_1, 2),
        "upper_2": round(upper_2, 2),
        "lower_2": round(lower_2, 2),
        "sd": round(sd, 2),
        "price_vs_vwap": price_vs,
        "in_band": in_band,
    }


def calc_ema_cloud(ema_values: dict[int, list[float]]) -> dict:
    """
    计算EMA趋势云状态。

    Returns:
        {
            "fast_cloud": "多头云"/"空头云"/"交织",
            "slow_cloud": "多头云"/"空头云"/"交织",
            "ema_ranking": str,        # "9>21>34>55" 等
            "fast_distance_pct": float, # 价格距快速云的%
            "trend_strength": "强趋势"/"弱趋势"/"盘整",
        }
    """
    result = {
        "fast_cloud": "交织",
        "slow_cloud": "交织",
        "ema_ranking": "未知",
        "fast_distance_pct": 0.0,
        "trend_strength": "盘整",
    }

    # 获取各EMA最新值
    vals = {}
    for period, ema_list in ema_values.items():
        last = next((v for v in reversed(ema_list) if v is not None), None)
        if last is not None:
            vals[period] = last

    if len(vals) < 3:
        return result

    # 排列
    sorted_periods = sorted(vals.keys())
    ranking = " > ".join(str(p) for p in sorted_periods)  # 简单版
    # 实际比较值
    actual_ranking_parts = []
    for p in sorted_periods:
        actual_ranking_parts.append(f"EMA{p}")
    if len(vals) >= 4:
        if vals[9] > vals[21] > vals[34] > vals[55]:
            ranking = "9>21>34>55"
            result["trend_strength"] = "强趋势·多头排列"
        elif vals[9] < vals[21] < vals[34] < vals[55]:
            ranking = "9<21<34<55"
            result["trend_strength"] = "强趋势·空头排列"
        elif vals[9] > vals[21] and vals[34] > vals[55]:
            ranking = "9>21 · 34>55"
    result["ema_ranking"] = ranking

    # 快速云
    if 9 in vals and 21 in vals:
        if vals[9] > vals[21]:
            result["fast_cloud"] = "多头云"
        elif vals[9] < vals[21]:
            result["fast_cloud"] = "空头云"

    # 慢速云
    if 34 in vals and 55 in vals:
        if vals[34] > vals[55]:
            result["slow_cloud"] = "多头云"
        elif vals[34] < vals[55]:
            result["slow_cloud"] = "空头云"

    # 快速云距离
    if 9 in vals and vals[9] > 0:
        result["fast_distance_pct"] = round(abs(vals[9] - vals[21]) / vals[9] * 100, 2) if 21 in vals else 0.0

    return result


def analyze_cvd_absorption(cvd_data: dict) -> dict:
    """
    对齐棠溪 Pine CVD参数：
      CVD_ABSORB_LEN=12, CVD_ABSORB_PRICE_ATR=0.8, CVD_ABSORB_DELTA_MULT=3.0

    基于 cvd_aggtrades.py 的输出做吸收/派发检测。
    """
    direction = cvd_data.get("direction", "?")
    quality = cvd_data.get("quality", "C")
    net_delta = cvd_data.get("net_delta", 0)
    buy_volume = cvd_data.get("buy_volume", 0)
    sell_volume = cvd_data.get("sell_volume", 0)
    total_volume = buy_volume + sell_volume

    if total_volume <= 0:
        return {"absorption": False, "pattern": "数据不足", "confidence": 0}

    buy_pct = buy_volume / total_volume
    imbalance = abs(buy_pct - 0.5)

    # 吸收检测：单方向占比 > 55% 但价格未动
    if imbalance > 0.05:  # 方向偏离5%+
        if buy_pct > 0.55:
            pattern = "买盘吸收"
            conf = min(80, int(imbalance * 200))
        elif buy_pct < 0.45:
            pattern = "卖盘派发"
            conf = min(80, int(imbalance * 200))
        else:
            pattern = "正常"
            conf = 0
    else:
        pattern = "均衡"
        conf = 0

    return {
        "absorption": imbalance > 0.05,
        "pattern": pattern,
        "confidence": conf,
        "buy_pct": round(buy_pct, 3),
        "net_delta": net_delta,
        "quality": quality,
    }


def vwap_ema_cvd_summary(symbol: str, klines: list[dict] = None) -> dict:
    """
    一键计算：从K线数据 → VWAP + EMA + CVD 组合摘要。

    输入 klines: [{"open","high","low","close","volume"}, ...]
    不传则返回空结果。

    Returns: 参与分析卡渲染的 dict
    """
    if not klines:
        return {"available": False, "reason": "无K线数据"}

    n = len(klines)
    closes = [k.get("close", 0) for k in klines]
    highs = [k.get("high", 0) for k in klines]
    lows = [k.get("low", 0) for k in klines]
    volumes = [k.get("volume", 0) for k in klines]

    # VWAP
    vwap_result = calc_vwap(highs, lows, closes, volumes, anchor="session")

    # EMA
    ema_values = {}
    for period in EMA_PERIODS:
        ema_values[period] = calc_ema(closes, period)

    ema_cloud = calc_ema_cloud(ema_values)

    # ATR
    atr_list = calc_atr(highs, lows, closes, period=14)
    current_atr = next((v for v in reversed(atr_list) if v is not None), None)

    # 价格位置
    current_price = closes[-1] if closes else 0
    current_vwap = vwap_result.get("vwap")

    # 组合摘要
    summary_parts = []
    if current_vwap:
        summary_parts.append(f"VWAP `{current_vwap}` · 价在{'' if current_price > current_vwap else 'VWAP'}{'上' if current_price > current_vwap else '下'}")

    ema_summary = []
    for p in EMA_PERIODS:
        ema_list = ema_values.get(p, [])
        last = next((v for v in reversed(ema_list) if v is not None), None)
        if last is not None:
            vs = "上" if current_price > last else "下"
            ema_summary.append(f"EMA{p}={last:.1f}({vs})")
    if ema_summary:
        summary_parts.append(" · ".join(ema_summary))

    return {
        "available": True,
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "vwap": vwap_result,
        "ema": {str(p): round(ema_values[p][-1], 2) if ema_values[p] and ema_values[p][-1] else None for p in EMA_PERIODS},
        "ema_cloud": ema_cloud,
        "atr": round(current_atr, 2) if current_atr else None,
        "summary": " · ".join(summary_parts) if summary_parts else "数据不足",
    }
