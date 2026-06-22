#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
棠溪 · 三层确认模型 v1.0
FVG(公允价值缺口) + OB(订单块) + Sweep(流动性扫荡) = A+ 入场

社区对标：ICT Smart Money Concepts 三层确认管线
"""

from typing import Tuple, Optional


# ═══════════════════════════════════════
# Silver Bullet 检测 (ICT最高胜率模型 70%+)
# 时间窗: 14:00-15:00 UTC (纽约开盘后)
# 条件: 价格回到最近FVG + CVD背离 + 位移确认
# ═══════════════════════════════════════

def detect_silver_bullet(
    price: float,
    ohlcv: list[dict],
    tv_data: dict,
    session: dict,
) -> Tuple[str, float, str]:
    """
    Silver Bullet 检测。
    
    Returns: (direction, confidence, reasoning)
    """
    if not ohlcv or len(ohlcv) < 20:
        return "null", 0.0, "数据不足"
    
    # 条件1: 必须在 Silver Bullet 时间窗
    from session_strategy import get_active_killzone
    kz = get_active_killzone()
    if not kz or kz["key"] != "silver_bullet":
        return "null", 0.0, "非SilverBullet窗"
    
    # 条件2: 位移检测 — 前3根有大实体（>2倍平均实体）
    bodies = []
    for bar in ohlcv[-10:]:
        o = float(bar.get("open", 0))
        c = float(bar.get("close", 0))
        if o and c:
            bodies.append(abs(c - o))
    if not bodies:
        return "null", 0.0, "无K线数据"
    
    avg_body = sum(bodies) / len(bodies)
    recent_3 = bodies[-3:]
    displacement = any(b > avg_body * 2.0 for b in recent_3)
    
    if not displacement:
        return "null", 0.0, "无位移"
    
    # 条件3: CVD背离确认
    cvd = float(tv_data.get("cvd", 0))
    cvd_slope = float(tv_data.get("cvd_slope", 0))
    
    # 方向判断
    price_change = (c - o) / o * 100 if (o := float(ohlcv[-1].get("open", 0))) else 0
    direction = "long" if price_change > 0.5 and cvd_slope > 0 else \
                "short" if price_change < -0.5 and cvd_slope < 0 else "null"
    
    if direction == "null":
        return "null", 0.0, "方向不明确"
    
    confidence = 0.65  # 基础白银子弹置信
    if displacement and abs(price_change) > 1.0:
        confidence += 0.10
    if abs(cvd) > 3000 and cvd_slope * (1 if direction == "long" else -1) > 0:
        confidence += 0.05
    
    dir_cn = "做多" if direction == "long" else "做空"
    return direction, min(confidence, 1.0), f"★银弹窗口 {dir_cn}·位移+{price_change:.1f}%·CVD{'顺' if direction=='long' else '逆'}"


# ═══════════════════════════════════════
# FVG 检测 — 公允价值缺口（未填充区域）
# ═══════════════════════════════════════

def detect_fvg(ohlcv: list[dict]) -> Optional[dict]:
    """
    检测最近未填充的 FVG。
    
    多头 FVG: K线低点 > 前前K线高点（价格跳过该区域向上）
    空头 FVG: K线高点 < 前前K线低点（价格跳过该区域向下）
    """
    if len(ohlcv) < 5:
        return None
    
    # 找最近5根内的FVG
    for i in range(-5, -1):
        if abs(i) > len(ohlcv):
            break
        
        curr = ohlcv[i]
        prev2 = ohlcv[i - 2] if i - 2 >= -len(ohlcv) else None
        if not prev2:
            continue
        
        c_low = float(curr.get("low", 0))
        c_high = float(curr.get("high", 0))
        p2_high = float(prev2.get("high", 0))
        p2_low = float(prev2.get("low", 0))
        
        # 多头FVG
        if c_low > p2_high and c_low - p2_high > 0:
            return {
                "type": "bullish",
                "top": c_low,
                "bottom": p2_high,
                "size_pct": round((c_low - p2_high) / p2_high * 100, 2),
                "bars_ago": abs(i),
            }
        
        # 空头FVG
        if c_high < p2_low and p2_low - c_high > 0:
            return {
                "type": "bearish",
                "top": p2_low,
                "bottom": c_high,
                "size_pct": round((p2_low - c_high) / c_high * 100, 2),
                "bars_ago": abs(i),
            }
    
    return None


def fvg_entry_score(price: float, fvg: dict, tv_data: dict) -> Tuple[str, float, str]:
    """
    价格回到FVG区域时的入场评分。
    
    返回: (direction, confidence, reasoning)
    """
    if not fvg:
        return "null", 0.0, "无FVG"
    
    fvg_top = fvg["top"]
    fvg_bottom = fvg["bottom"]
    in_zone = fvg_bottom <= price <= fvg_top
    
    if not in_zone:
        return "null", 0.0, f"价格未在FVG区域(距±{abs(price-fvg_top):.0f})"
    
    direction = "long" if fvg["type"] == "bullish" else "short"
    confidence = 0.45  # FVG单独不足以入场，需配合其他信号
    
    # FVG大小适中最佳（太大=不确定性高，太小=不重要）
    if 0.1 < fvg["size_pct"] < 1.0:
        confidence += 0.10
    elif fvg["size_pct"] > 2.0:
        confidence -= 0.10
    
    # CVD配合
    cvd_slope = float(tv_data.get("cvd_slope", 0))
    if (direction == "long" and cvd_slope > 0) or (direction == "short" and cvd_slope < 0):
        confidence += 0.08
    
    dir_cn = "做多" if direction == "long" else "做空"
    return direction, min(confidence, 1.0), f"FVG填充({fvg['type']}·size{fvg['size_pct']}%)"


# ═══════════════════════════════════════
# Liquidity Sweep 检测
# ═══════════════════════════════════════

def detect_liquidity_sweep(ohlcv: list[dict], tv_data: dict) -> dict | None:
    """
    检测流动性扫荡：刺破前高低点后快速收回。
    """
    if len(ohlcv) < 10:
        return None
    
    highs = [float(b.get("high", 0)) for b in ohlcv[-10:]]
    lows = [float(b.get("low", 0)) for b in ohlcv[-10:]]
    closes = [float(b.get("close", 0)) for b in ohlcv[-10:]]
    opens = [float(b.get("open", 0)) for b in ohlcv[-10:]]
    
    # 前5根的高低范围
    prev_high = max(highs[:5]) if highs[:5] else 0
    prev_low = min(lows[:5]) if lows[:5] else 0
    current_low = lows[-1]
    current_high = highs[-1]
    current_close = closes[-1]
    current_open = opens[-1]
    
    # 向下扫荡：刺破前低后收回（看涨信号）
    if current_low < prev_low and current_close > prev_low:
        wick_down = abs(min(current_open, current_close) - current_low)
        body = abs(current_close - current_open)
        if wick_down > body * 1.5:  # 长下影线
            return {
                "type": "bullish_sweep",
                "sweep_level": current_low,
                "recovery_level": prev_low,
                "wick_ratio": round(wick_down / max(body, 1), 1),
            }
    
    # 向上扫荡：刺破前高后收回（看跌信号）
    if current_high > prev_high and current_close < prev_high:
        wick_up = current_high - max(current_open, current_close)
        body = abs(current_close - current_open)
        if wick_up > body * 1.5:
            return {
                "type": "bearish_sweep",
                "sweep_level": current_high,
                "recovery_level": prev_high,
                "wick_ratio": round(wick_up / max(body, 1), 1),
            }
    
    return None


def sweep_entry_score(sweep: dict, tv_data: dict) -> Tuple[str, float, str]:
    """流动性扫荡的入场评分。"""
    if not sweep:
        return "null", 0.0, "无扫荡"
    
    direction = "long" if sweep["type"] == "bullish_sweep" else "short"
    confidence = 0.50
    
    # 影线/实体比越大越可靠
    if sweep["wick_ratio"] > 2.5:
        confidence += 0.10
    elif sweep["wick_ratio"] > 2.0:
        confidence += 0.05
    
    # CVD 方向验证
    cvd_slope = float(tv_data.get("cvd_slope", 0))
    if (direction == "long" and cvd_slope > 0) or (direction == "short" and cvd_slope < 0):
        confidence += 0.08
    
    dir_cn = "做多" if direction == "long" else "做空"
    return direction, min(confidence, 1.0), f"扫流动性·{sweep['type']}·wick{sweep['wick_ratio']}x"


# ═══════════════════════════════════════
# 三层确认组合评分（A+ 入场）
# ═══════════════════════════════════════

def triple_confirmation_score(
    price: float,
    ohlcv: list[dict],
    tv_data: dict,
    session: dict,
) -> Tuple[str, float, str]:
    """
    OB(Order Block) + FVG + Liquidity Sweep 三层确认。
    任意两层同时满足 → A级信号。
    三层同时满足 → A+ 信号。
    """
    fvg = detect_fvg(ohlcv)
    sweep = detect_liquidity_sweep(ohlcv, tv_data)
    
    # 简化 OB 检测：用 VAH/VAL/POC 替代
    poc = float(tv_data.get("poc", 0))
    vah = float(tv_data.get("vah", 0))
    val = float(tv_data.get("val", 0))
    
    # OB 确认：价格在价值区内
    ob_confirmed = val <= price <= vah
    
    fvg_result = fvg_entry_score(price, fvg, tv_data) if fvg else ("null", 0.0, "无FVG")
    sweep_result = sweep_entry_score(sweep, tv_data) if sweep else ("null", 0.0, "无扫荡")
    
    # 计算确认层数
    layers = 0
    direction_votes = {"long": 0, "short": 0}
    
    if ob_confirmed and poc > 0:
        layers += 1
        if price > poc:
            direction_votes["long"] += 1
        else:
            direction_votes["short"] += 1
    
    if fvg_result[0] != "null":
        layers += 1
        direction_votes[fvg_result[0]] += 1
    
    if sweep_result[0] != "null":
        layers += 1
        direction_votes[sweep_result[0]] += 1
    
    # 确定主导方向
    direction = "long" if direction_votes["long"] >= direction_votes["short"] else "short"
    if direction_votes["long"] == 0 and direction_votes["short"] == 0:
        return "null", 0.0, "无方向确认"
    
    # 评分
    if layers >= 3:
        confidence = 0.75
        grade = "A+"
    elif layers >= 2:
        confidence = 0.60
        grade = "A"
    elif layers >= 1:
        confidence = 0.40
        grade = "B"
    else:
        return "null", 0.0, "无确认层"
    
    dir_cn = "做多" if direction == "long" else "做空"
    details = []
    if ob_confirmed: details.append("OB确认")
    if fvg: details.append(f"FVG({fvg['type']})")
    if sweep: details.append(f"Sweep({sweep['type']})")
    
    return direction, confidence, f"{grade}·{dir_cn}·{'+'.join(details)}·{layers}层"


if __name__ == "__main__":
    print("三层确认模型已加载")
    print("可用: detect_silver_bullet | detect_fvg | detect_liquidity_sweep | triple_confirmation_score")
