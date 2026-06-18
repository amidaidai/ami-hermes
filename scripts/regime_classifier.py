#!/usr/bin/env python3
"""
棠溪 · 市场体制分类器 v1.0（自贸实现，不依赖外部MCP）
融合: regime-mcp-server (shadowfax-mitch) 方法论 + 棠溪现有VIX/宏观数据

输出: 博弈段③ 市场体制行 + 交易建议

体制分类:
  - LOW_VOL_BULL:   低波上涨 → 卖Put·theta衰减
  - LOW_VOL_BEAR:   低波下跌 → 买Put·方向博弈
  - HIGH_VOL_BULL:  高波上涨 → 追趋势·宽止损
  - HIGH_VOL_BEAR:  高波下跌 → 卖Call·or 观望
  - LOW_VOL_NEUTRAL:低波震荡 → 卖跨式·theta收割
  - HIGH_VOL_NEUTRAL:高波震荡 → 宽跨式·买波动
"""

from dataclasses import dataclass
from typing import Optional
import json


@dataclass
class Regime:
    name: str
    vix_level: str            # LOW/NORMAL/HIGH/EXTREME
    volatility_percentile: float  # 0-100
    trend: str                # bull/bear/neutral
    description: str
    trading_implications: list[str]
    risk_level: str           # low/medium/high/extreme


def classify_vix(vix: float) -> str:
    """VIX分级"""
    if vix < 15:
        return "LOW"
    elif vix < 20:
        return "NORMAL"
    elif vix < 30:
        return "HIGH"
    else:
        return "EXTREME"


def classify_regime(vix: Optional[float] = None,
                     spy_change_pct: float = 0.0,
                     dxy_change_pct: float = 0.0,
                     us10y: Optional[float] = None,
                     fear_greed: Optional[int] = None,
                     btc_change_24h_pct: float = 0.0,
                     btc_volatility_20d_pct: float = 2.5,
                     gold_change_pct: float = 0.0) -> Regime:
    """
    市场体制分类
    
    输入: VIX, SPY, DXY, US10Y, F&G, BTC波动率
    输出: Regime 对象
    """
    
    # VIX分级
    vix_level = classify_vix(vix) if vix else "NORMAL"
    
    # 趋势判定（多资产聚合）
    trend_signals = []
    if spy_change_pct > 0.5:
        trend_signals.append("bull")
    elif spy_change_pct < -0.5:
        trend_signals.append("bear")
    else:
        trend_signals.append("neutral")
    
    if btc_change_24h_pct > 2.0:
        trend_signals.append("bull")
    elif btc_change_24h_pct < -2.0:
        trend_signals.append("bear")
    
    if gold_change_pct > 1.0:
        trend_signals.append("bear")  # 金涨=避险
    elif gold_change_pct < -1.0:
        trend_signals.append("bull")  # 金跌=风险偏好
    
    # 投票
    bull_count = trend_signals.count("bull")
    bear_count = trend_signals.count("bear")
    
    if bull_count > bear_count:
        trend = "bull"
    elif bear_count > bull_count:
        trend = "bear"
    else:
        trend = "neutral"
    
    # 波动率分位数
    vol_pct = min(100, max(0, (btc_volatility_20d_pct / 5.0) * 100))
    
    # 体制分类
    if vix_level in ("LOW", "NORMAL") and trend == "bull":
        regime_name = "LOW_VOL_BULL"
        description = "低波上涨·牛市中继"
        implications = [
            "卖Put收取权利金·theta衰减有利",
            "回调买·不追高",
            "趋势仓位持有·不加杠杆",
        ]
        risk_level = "low"
    elif vix_level in ("LOW", "NORMAL") and trend == "bear":
        regime_name = "LOW_VOL_BEAR"
        description = "低波阴跌·慢熊"
        implications = [
            "轻仓·等放量反弹确认",
            "不做逆势多",
            "买Put博弈加速下跌",
        ]
        risk_level = "medium"
    elif vix_level in ("HIGH", "EXTREME") and trend == "bull":
        regime_name = "HIGH_VOL_BULL"
        description = "高波急涨·情绪驱动"
        implications = [
            "追趋势·宽止损(≥1.5×ATR)",
            "分批建仓·防假突破",
            "R:R需≥1:3补偿高波动",
        ]
        risk_level = "high"
    elif vix_level in ("HIGH", "EXTREME") and trend == "bear":
        regime_name = "HIGH_VOL_BEAR"
        description = "高波急跌·恐慌抛售"
        implications = [
            "观望优先·等VIX回落",
            "若做空·用卖Call而非裸空",
            "注意轧空风险·设硬止损",
        ]
        risk_level = "extreme"
    elif vix_level in ("LOW", "NORMAL") and trend == "neutral":
        regime_name = "LOW_VOL_NEUTRAL"
        description = "低波震荡·方向不明"
        implications = [
            "卖跨式/宽跨式·theta收割最优",
            "不做方向性交易",
            "等突破确认后再入场",
        ]
        risk_level = "low"
    else:  # HIGH_VOL_NEUTRAL
        regime_name = "HIGH_VOL_NEUTRAL"
        description = "高波震荡·方向未定"
        implications = [
            "买跨式·博弈波动突破",
            "不做卖权·gamma风险大",
            "等VIX回落再建仓",
        ]
        risk_level = "high"
    
    # 恐慌贪婪极端修正
    if fear_greed and fear_greed <= 20 and regime_name in ("LOW_VOL_BEAR", "HIGH_VOL_BEAR"):
        implications.insert(0, "⚠ 恐慌贪婪极度恐惧·底部博弈·可能反转")
        risk_level = "extreme"
    elif fear_greed and fear_greed >= 80 and regime_name in ("LOW_VOL_BULL", "HIGH_VOL_BULL"):
        implications.insert(0, "⚠ 恐慌贪婪极度贪婪·顶部预警·减仓")
        risk_level = "high"
    
    return Regime(
        name=regime_name,
        vix_level=vix_level,
        volatility_percentile=round(vol_pct, 1),
        trend=trend,
        description=description,
        trading_implications=implications,
        risk_level=risk_level,
    )


def regime_card_line(regime: Regime) -> str:
    """生成分析卡博弈段③ 市场体制行"""
    emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "extreme": "🔴"}[regime.risk_level]
    return f"{emoji} 市场体制：{regime.name} — {regime.description}"


def regime_detail_text(regime: Regime) -> str:
    """生成博弈段体制详情"""
    lines = [
        f"市场体制：{regime.name}（{regime.description}）",
        f"VIX：{regime.vix_level} · 波动率分位：{regime.volatility_percentile:.0f}%",
        f"风险等级：{regime.risk_level.upper()}",
        f"交易建议：",
    ]
    for imp in regime.trading_implications:
        lines.append(f"  — {imp}")
    return "\n".join(lines)


# ═══ CLI ═══
if __name__ == "__main__":
    # Demo: 当前市场体制
    regime = classify_regime(
        vix=18.5,
        spy_change_pct=-0.3,
        dxy_change_pct=0.0,
        us10y=4.25,
        fear_greed=15,
        btc_change_24h_pct=-2.9,
        btc_volatility_20d_pct=3.8,
        gold_change_pct=-0.04,
    )
    
    print("═" * 40)
    print(regime_card_line(regime))
    print("═" * 40)
    print(regime_detail_text(regime))
    print()
    print(json.dumps(regime.__dict__, indent=2, ensure_ascii=False))
