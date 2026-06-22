#!/usr/bin/env python3
"""2022 ICT/SMC 模型管线 — Sweep→Displacement→FVG→Retest→Entry"""
import json, os
from datetime import datetime, timezone, timedelta
from collections import deque

TZ = timezone(timedelta(hours=8))
DIR = os.path.expanduser("~/AppData/Local/hermes/data")

FVG_AVAILABLE = True
try:
    from fvg_detector import detect_fvg, update_fvg_status, best_fvg
except ImportError:
    FVG_AVAILABLE = False
    # 静默降级


def detect_sweep(klines, levels=None):
    """检测流动性扫荡。
    
    扫荡定义: 价格突破关键位(前高/低/VAH/VAL/POC)后30s/1根K线内回收。
    
    Args:
        klines: list of [time, open, high, low, close, volume]
        levels: dict of {name: price} 关键位
    
    Returns:
        dict: {swept, direction, level_price, level_name, recovery}
    """
    if not levels:
        levels = {}
    if not klines or len(klines) < 5:
        return {"swept": False, "direction": "none", "level_price": 0, "level_name": ""}
    
    # 最近5根K线
    recent = klines[-5:]
    last = recent[-1]
    last_close = float(last[4])
    last_low = float(last[3])
    last_high = float(last[2])
    
    # 对每个关键位检查扫荡
    for name, price in levels.items():
        if not price or price == 0:
            continue
        
        # 向下扫荡: 价格突破支撑后回收
        if last_low < price and last_close > price:
            return {
                "swept": True,
                "direction": "bullish",
                "level_price": price,
                "level_name": name,
                "recovery": round(abs(last_close - price), 2),
                "sweep_depth": round(abs(last_low - price), 2),
            }
        
        # 向上扫荡: 价格突破阻力后回收
        if last_high > price and last_close < price:
            return {
                "swept": True,
                "direction": "bearish",
                "level_price": price,
                "level_name": name,
                "recovery": round(abs(price - last_close), 2),
                "sweep_depth": round(abs(last_high - price), 2),
            }
    
    return {"swept": False, "direction": "none", "level_price": 0, "level_name": ""}


def detect_displacement(klines, start_idx=None):
    """检测扫荡后的位移。
    
    位移定义: 扫荡后5根K线内出现强势移动(大实体+放量)。
    
    Returns:
        dict: {displaced, direction, strength, fvg_formed}
    """
    if not klines or len(klines) < 5:
        return {"displaced": False, "direction": "none", "strength": 0, "fvg_formed": False}
    
    if start_idx is None:
        start_idx = max(0, len(klines) - 10)
    
    lookback = klines[start_idx:]
    if len(lookback) < 5:
        return {"displaced": False, "direction": "none", "strength": 0, "fvg_formed": False}
    
    # 前5根均值成交量
    vol_ma = sum(float(k[5]) for k in lookback[:5]) / min(len(lookback[:5]), 5)
    if vol_ma == 0:
        vol_ma = 1
    
    best_move = 0
    direction = "none"
    fvg_in_displacement = False
    
    for i in range(1, min(6, len(lookback))):
        o = float(lookback[i][1])
        c = float(lookback[i][4])
        h = float(lookback[i][2])
        l = float(lookback[i][3])
        v = float(lookback[i][5])
        
        body_pct = abs(c - o) / o * 100
        vol_ratio = v / vol_ma if vol_ma > 0 else 1
        
        # 位移条件: 实体>0.3% 且 放量>1.3x
        if body_pct > 0.3 and vol_ratio > 1.3:
            move = body_pct * vol_ratio
            if move > best_move:
                best_move = move
                direction = "bullish" if c > o else "bearish"
    
    # 检查是否形成FVG
    if FVG_AVAILABLE:
        fvgs = detect_fvg(klines[-30:], lookback=30)
        fvg_in_displacement = len(fvgs) > 0
    
    displaced = best_move > 0.5
    return {
        "displaced": displaced,
        "direction": direction,
        "strength": round(best_move, 2),
        "fvg_formed": fvg_in_displacement,
    }


def check_retest(klines, fvg_midpoint, tolerance=10):
    """检测价格是否回测FVG 50%线。"""
    if not klines or not fvg_midpoint:
        return {"retested": False, "side": "none", "price": 0}
    
    recent = klines[-5:]
    for k in recent:
        h, l = float(k[2]), float(k[3])
        if l <= fvg_midpoint <= h:
            return {"retested": True, "side": "inside", "price": fvg_midpoint}
        if abs(float(k[4]) - fvg_midpoint) < tolerance:
            return {"retested": True, "side": "close_to", "price": float(k[4])}
    
    return {"retested": False, "side": "none", "price": 0}


def run_pipeline(klines, levels=None, current_price=None):
    """全流程运行：sweep→displacement→fvg→retest→entry_signal。
    
    Returns:
        dict: {stage, signal_type, entry_price, confirmations, score, details}
    """
    result = {
        "stage": "idle",
        "signal_type": None,
        "direction": None,
        "entry_price": None,
        "confirmations": [],
        "score": 0,
        "timestamp": datetime.now(TZ).strftime("%H:%M:%S"),
    }
    
    if not klines or len(klines) < 20:
        return result
    
    # Step 1: 检测扫荡
    sweep = detect_sweep(klines, levels)
    if not sweep["swept"]:
        result["stage"] = "wait_sweep"
        result["details"] = "等待流动性扫荡"
        return result
    
    result["confirmations"].append({
        "type": "sweep",
        "direction": sweep["direction"],
        "level": sweep["level_name"],
        "price": sweep["level_price"],
    })
    result["score"] += 2
    
    # Step 2: 检测位移
    displacement = detect_displacement(klines)
    if not displacement["displaced"]:
        result["stage"] = "sweep_no_displacement"
        result["details"] = f"已扫荡{sweep['level_name']}，但无后续位移"
        return result
    
    result["direction"] = displacement["direction"]
    result["confirmations"].append({
        "type": "displacement",
        "direction": displacement["direction"],
        "strength": displacement["strength"],
        "fvg_formed": displacement["fvg_formed"],
    })
    result["score"] += 2
    
    if not displacement["fvg_formed"]:
        result["stage"] = "displacement_no_fvg"
        result["details"] = "有位移但未形成FVG"
        return result
    
    # Step 3: FVG已形成，等待回测
    fvgs = detect_fvg(klines[-30:]) if FVG_AVAILABLE else []
    best = best_fvg(fvgs) if fvgs else None
    
    if not best:
        result["stage"] = "fvg_pending"
        result["details"] = "FVG形成中，等待确认"
        return result
    
    result["confirmations"].append({
        "type": "fvg_formed",
        "midpoint": best["midpoint"],
        "gap": best["gap_size"],
        "fvg_type": best["type"],
    })
    result["score"] += 1
    
    # Step 4: 检测回测
    retest = check_retest(klines, best["midpoint"])
    if retest["retested"]:
        result["stage"] = "entry_ready"
        result["signal_type"] = f"fvg_retest_{best['type']}"
        result["entry_price"] = best["midpoint"]
        result["confirmations"].append({
            "type": "retest",
            "side": retest["side"],
            "price": retest["price"],
        })
        result["score"] += 2
        result["details"] = f"⭐ 入场就绪: {best['type']}FVG回测 @ {best['midpoint']}"
    else:
        result["stage"] = "wait_retest"
        result["details"] = f"FVG@{best['midpoint']}待回测"
        result["entry_price"] = best["midpoint"]
    
    return result


def pipeline_summary(pipe_result):
    """管线结果可读化。"""
    if pipe_result["stage"] == "entry_ready":
        return f"⭐ {pipe_result['direction']} 入场 · FVG回测 @ {pipe_result['entry_price']}"
    elif pipe_result["stage"] == "wait_retest":
        return f"等待FVG回测 @ {pipe_result['entry_price']}"
    elif pipe_result["stage"] == "wait_sweep":
        return "等待流动性扫荡触发"
    else:
        return pipe_result.get("details", f"阶段: {pipe_result['stage']}")


if __name__ == "__main__":
    # 测试: 模拟扫荡+位移+FVG
    import random
    test_klines = []
    base = 64200.0
    for i in range(25):
        if i == 18:
            # 向下扫荡VAL
            test_klines.append([i, base-30, base-20, base-120, base-25, 2000])
        elif i == 19:
            # 扫后回收
            test_klines.append([i, base-25, base+30, base-40, base+20, 3000])
        elif i == 20:
            # 位移阳线
            test_klines.append([i, base+20, base+100, base+10, base+90, 5000])
        elif i == 21:
            test_klines.append([i, base+90, base+140, base+80, base+130, 4000])
        elif i == 22:
            test_klines.append([i, base+130, base+160, base+80, base+90, 3000])
        elif i == 23:
            test_klines.append([i, base+90, base+120, base+70, base+100, 2500])
        elif i == 24:
            test_klines.append([i, base+100, base+115, base+95, base+105, 2000])
        else:
            base += random.randint(-20, 20)
            test_klines.append([i, base, base+30, base-20, base+5, 800])
    
    levels = {"VAL": 64100.0, "VAH": 64600.0, "POC": 64300.0}
    
    result = run_pipeline(test_klines, levels)
    print(f"阶段: {result['stage']}")
    print(f"得分: {result['score']}")
    print(f"详情: {result.get('details', '')}")
    print(f"确认数: {len(result['confirmations'])}")
    for c in result["confirmations"]:
        print(f"  [{c['type']}] {c}")
    print(f"\n摘要: {pipeline_summary(result)}")
