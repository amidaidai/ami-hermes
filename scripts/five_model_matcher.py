#!/usr/bin/env python3
"""
棠溪 · 五模型入场生成器 v1.0
融合: analyseur-crypto (alexch03) setup_generator 规则化框架

五类固定模型（V5.1 核心）:
  1. VWAP反抽 — 价格偏离VWAP后回归 → 反抽入场
  2. VAH回收   — 价格突破VAH后回踩 → 回收入场
  3. VAL回收   — 价格跌破VAL后回升 → 回收入场
  4. POC拒绝   — 价格测试POC被拒绝 → 拒绝入场
  5. 扫流动性回收 — 价格扫高低点后快速收回 → 回收入场
  6. 突破接受   — 价格突破关键位并回踩确认 → 顺势入场

每个模型独立包含: 触发条件 + 入场价 + 止损 + 止盈 + 失效条件
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class SetupLevel:
    """单个入场位"""
    name: str
    direction: str          # "long" / "short"
    entry: float
    stop: float
    targets: list[float]
    invalid_if: str
    condition: str          # "breach" / "near_or_breach" / "close_confirm"
    priority: str           # "high" / "medium"
    confidence_score: int   # 0-100
    confluence: list[str]   # 合流确认项
    rr_ratio: float = 0.0


@dataclass
class ModelSetup:
    """模型完整入场方案"""
    model_name: str
    model_name_zh: str
    direction: str           # "long" / "short" / "neutral"
    setups: list[SetupLevel]
    notes: list[str]


# ═══ VWAP反抽 ═══
def vwap_rejection(current_price: float, vwap: float, vwap_band1: float,
                     vwap_band2: float, ema9: float, ema21: float,
                     cvd_value: float, cvd_slope: float) -> ModelSetup:
    """
    VWAP反抽模型
    
    触发：价格从VWAP band外回归 → 在VWAP/Band1处反抽
    方向由EMA排列决定：9<21→偏空向下反抽，9>21→偏多向上反抽
    """
    setups = []
    notes = []
    
    # 方向判定
    if ema9 < ema21:
        direction = "short"
        direction_zh = "做空"
        notes.append(f"EMA空头排列 9({ema9:.0f})<21({ema21:.0f})")
    elif ema9 > ema21:
        direction = "long"
        direction_zh = "做多"
        notes.append(f"EMA多头排列 9({ema9:.0f})>21({ema21:.0f})")
    else:
        return ModelSetup("vwap_rejection", "VWAP反抽", "neutral", [], ["EMA平行·无方向"])
    
    if direction == "short":
        # 做空：价格回弹到VWAP/Band1 → 反抽做空
        if current_price < vwap:
            entry = vwap
            stop = vwap_band1 * 1.002  # 止损略高于Band1
            targets = [vwap_band2, vwap_band2 * 0.985]
            
            rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
            
            setups.append(SetupLevel(
                name="S1_VWAP拒绝做空",
                direction="short",
                entry=round(entry, 1),
                stop=round(stop, 1),
                targets=[round(t, 1) for t in targets],
                invalid_if=f"15m close above {vwap_band1:.0f}",
                condition="breach",
                priority="high",
                confidence_score=78,
                confluence=[
                    f"价格({current_price:.0f})<VWAP({vwap:.0f})",
                    f"EMA空头排列",
                    f"CVD {cvd_value:.0f} {'配合' if cvd_value < 0 else '未配合'}",
                ],
                rr_ratio=round(rr, 1),
            ))
    else:
        # 做多：价格回落到VWAP/Band1 → 反抽做多
        if current_price > vwap:
            entry = vwap
            stop = vwap_band1 * 0.998
            targets = [vwap_band1 * 1.015, vwap_band1 * 1.03]
            
            rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
            
            setups.append(SetupLevel(
                name="S1_VWAP反弹做多",
                direction="long",
                entry=round(entry, 1),
                stop=round(stop, 1),
                targets=[round(t, 1) for t in targets],
                invalid_if=f"15m close below {vwap_band1:.0f}",
                condition="breach",
                priority="high",
                confidence_score=78,
                confluence=[
                    f"价格({current_price:.0f})>VWAP({vwap:.0f})",
                    f"EMA多头排列",
                    f"CVD {cvd_value:.0f} {'配合' if cvd_value > 0 else '未配合'}",
                ],
                rr_ratio=round(rr, 1),
            ))
    
    return ModelSetup("vwap_rejection", "VWAP反抽", direction, setups, notes)


# ═══ VAH回收 ═══
def vah_reclaim(current_price: float, vah: float, vwap: float,
                 poc: float, cvd_value: float) -> ModelSetup:
    """
    VAH回收模型
    
    触发：价格突破VAH后回踩VAH不破 → 顺势做多
    或：价格未达VAH即回落 → 偏空
    """
    setups = []
    notes = []
    
    if current_price > vah:
        # 已突破VAH → 回踩VAH做多
        entry = vah
        stop = vah * 0.995
        targets = [vah * 1.01, vah * 1.02]
        rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        
        setups.append(SetupLevel(
            name="S1_VAH回踩做多",
            direction="long",
            entry=round(entry, 1),
            stop=round(stop, 1),
            targets=[round(t, 1) for t in targets],
            invalid_if=f"15m close below {vah * 0.995:.0f}",
            condition="near_or_breach",
            priority="high",
            confidence_score=75,
            confluence=[
                f"价格({current_price:.0f})>VAH({vah:.0f})",
                f"突破接受后回踩确认",
            ],
            rr_ratio=round(rr, 1),
        ))
        notes.append("已突破VAH·等回踩确认做多")
        return ModelSetup("vah_reclaim", "VAH回收", "long", setups, notes)
    
    elif current_price < vah and current_price > poc:
        # 在VAH和POC之间 → VAH做空反抽
        entry = vah
        stop = vah * 1.003
        targets = [poc, vwap]
        rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        
        setups.append(SetupLevel(
            name="S1_VAH拒绝做空",
            direction="short",
            entry=round(entry, 1),
            stop=round(stop, 1),
            targets=[round(t, 1) for t in targets],
            invalid_if=f"15m close above {vah * 1.005:.0f}",
            condition="near_or_breach",
            priority="high",
            confidence_score=74,
            confluence=[
                f"价格({current_price:.0f})在POC({poc:.0f})-VAH({vah:.0f})间",
                f"VAH做空反抽",
            ],
            rr_ratio=round(rr, 1),
        ))
        notes.append("POC-VAH区间·VAH做空反抽")
        return ModelSetup("vah_reclaim", "VAH回收", "short", setups, notes)
    
    return ModelSetup("vah_reclaim", "VAH回收", "neutral", [], ["价格在VAL以下·不适用VAH回收"])


# ═══ VAL回收 ═══
def val_reclaim(current_price: float, val: float, vwap: float,
                 poc: float, cvd_value: float) -> ModelSetup:
    """
    VAL回收模型
    
    触发：价格跌破VAL后回升站上VAL → 做多回收
    或：价格在VAL上方 → VAL做多回收
    """
    setups = []
    notes = []
    
    if current_price < val:
        # 跌破了VAL → 等回升站上VAL做多
        entry = val
        stop = val * 0.995
        targets = [poc, vwap]
        rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        
        setups.append(SetupLevel(
            name="S1_VAL回收做多",
            direction="long",
            entry=round(entry, 1),
            stop=round(stop, 1),
            targets=[round(t, 1) for t in targets],
            invalid_if=f"15m close below {val * 0.992:.0f}",
            condition="close_confirm",
            priority="high",
            confidence_score=73,
            confluence=[
                f"价格({current_price:.0f})<VAL({val:.0f})",
                f"等回升站上VAL做多",
            ],
            rr_ratio=round(rr, 1),
        ))
        notes.append("跌破VAL·等回收站上VAL做多")
        return ModelSetup("val_reclaim", "VAL回收", "long", setups, notes)
    
    elif current_price > val and current_price < poc:
        # VAL上方→回踩VAL做多
        entry = val
        stop = val * 0.995
        targets = [poc, vwap]
        rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        
        setups.append(SetupLevel(
            name="S1_VAL回踩做多",
            direction="long",
            entry=round(entry, 1),
            stop=round(stop, 1),
            targets=[round(t, 1) for t in targets],
            invalid_if=f"15m close below {val * 0.992:.0f}",
            condition="near_or_breach",
            priority="high",
            confidence_score=76,
            confluence=[
                f"价格({current_price:.0f})在VAL({val:.0f})-POC({poc:.0f})间",
                f"VAL回踩做多",
            ],
            rr_ratio=round(rr, 1),
        ))
        notes.append("VAL-POC区间·回踩VAL做多")
        return ModelSetup("val_reclaim", "VAL回收", "long", setups, notes)
    
    return ModelSetup("val_reclaim", "VAL回收", "neutral", [], ["价格在VAH以上·不适用VAL回收"])


# ═══ POC拒绝 ═══
def poc_rejection(current_price: float, poc: float, vah: float, val: float,
                   cvd_value: float) -> ModelSetup:
    """
    POC拒绝模型
    
    触发：价格测试POC被拒绝 → 反向入场
    """
    setups = []
    notes = []
    
    if current_price < poc:
        # POC下方→测试POC做空
        entry = poc
        stop = poc * 1.003
        targets = [val, val * 0.99]
        rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        
        setups.append(SetupLevel(
            name="S1_POC拒绝做空",
            direction="short",
            entry=round(entry, 1),
            stop=round(stop, 1),
            targets=[round(t, 1) for t in targets],
            invalid_if=f"15m close above {poc * 1.005:.0f}",
            condition="near_or_breach",
            priority="high",
            confidence_score=76,
            confluence=[
                f"价格({current_price:.0f})<POC({poc:.0f})",
                f"测试POC做空",
                f"CVD {cvd_value:.0f} {'配合' if cvd_value < 0 else '未配合'}",
            ],
            rr_ratio=round(rr, 1),
        ))
        notes.append("POC下方·测试POC做空")
        return ModelSetup("poc_rejection", "POC拒绝", "short", setups, notes)
    
    elif current_price > poc:
        # POC上方→测试POC做多
        entry = poc
        stop = poc * 0.997
        targets = [vah, vah * 1.01]
        rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        
        setups.append(SetupLevel(
            name="S1_POC反弹做多",
            direction="long",
            entry=round(entry, 1),
            stop=round(stop, 1),
            targets=[round(t, 1) for t in targets],
            invalid_if=f"15m close below {poc * 0.995:.0f}",
            condition="near_or_breach",
            priority="high",
            confidence_score=76,
            confluence=[
                f"价格({current_price:.0f})>POC({poc:.0f})",
                f"测试POC做多",
            ],
            rr_ratio=round(rr, 1),
        ))
        notes.append("POC上方·测试POC做多")
        return ModelSetup("poc_rejection", "POC拒绝", "long", setups, notes)
    
    return ModelSetup("poc_rejection", "POC拒绝", "neutral", [], ["价格=POC·无方向"])


# ═══ 扫流动性回收 ═══
def liquidity_sweep(current_price: float, recent_high: float, recent_low: float,
                     atr: float, cvd_value: float) -> ModelSetup:
    """
    扫流动性回收模型
    
    触发：价格刺破近期高/低点后快速收回
    """
    setups = []
    notes = []
    
    sweep_range = atr * 0.3
    
    if abs(current_price - recent_low) < sweep_range:
        # 在低点附近→扫低回收做多
        entry = recent_low
        stop = recent_low * 0.993
        targets = [recent_low * 1.015, recent_low * 1.03]
        rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        
        setups.append(SetupLevel(
            name="S1_扫低回收做多",
            direction="long",
            entry=round(entry, 1),
            stop=round(stop, 1),
            targets=[round(t, 1) for t in targets],
            invalid_if=f"15m close below {recent_low * 0.99:.0f}",
            condition="close_confirm",
            priority="high",
            confidence_score=80,
            confluence=[
                f"距近期低点{recent_low:.0f}仅{sweep_range:.0f}点",
                f"ATR {atr:.0f}·扫低空间充足",
                f"需5m收盘确认收回",
            ],
            rr_ratio=round(rr, 1),
        ))
        notes.append("低点附近·扫低回收做多")
        return ModelSetup("liquidity_sweep", "扫流动性回收", "long", setups, notes)
    
    elif abs(current_price - recent_high) < sweep_range:
        # 在高点附近→扫高回收做空
        entry = recent_high
        stop = recent_high * 1.007
        targets = [recent_high * 0.985, recent_high * 0.97]
        rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        
        setups.append(SetupLevel(
            name="S1_扫高回收做空",
            direction="short",
            entry=round(entry, 1),
            stop=round(stop, 1),
            targets=[round(t, 1) for t in targets],
            invalid_if=f"15m close above {recent_high * 1.01:.0f}",
            condition="close_confirm",
            priority="high",
            confidence_score=80,
            confluence=[
                f"距近期高点{recent_high:.0f}仅{sweep_range:.0f}点",
                f"ATR {atr:.0f}·扫高空间充足",
                f"需5m收盘确认收回",
            ],
            rr_ratio=round(rr, 1),
        ))
        notes.append("高点附近·扫高回收做空")
        return ModelSetup("liquidity_sweep", "扫流动性回收", "short", setups, notes)
    
    return ModelSetup("liquidity_sweep", "扫流动性回收", "neutral", [],
                       [f"距高点{recent_high-recent_low:.0f}点·中间位置"])


# ═══ 突破接受 ═══
def breakout_accept(current_price: float, key_level: float, side: str,
                     atr: float, cvd_value: float) -> ModelSetup:
    """
    突破接受模型
    
    触发：价格突破关键位(支撑/阻力)并回踩确认
    side: "support"→跌破支撑→做空, "resistance"→突破阻力→做多
    """
    setups = []
    
    if side == "resistance" and current_price > key_level:
        # 突破阻力→回踩做多
        entry = key_level
        stop = key_level * 0.995
        targets = [key_level * 1.015, key_level * 1.03]
        rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        
        setups.append(SetupLevel(
            name="S1_突破阻力做多",
            direction="long",
            entry=round(entry, 1),
            stop=round(stop, 1),
            targets=[round(t, 1) for t in targets],
            invalid_if=f"15m close below {key_level * 0.995:.0f}",
            condition="near_or_breach",
            priority="high",
            confidence_score=74,
            confluence=[
                f"突破阻力{key_level:.0f}",
                f"回踩确认不破→做多",
            ],
            rr_ratio=round(rr, 1),
        ))
        return ModelSetup("breakout_accept", "突破接受", "long", setups, [])
    
    elif side == "support" and current_price < key_level:
        # 跌破支撑→反弹做空
        entry = key_level
        stop = key_level * 1.005
        targets = [key_level * 0.985, key_level * 0.97]
        rr = abs(entry - targets[0]) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        
        setups.append(SetupLevel(
            name="S1_跌破支撑做空",
            direction="short",
            entry=round(entry, 1),
            stop=round(stop, 1),
            targets=[round(t, 1) for t in targets],
            invalid_if=f"15m close above {key_level * 1.005:.0f}",
            condition="near_or_breach",
            priority="high",
            confidence_score=74,
            confluence=[
                f"跌破支撑{key_level:.0f}",
                f"反弹确认不过→做空",
            ],
            rr_ratio=round(rr, 1),
        ))
        return ModelSetup("breakout_accept", "突破接受", "short", setups, [])
    
    return ModelSetup("breakout_accept", "突破接受", "neutral", [],
                       [f"距{side}{key_level:.0f}较远·等待"])


# ═══ 五模型全量运行 ═══
def generate_all_setups(current_price: float,
                         vwap: float, vwap_band1: float, vwap_band2: float,
                         vah: float, val: float, poc: float,
                         ema9: float, ema21: float,
                         recent_high: float, recent_low: float,
                         atr: float, cvd_value: float, cvd_slope: float = 0) -> dict:
    """
    五模型全量运行 → 匹配最佳入场方案
    
    Returns:
        {
            "symbol": str,
            "price": float,
            "matched_models": [...],    # 有匹配的模型
            "best_setup": {...},       # 最高置信度入场
            "all_setups": [...],       # 所有入场位
        }
    """
    results = []
    
    # 1. VWAP反抽
    vwap_setup = vwap_rejection(current_price, vwap, vwap_band1, vwap_band2,
                                  ema9, ema21, cvd_value, cvd_slope)
    if vwap_setup.direction != "neutral":
        results.append(vwap_setup)
    
    # 2. VAH回收
    vah_setup = vah_reclaim(current_price, vah, vwap, poc, cvd_value)
    if vah_setup.direction != "neutral":
        results.append(vah_setup)
    
    # 3. VAL回收
    val_setup = val_reclaim(current_price, val, vwap, poc, cvd_value)
    if val_setup.direction != "neutral":
        results.append(val_setup)
    
    # 4. POC拒绝
    poc_setup = poc_rejection(current_price, poc, vah, val, cvd_value)
    if poc_setup.direction != "neutral":
        results.append(poc_setup)
    
    # 5. 扫流动性回收
    sweep_setup = liquidity_sweep(current_price, recent_high, recent_low, atr, cvd_value)
    if sweep_setup.direction != "neutral":
        results.append(sweep_setup)
    
    # 找最佳
    all_setups = []
    best = None
    for model in results:
        for s in model.setups:
            all_setups.append({
                "model": model.model_name_zh,
                "direction": s.direction,
                "entry": s.entry,
                "stop": s.stop,
                "targets": s.targets,
                "confidence": s.confidence_score,
                "rr_ratio": s.rr_ratio,
                "confluence": s.confluence,
            })
            if best is None or s.confidence_score > best["confidence"]:
                best = {
                    "model": model.model_name_zh,
                    "direction": s.direction,
                    "entry": s.entry,
                    "stop": s.stop,
                    "targets": s.targets,
                    "confidence": s.confidence_score,
                    "rr_ratio": s.rr_ratio,
                    "confluence": s.confluence,
                    "invalid_if": s.invalid_if,
                }
    
    matched = [r.model_name_zh for r in results]
    
    return {
        "price": current_price,
        "matched_models": matched,
        "best_setup": best,
        "all_setups": sorted(all_setups, key=lambda x: x["confidence"], reverse=True),
    }


# ═══ CLI ═══
if __name__ == "__main__":
    # Demo: 用当前BTC数据跑五模型
    result = generate_all_setups(
        current_price=63980,
        vwap=64308, vwap_band1=63988, vwap_band2=63668,
        vah=64806, val=63985, poc=64684,
        ema9=64066, ema21=64266,
        recent_high=66192, recent_low=63696,
        atr=450, cvd_value=-469, cvd_slope=-102.5,
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
