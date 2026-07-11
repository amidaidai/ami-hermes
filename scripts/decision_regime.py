#!/usr/bin/env python3
"""棠溪实时执行体制分类器。

只使用当前交易品种的结构/波动/成交特征，不依赖固定VIX演示值。
体制负责选择模型，不负责决定多空方向。
"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class DecisionRegime:
    code: str
    name: str
    allowed_models: tuple[str, ...]
    blocked_models: tuple[str, ...]
    position_multiplier: float  # 风险除数：越大仓位越小；0表示禁做
    exhausted: bool = False
    reason: str = ""


def classify_decision_regime(
    *,
    adx: float,
    atr_ratio: float,
    ema_spread_atr: float,
    vwap_crosses_20: int,
    va_stay_ratio_20: float,
    displacement_atr: float,
    rvol: float,
    adr_remaining_ratio: float | None = None,
    vwap_distance_atr: float | None = None,
) -> DecisionRegime:
    """把闭柱特征分类为趋势/平衡/收敛/扩张，耗尽作为风险叠加位。"""
    # 扩张优先于趋势：它决定“等首次回踩”，而不是追当前位移。
    if atr_ratio >= 1.30 and displacement_atr >= 1.0 and rvol >= 1.2:
        result = DecisionRegime(
            code="expansion",
            name="扩张",
            allowed_models=("fvg_pullback", "ob_pullback", "breakout_acceptance"),
            blocked_models=("direct_chase", "value_rotation", "countertrend_mean_reversion"),
            position_multiplier=2.0,
            reason="ATR扩张+位移+RVOL确认，只做首次回踩",
        )
    elif atr_ratio < 0.75 and ema_spread_atr < 0.25:
        result = DecisionRegime(
            code="compression",
            name="收敛",
            allowed_models=("breakout_acceptance",),
            blocked_models=("direct_chase", "fvg_pullback", "ob_pullback", "value_rotation"),
            position_multiplier=1.5,
            reason="ATR收缩且EMA收拢，等待位移后接受",
        )
    elif adx >= 25 and ema_spread_atr >= 0.45 and vwap_crosses_20 <= 3:
        result = DecisionRegime(
            code="trend",
            name="趋势",
            allowed_models=("vwap_pullback", "fvg_pullback", "ob_pullback", "breakout_acceptance"),
            blocked_models=("countertrend_mean_reversion",),
            position_multiplier=1.0,
            reason="ADX与EMA扩张确认，VWAP单侧接受",
        )
    else:
        strong_balance = adx < 20 and vwap_crosses_20 >= 4 and va_stay_ratio_20 >= 0.60
        result = DecisionRegime(
            code="balance",
            name="平衡" if strong_balance else "平衡待确认",
            allowed_models=("value_rotation", "poc_rejection", "vwap_mean_reversion"),
            blocked_models=("direct_chase", "breakout_acceptance"),
            position_multiplier=1.25 if strong_balance else 1.5,
            reason="ADX偏低且价格在价值区/VWAP两侧轮转" if strong_balance else "结构未形成稳定趋势，按平衡降级",
        )

    exhausted = (
        adr_remaining_ratio is not None and adr_remaining_ratio <= 0.15
    ) or (
        vwap_distance_atr is not None and abs(vwap_distance_atr) >= 2.5
    )
    if exhausted:
        result = replace(
            result,
            exhausted=True,
            position_multiplier=round(result.position_multiplier * 1.5, 3),
            reason=result.reason + "；ADR耗尽或偏离VWAP过远，禁止追价",
        )
    return result
