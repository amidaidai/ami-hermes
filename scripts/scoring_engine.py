#!/usr/bin/env python3
"""
棠溪 · 机器化评分引擎 v1.0
融合: trading-scanner (NadirAliOfficial) 14分加权 + 棠溪现有13分体系

用法:
  from scoring_engine import score_setup
  result = score_setup(symbol, structure, orderflow, timeframe, catalyst, risk, sentiment)

输出: {total, max_score, grade, breakdown, recommendation}
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dataclasses import dataclass, field
from typing import Optional

# ═══ 评分权重（融合 trading-scanner 14分体系） ═══
WEIGHTS = {
    "structure":    3.0,   # 结构检测 BOS/CHoCH/FVG/OB 合流
    "orderflow":    2.5,   # CVD + Taker + 量比
    "timeframe":    2.0,   # 4周期一致性
    "catalyst":     2.0,   # 新闻/事件/数据公布
    "risk":         2.5,   # R:R + ATR + 仓位合理性
    "sentiment":    2.0,   # X情绪 + CG情绪 + 恐慌贪婪
}
MAX_SCORE = sum(WEIGHTS.values())  # 14.0

# ═══ 等级映射（融合 trading-scanner 4级） ═══
def grade_from_score(score: float) -> str:
    if score >= 12:
        return "💎 Elite"
    elif score >= 10:
        return "🥇 A+"
    elif score >= 7:
        return "🥈 A"
    elif score >= 4:
        return "🥉 标准"
    else:
        return "❌ 不合格"


def score_structure(smc_result: Optional[dict] = None,
                     tv_levels: Optional[dict] = None,
                     manual_structure: Optional[dict] = None) -> dict:
    """
    结构分：BOS/CHoCH/OB/FVG/EQH/EQL 检测 + TV指标确认
    
    满分3.0，扣分项：
    - 无SMC检测 → -1.5
    - 无BOS/CHoCH → -1.0
    - 无OB/FVG → -0.5
    - TV指标冲突 → -0.5
    """
    score = 0.0
    details = []
    
    if smc_result:
        # SMC结构检测
        sb = smc_result.get("structure_breaks", [])
        bos_count = sum(1 for s in sb if s.get("type") == "BOS")
        choch_count = sum(1 for s in sb if s.get("type") == "CHOCH")
        ob_count = len(smc_result.get("swing_order_blocks", [])) + len(smc_result.get("internal_order_blocks", []))
        fvg_count = len(smc_result.get("fair_value_gaps", []))
        
        if bos_count + choch_count > 0:
            score += 1.5
            details.append(f"BOS×{bos_count} CHoCH×{choch_count}")
        else:
            details.append("无BOS/CHoCH检测")
        
        if ob_count + fvg_count > 0:
            score += 0.75
            details.append(f"OB×{ob_count} FVG×{fvg_count}")
        
        # 趋势确认
        trend = smc_result.get("swing_trend", "neutral")
        if trend != "neutral":
            score += 0.5
            details.append(f"趋势:{trend}")
    else:
        # 用TV指标替代
        if tv_levels:
            vwap = tv_levels.get("S VWAP")
            ema9 = tv_levels.get("EMA 9")
            if vwap and ema9:
                score += 1.0
                details.append("TV VWAP+EMA可用")
        
        if manual_structure:
            score += 0.5
            details.append("手动结构位")
    
    score = min(score, 3.0)
    return {
        "score": round(score, 1),
        "max": 3.0,
        "details": details,
        "grade": "A" if score >= 2.0 else "B" if score >= 1.0 else "C"
    }


def score_orderflow(cvd_value: Optional[float] = None,
                     cvd_slope: Optional[float] = None,
                     taker_ratio: Optional[float] = None,
                     volume_ratio: Optional[float] = None,
                     cvd_quality: str = "C") -> dict:
    """
    订单流分：CVD + Taker + 量比
    
    满分2.5
    - CVD C级 → ×0.6 折扣
    - CVD斜率与方向一致 → +1.0
    - Taker买卖比确认 → +0.75
    - 量比放量(>1.5) → +0.75
    """
    score = 0.0
    details = []
    discount = 0.6 if cvd_quality == "C" else 0.8 if cvd_quality == "B" else 1.0
    
    if cvd_value is not None:
        if cvd_slope is not None:
            score += 1.0 * discount
            details.append(f"CVD {cvd_value:.0f} 斜率{cvd_slope:.0f}")
        else:
            score += 0.5 * discount
            details.append(f"CVD {cvd_value:.0f}")
    
    if taker_ratio is not None:
        direction = "买" if taker_ratio > 1.0 else "卖" if taker_ratio < 1.0 else "中性"
        score += 0.75 * discount
        details.append(f"Taker {direction} {taker_ratio:.2f}")
    
    if volume_ratio is not None:
        if volume_ratio > 2.0:
            details.append(f"量比 {volume_ratio:.1f} 爆量")
            score += 0.75 * discount
        elif volume_ratio > 1.5:
            details.append(f"量比 {volume_ratio:.1f} 放量")
            score += 0.5 * discount
        elif volume_ratio > 0.7:
            details.append(f"量比 {volume_ratio:.1f} 正常")
            score += 0.25 * discount
    
    if cvd_quality == "C":
        details.append("⚠ CVD C级·半仓")
    
    return {
        "score": round(min(score, 2.5), 1),
        "max": 2.5,
        "details": details,
        "discount": discount,
        "grade": "A" if score >= 2.0 else "B" if score >= 1.0 else "C"
    }


def score_timeframe(tf_consensus: int = 0,
                     tf_total: int = 4,
                     tf_details: Optional[dict] = None) -> dict:
    """
    多周期一致性：4h→1h→15m→5m 方向是否一致
    
    满分2.0
    - 4周期一致 → 2.0
    - 3周期一致 → 1.5
    - 2周期一致 → 1.0
    - 1周期或无 → 0.5
    - 0周期(全部冲突) → 0
    """
    ratio = tf_consensus / max(tf_total, 1)
    score = ratio * 2.0
    details = [f"{tf_consensus}/{tf_total} 周期一致"]
    
    if tf_details:
        for tf_name, status in tf_details.items():
            details.append(f"  {tf_name}: {status}")
    
    return {
        "score": round(score, 1),
        "max": 2.0,
        "consensus_ratio": round(ratio, 2),
        "details": details,
        "grade": "A" if ratio >= 0.75 else "B" if ratio >= 0.5 else "C"
    }


def score_catalyst(has_fomc: bool = False,
                    has_nfp: bool = False,
                    has_data_event: bool = False,
                    news_sentiment: str = "neutral",
                    blackout_active: bool = False) -> dict:
    """
    催化分：重大事件 + 新闻情绪
    
    满分2.0
    - 新闻黑窗期(禁做) → 0
    - 无重大事件 → 1.0 (基线)
    - 事件确认方向 → +1.0
    - 事件不确定 → -0.5
    """
    if blackout_active:
        return {"score": 0, "max": 2.0, "details": ["⚠ 新闻黑窗期·禁做"], "grade": "C"}
    
    score = 1.0  # 基线
    details = []
    
    if has_fomc:
        details.append("Fed决议窗口")
    if has_nfp:
        details.append("NFP数据日")
    if has_data_event:
        details.append("重要数据公布")
    
    if news_sentiment == "bullish":
        score += 0.5
        details.append("新闻偏多→+0.5")
    elif news_sentiment == "bearish":
        score += 0.5
        details.append("新闻偏空→+0.5")
    elif news_sentiment == "conflicting":
        score -= 0.5
        details.append("新闻分歧→-0.5")
    
    score = max(0, min(score, 2.0))
    return {
        "score": round(score, 1),
        "max": 2.0,
        "details": details or ["无重大催化"],
        "grade": "A" if score >= 1.5 else "B" if score >= 1.0 else "C"
    }


def score_risk(entry_price: Optional[float] = None,
                stop_price: Optional[float] = None,
                target1_price: Optional[float] = None,
                atr_value: Optional[float] = None,
                risk_usd: Optional[float] = None,
                account_balance: float = 100.0,
                max_risk_pct: float = 0.03,
                daily_pnl: float = 0.0,
                daily_drawdown_pct: float = 0.0,
                consecutive_losses: int = 0) -> dict:
    """
    风控分：R:R + ATR + 仓位合理性 + 风险宪法
    
    满分2.5
    - R:R ≥ 1:2 → +1.0, <1:1.5 → 0
    - 止损 ≥ 0.5×ATR → +0.75
    - 仓位 ≤ 3%本金 → +0.5
    - 日回撤超标 → -1.0
    - 连续亏损 > 3 → -0.75
    """
    score = 0.0
    details = []
    constitution_violations = []
    
    # R:R 检查
    if entry_price and stop_price and target1_price:
        risk = abs(entry_price - stop_price)
        reward = abs(target1_price - entry_price)
        if risk > 0:
            rr = reward / risk
            if rr >= 2.0:
                score += 1.0
                details.append(f"R:R {rr:.1f}:1 ≥1:2 ✓")
            elif rr >= 1.5:
                score += 0.5
                details.append(f"R:R {rr:.1f}:1 <1:2 ⚠")
            else:
                constitution_violations.append(f"R:R {rr:.1f}:1 不合格")
    
    # ATR 止损合理性
    if stop_price and atr_value and entry_price:
        stop_distance = abs(entry_price - stop_price)
        if stop_distance >= 0.5 * atr_value:
            score += 0.75
            details.append(f"止损{stop_distance:.0f}≥0.5×ATR{atr_value:.0f} ✓")
        else:
            details.append(f"止损{stop_distance:.0f}<0.5×ATR{atr_value:.0f} ⚠")
    
    # 仓位检查（融合 trading-scanner 风险宪法）
    if risk_usd and account_balance > 0:
        risk_pct = risk_usd / account_balance
        if risk_pct <= max_risk_pct + 0.001:
            score += 0.5
            details.append(f"仓位 {risk_pct:.1%} ≤ {max_risk_pct:.0%} ✓")
        else:
            constitution_violations.append(f"仓位 {risk_pct:.1%} > {max_risk_pct:.0%} 上限")
    
    # 风险宪法：日回撤
    if daily_drawdown_pct >= 0.05:
        constitution_violations.append(f"日回撤 {daily_drawdown_pct:.1%} ≥ 5% 熔断")
        score -= 1.0
    
    # 风险宪法：连续亏损
    if consecutive_losses >= 3:
        constitution_violations.append(f"连续 {consecutive_losses} 亏损 ≥ 3 暂停")
        score -= 0.75
    
    # 风险宪法：日亏损上限
    if daily_pnl < -account_balance * 0.05:
        constitution_violations.append(f"日亏 ${abs(daily_pnl):.0f} > 5% 熔断")
        score -= 1.0
    
    score = max(0, min(score, 2.5))
    
    return {
        "score": round(score, 1),
        "max": 2.5,
        "details": details,
        "violations": constitution_violations,
        "grade": "A" if score >= 2.0 else "B" if score >= 1.0 else "C",
        "constitution_ok": len(constitution_violations) == 0
    }


def score_sentiment(x_direction: str = "neutral",
                     x_strength: str = "low",
                     cg_sentiment_pct: Optional[float] = None,
                     fear_greed: Optional[int] = None,
                     search_sentiment: str = "neutral") -> dict:
    """
    情绪分：X情绪 + CG社区 + 恐慌贪婪 + 搜索情绪
    
    满分2.0
    - X情绪明确方向 → +0.75
    - CG情绪极端(>70%/<30%) → +0.5
    - 恐慌贪婪极端(<25 或 >75) → +0.5
    - 搜索情绪确认 → +0.25
    """
    score = 0.0
    details = []
    
    if x_direction in ("bullish", "bearish"):
        score += 0.5
        if x_strength in ("high", "medium"):
            score += 0.25
        details.append(f"X情绪: {x_direction}·强度{x_strength}")
    else:
        details.append("X情绪: neutral")
    
    if cg_sentiment_pct is not None:
        if cg_sentiment_pct > 70:
            score += 0.5
            details.append(f"CG极度看多 {cg_sentiment_pct:.0f}%")
        elif cg_sentiment_pct < 30:
            score += 0.5
            details.append(f"CG极度看空 {cg_sentiment_pct:.0f}%")
        else:
            details.append(f"CG中性 {cg_sentiment_pct:.0f}%")
    
    if fear_greed is not None:
        if fear_greed <= 25:
            score += 0.5
            details.append(f"恐慌贪婪 {fear_greed} 极度恐惧·底部信号")
        elif fear_greed >= 75:
            score += 0.5
            details.append(f"恐慌贪婪 {fear_greed} 极度贪婪·顶部信号")
        else:
            details.append(f"恐慌贪婪 {fear_greed}")
    
    if search_sentiment != "neutral":
        score += 0.25
        details.append(f"搜索: {search_sentiment}")
    
    return {
        "score": round(min(score, 2.0), 1),
        "max": 2.0,
        "details": details,
        "grade": "A" if score >= 1.5 else "B" if score >= 0.5 else "C"
    }


def score_setup(symbol: str,
                # 结构
                smc_result: Optional[dict] = None,
                tv_levels: Optional[dict] = None,
                manual_structure: Optional[dict] = None,
                # 订单流
                cvd_value: Optional[float] = None,
                cvd_slope: Optional[float] = None,
                taker_ratio: Optional[float] = None,
                volume_ratio: Optional[float] = None,
                cvd_quality: str = "C",
                # 周期
                tf_consensus: int = 0,
                tf_total: int = 4,
                tf_details: Optional[dict] = None,
                # 催化
                has_fomc: bool = False,
                has_nfp: bool = False,
                has_data_event: bool = False,
                news_sentiment: str = "neutral",
                blackout_active: bool = False,
                # 风控
                entry_price: Optional[float] = None,
                stop_price: Optional[float] = None,
                target1_price: Optional[float] = None,
                atr_value: Optional[float] = None,
                risk_usd: Optional[float] = None,
                account_balance: float = 100.0,
                max_risk_pct: float = 0.03,
                daily_pnl: float = 0.0,
                daily_drawdown_pct: float = 0.0,
                consecutive_losses: int = 0,
                # 情绪
                x_direction: str = "neutral",
                x_strength: str = "low",
                cg_sentiment_pct: Optional[float] = None,
                fear_greed: Optional[int] = None,
                search_sentiment: str = "neutral") -> dict:
    """
    棠溪 · 全维度机器评分 v1.0
    
    Returns:
        {
            "symbol": str,
            "total": float,        # /14
            "max_score": 14.0,
            "grade": str,          # 💎Elite/🥇A+/🥈A/🥉标准/❌不合格
            "breakdown": {         # 逐项明细
                "structure": {...},
                "orderflow": {...},
                "timeframe": {...},
                "catalyst": {...},
                "risk": {...},
                "sentiment": {...}
            },
            "recommendation": str,
            "constitution_violations": [...],
        }
    """
    structure = score_structure(smc_result, tv_levels, manual_structure)
    orderflow = score_orderflow(cvd_value, cvd_slope, taker_ratio, volume_ratio, cvd_quality)
    timeframe = score_timeframe(tf_consensus, tf_total, tf_details)
    catalyst = score_catalyst(has_fomc, has_nfp, has_data_event, news_sentiment, blackout_active)
    risk = score_risk(entry_price, stop_price, target1_price, atr_value, risk_usd,
                       account_balance, max_risk_pct, daily_pnl, daily_drawdown_pct, consecutive_losses)
    sentiment = score_sentiment(x_direction, x_strength, cg_sentiment_pct, fear_greed, search_sentiment)
    
    total = (structure["score"] + orderflow["score"] + timeframe["score"] +
             catalyst["score"] + risk["score"] + sentiment["score"])
    grade = grade_from_score(total)
    
    # 风控宪法违规 → 降级
    violations = risk.get("violations", [])
    if violations and total >= 7:
        grade = f"{grade} ⚠风控违规"
    
    # 推荐操作
    if catalyst.get("blackout_active"):
        recommendation = "X禁做·新闻黑窗期"
    elif not risk.get("constitution_ok", True):
        recommendation = "X禁做·风控宪法违规"
    elif total >= 12:
        recommendation = "A做·全维度确认·Elite级别"
    elif total >= 10:
        recommendation = "A做·高概率·A+级别"
    elif total >= 7:
        recommendation = "B等待·条件就绪·A级别"
    elif total >= 4:
        recommendation = "B等待·信号偏弱·标准级别"
    else:
        recommendation = "X禁做·综合评分不足"
    
    return {
        "symbol": symbol,
        "total": round(total, 1),
        "max_score": MAX_SCORE,
        "grade": grade,
        "breakdown": {
            "structure": structure,
            "orderflow": orderflow,
            "timeframe": timeframe,
            "catalyst": catalyst,
            "risk": risk,
            "sentiment": sentiment,
        },
        "recommendation": recommendation,
        "constitution_violations": violations,
    }


# ═══ CLI ═══
if __name__ == "__main__":
    # Demo: 用当前BTC数据快速评分
    result = score_setup(
        symbol="BTCUSDT",
        # 结构：无SMC，用TV指标
        tv_levels={"S VWAP": 64308, "EMA 9": 64066},
        # 订单流：CVD -469, Taker=0.71, CVD C级
        cvd_value=-469, cvd_slope=-102.5, taker_ratio=0.7073,
        volume_ratio=0.85, cvd_quality="C",
        # 周期：4h↓1h↓15m↓5m→ 3/4一致
        tf_consensus=3, tf_total=4,
        tf_details={"4h":"偏空","1h":"偏空","15m":"偏空","5m":"震荡"},
        # 风控
        entry_price=64050, stop_price=64510, target1_price=63670,
        atr_value=450, risk_usd=3.0, account_balance=67.52,
        # 情绪
        x_direction="bearish", x_strength="medium",
        cg_sentiment_pct=72, fear_greed=15,
        search_sentiment="bearish",
    )
    
    import json as _json
    print(_json.dumps(result, indent=2, ensure_ascii=False))
