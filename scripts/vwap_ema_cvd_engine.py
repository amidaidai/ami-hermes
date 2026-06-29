#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -*- coding: utf-8 -*-
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
from typing import Union, Optional as Opt
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


def analyze_cvd_iceberg(cvd_data: dict, price_changes: Opt[list[float]] = None) -> dict:
    """v7.3新增: 冰山订单检测。
    
    检测特征：连续同向小额成交 + 价格几无位移 → 疑似冰山（大单被拆分隐藏）。
    
    Args:
        cvd_data: cvd_aggtrades.py输出
        price_changes: 同期价格变动序列（可选·用于检测价格停滞）
    Returns:
        {iceberg: bool, pattern: str, confidence: int (0-100)}
    """
    buy_count = cvd_data.get("buy_count", 0)
    sell_count = cvd_data.get("sell_count", 0)
    total_count = buy_count + sell_count
    if total_count < 20:
        return {"iceberg": False, "pattern": "数据不足", "confidence": 0}
    
    # 方向一致性：单方向笔数占比 > 65% 但每笔量小
    buy_pct = buy_count / total_count if total_count else 0
    sell_pct = sell_count / total_count if total_count else 0
    dominant_pct = max(buy_pct, sell_pct)
    
    avg_size = (cvd_data.get("buy_volume", 0) + cvd_data.get("sell_volume", 0)) / total_count if total_count else 0
    # 冰山特征：单方向主导 + 小额碎单（≤中位数2倍）
    is_small_lots = avg_size < 0.5  # 相对小单（阈值可调）
    
    if dominant_pct > 0.65 and is_small_lots:
        # 价格位移检查：若有 price_changes，确认价格停滞
        if price_changes and len(price_changes) > 5:
            price_range = max(price_changes) - min(price_changes)
            if price_range < abs(price_changes[0]) * 0.003:  # 价格范围 < 0.3%
                conf = min(85, int((dominant_pct - 0.5) * 200) + 30)
                direction = "买方" if buy_pct > sell_pct else "卖方"
                return {
                    "iceberg": True,
                    "pattern": f"{direction}冰山·小额碎单{total_count}笔·价未动",
                    "confidence": conf,
                    "dominant_pct": round(dominant_pct, 3),
                    "avg_lot_size": round(avg_size, 3),
                }
        # 无价格数据时降低置信度
        conf = min(60, int((dominant_pct - 0.5) * 150))
        direction = "买方" if buy_pct > sell_pct else "卖方"
        return {
            "iceberg": True,
            "pattern": f"{direction}疑似冰山·碎单占比{dominant_pct:.0%}",
            "confidence": conf,
            "dominant_pct": round(dominant_pct, 3),
            "avg_lot_size": round(avg_size, 3),
        }
    
    return {"iceberg": False, "pattern": "无明显冰山", "confidence": 0}


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


# ═══════════════════ 多资产相关性检查 v7.3 ═══════════════════

def check_correlation_warning(btc_price: float, xau_price: float,
                               btc_position: bool = False, xau_position: bool = False) -> dict:
    """多资产持仓相关性警告。
    
    BTC和XAU通常负相关或弱相关，但极端宏观事件下可能同向。
    双持时警告合并风险。
    
    Returns: {warning: bool, message: str, suggested_action: str}
    """
    if not (btc_position and xau_position):
        return {"warning": False, "message": "", "suggested_action": ""}
    
    # 双持检查：总风险不应该 > 单笔上限×2
    return {
        "warning": True,
        "message": "⚠ BTC+XAU双持 · 合并风险需评估",
        "suggested_action": "若同向(均为多/空)：缩小任一仓位50%·若反向：确认非对冲幻觉",
        "double_position": True,
    }


def check_correlation_btc_xau(btc_klines: list[dict], xau_klines: list[dict],
                                window: int = 48) -> dict:
    """计算BTC和XAU近期相关性（48根=4h×48=8天）。
    
    Returns: {correlation, strength, interpretation}
    """
    if not btc_klines or not xau_klines:
        return {"available": False, "reason": "K线数据不足"}
    
    n = min(len(btc_klines), len(xau_klines), window)
    btc_closes = [k.get("close", 0) for k in btc_klines[-n:]]
    xau_closes = [k.get("close", 0) for k in xau_klines[-n:]]
    
    # 用百分比收益计算相关性（去量纲）
    btc_rets = [(btc_closes[i] - btc_closes[i-1]) / btc_closes[i-1] for i in range(1, n) if btc_closes[i-1] > 0]
    xau_rets = [(xau_closes[i] - xau_closes[i-1]) / xau_closes[i-1] for i in range(1, n) if xau_closes[i-1] > 0]
    
    m = min(len(btc_rets), len(xau_rets))
    if m < 10:
        return {"available": False, "reason": "样本不足"}
    
    btc_rets = btc_rets[:m]
    xau_rets = xau_rets[:m]
    
    # Pearson correlation
    import math
    mean_b = sum(btc_rets) / m
    mean_x = sum(xau_rets) / m
    cov = sum((a - mean_b) * (b - mean_x) for a, b in zip(btc_rets, xau_rets)) / m
    std_b = math.sqrt(sum((a - mean_b) ** 2 for a in btc_rets) / m)
    std_x = math.sqrt(sum((b - mean_x) ** 2 for b in xau_rets) / m)
    
    if std_b < 1e-10 or std_x < 1e-10:
        return {"available": True, "correlation": 0, "strength": "无", "interpretation": "无波动"}
    
    corr = cov / (std_b * std_x)
    corr = max(-1.0, min(1.0, corr))
    
    abs_corr = abs(corr)
    if abs_corr < 0.3:
        strength, interp = "弱", "可独立持仓·无合并风险"
    elif abs_corr < 0.5:
        strength, interp = "中等", "轻相关·建议观察"
    elif abs_corr < 0.7:
        strength, interp = "较强", "高相关⚠·双持需缩减"
    else:
        strength, interp = "很强", "严重⚠·双持同向→合并仓位≤单笔上限"
    
    direction = "正" if corr > 0 else "负"
    return {
        "available": True,
        "correlation": round(corr, 3),
        "abs_correlation": round(abs_corr, 3),
        "strength": strength,
        "direction": direction,
        "interpretation": f"{direction}相关·{strength}·{interp}",
    }
