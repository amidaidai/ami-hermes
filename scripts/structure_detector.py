#!/usr/bin/env python3
"""
棠溪 · 简易结构检测器 v1.0（替换不可用的SMC库）
纯 Python，零外部依赖

输出: swing高/低点、支撑/阻力位、近期极值
"""

import json
from typing import Optional


def detect_swings(highs: list[float], lows: list[float], lookback: int = 5) -> dict:
    """
    检测近期摆动高/低点
    
    Args:
        highs: 高值序列 (最近在最后)
        lows:  低值序列
        lookback: 回看窗口
    
    Returns:
        {"swing_highs": [...], "swing_lows": [...], "recent_high": float, "recent_low": float}
    """
    n = len(highs)
    swing_highs = []
    swing_lows = []
    
    for i in range(lookback, n - lookback):
        # Swing high: 当前高点 > 前后lookback根
        if highs[i] == max(highs[i-lookback:i+lookback+1]):
            swing_highs.append({"index": i, "price": highs[i]})
        # Swing low: 当前低点 < 前后lookback根
        if lows[i] == min(lows[i-lookback:i+lookback+1]):
            swing_lows.append({"index": i, "price": lows[i]})
    
    # 去重相邻
    swing_highs = dedup_adjacent(swing_highs, "price")
    swing_lows = dedup_adjacent(swing_lows, "price")
    
    return {
        "swing_highs": swing_highs[-5:],   # 最近5个
        "swing_lows": swing_lows[-5:],
        "recent_high": max(highs[-50:]) if len(highs) >= 50 else max(highs),
        "recent_low": min(lows[-50:]) if len(lows) >= 50 else min(lows),
    }


def dedup_adjacent(items: list[dict], key: str) -> list[dict]:
    """去重相邻相同值"""
    if not items:
        return items
    result = [items[0]]
    for item in items[1:]:
        if item[key] != result[-1][key]:
            result.append(item)
    return result


def find_support_resistance(highs: list[float], lows: list[float], closes: list[float],
                             n_levels: int = 3, threshold_pct: float = 0.005) -> dict:
    """
    从摆动点找支撑/阻力
    
    支撑: 近期低点的聚类
    阻力: 近期高点的聚类
    """
    swings = detect_swings(highs, lows, lookback=5)
    
    # 阻力 = 近期摆动高点
    resistances = []
    for sh in swings["swing_highs"]:
        resistances.append({"price": sh["price"], "source": "swing_high"})
    
    # 支撑 = 近期摆动低点
    supports = []
    for sl in swings["swing_lows"]:
        supports.append({"price": sl["price"], "source": "swing_low"})
    
    # 排序：支撑升序、阻力降序
    supports.sort(key=lambda x: x["price"])
    resistances.sort(key=lambda x: x["price"], reverse=True)
    
    return {
        "supports": supports[:n_levels],
        "resistances": resistances[:n_levels],
        "recent_high": swings["recent_high"],
        "recent_low": swings["recent_low"],
    }


def structure_quality(levels: dict, current_price: float, atr: Optional[float] = None) -> dict:
    """
    评估结构位质量
    
    Returns:
        {"score": int, "grade": str, "details": [...]}
    """
    score = 50
    details = []
    
    supports = levels.get("supports", [])
    resistances = levels.get("resistances", [])
    
    if supports and resistances:
        score += 20
        details.append("支撑+阻力双向")
    elif supports:
        score += 10
        details.append("仅有支撑")
    elif resistances:
        score += 10
        details.append("仅有阻力")
    
    # 是否在支撑/阻力附近
    if supports:
        nearest_support = min(supports, key=lambda x: abs(x["price"] - current_price))
        support_distance_pct = abs(current_price - nearest_support["price"]) / current_price
        if support_distance_pct < 0.01:
            score += 15
            details.append(f"距支撑{nearest_support['price']:.0f}仅{support_distance_pct*100:.1f}%")
    if resistances:
        nearest_resistance = min(resistances, key=lambda x: abs(x["price"] - current_price))
        resistance_distance_pct = abs(current_price - nearest_resistance["price"]) / current_price
        if resistance_distance_pct < 0.01:
            score += 10
            details.append(f"距阻力{nearest_resistance['price']:.0f}仅{resistance_distance_pct*100:.1f}%")
    
    score = min(100, score)
    
    grade = "A" if score >= 80 else "B" if score >= 65 else "C"
    
    return {"score": score, "grade": grade, "details": details}


# ═══ CLI ═══
if __name__ == "__main__":
    # Demo
    highs = [66166, 66302, 66162, 65980, 65899, 66068, 66114, 66118, 66150, 66190,
             66347, 66573, 66550, 66527, 66478, 66426, 66383, 66503, 66595, 66653,
             66992, 66924, 66763, 66734, 66728, 66593, 66778, 66672, 66622, 66643,
             66582, 66479, 66490, 66570, 66683, 66818, 66500, 66463, 66275, 66166,
             66210, 66266, 66068, 65748, 65780, 65880, 65908, 66000, 65986, 65954,
             65822, 65866, 65827, 65852, 65862, 66011, 66249, 66137, 65970, 65932,
             65848, 65722, 65780, 65726, 65760, 65849, 65844, 65866, 65938, 65918,
             65754, 65788, 65880, 65882, 65792, 65792, 65834, 65763, 65778, 65723,
             65807, 65840, 65848, 65957, 65940, 65940, 66200, 66108, 65915, 65904,
             65820, 65883, 65854, 65902, 65945, 66048, 65978, 65862, 65928, 65934]
    
    lows = [66100, 66134, 65980, 65802, 65806, 65840, 65966, 66011, 66045, 66045,
            66154, 66296, 66394, 66348, 66319, 66315, 66300, 66345, 66369, 66514,
            66570, 66726, 66560, 66586, 66475, 66501, 66540, 66578, 66486, 66449,
            66397, 66368, 66380, 66406, 66547, 66442, 66368, 66010, 66011, 65928,
            66007, 66008, 65516, 65361, 65610, 65614, 65713, 65803, 65679, 65776,
            65726, 65706, 65706, 65740, 65710, 65740, 65951, 65872, 65802, 65828,
            65655, 65560, 65602, 65566, 65592, 65694, 65720, 65830, 65838, 65727,
            65655, 65710, 65715, 65721, 65704, 65680, 65727, 65644, 65712, 65627,
            65675, 65688, 65699, 65578, 65840, 65880, 65788, 65834, 65808, 65703,
            65780, 65770, 65824, 65788, 65864, 65892, 65794, 65747, 65814, 65774]
    
    closes = [63940, 63952, 63884, 63883, 63921]  # 简化
    
    result = find_support_resistance(highs, lows, closes)
    quality = structure_quality(result, closes[-1])
    
    print(json.dumps({
        "levels": result,
        "quality": quality
    }, indent=2, ensure_ascii=False))
