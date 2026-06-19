#!/usr/bin/env python3
"""
棠溪 · CVD高级分析模块 v1.0
借鉴: Bookmap CVD Trading Strategy + Reddit r/algotrading社区共识

功能:
    1. CVD Divergence — 价格新高+CVD新低=反转预警（Bookmap高价值建议）
    2. CVD Exhaustion — CVD激增但价格停滞=燃料耗尽
    3. CVD Absorption — CVD降但价格持稳=被动买盘吸收
    4. CVD+VWAP Confluence — CVD方向与VWAP位置共振确认

数据需求:
    - Binance K线 (OHLCV + taker_buy_volume)
    - 或预计算的CVD序列

用法:
    from cvd_analyzer import CVDAnalyzer
    analyzer = CVDAnalyzer()
    result = analyzer.analyze(closes, highs, lows, volumes, taker_buy_vols)
    # result = {"divergence": {...}, "exhaustion": {...}, "absorption": {...}}
"""

from __future__ import annotations
import requests
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class SignalType(Enum):
    """CVD信号类型"""
    BULLISH_DIVERGENCE = "看涨背离"    # 价格新低+CVD走高
    BEARISH_DIVERGENCE = "看跌背离"    # 价格新高+CVD走低
    EXHAUSTION_BUY = "买方耗尽"        # CVD大增但价格不上
    EXHAUSTION_SELL = "卖方耗尽"       # CVD大降但价格不下
    ABSORPTION_BULLISH = "看涨吸收"    # CVD降但价格持稳于支撑
    ABSORPTION_BEARISH = "看跌吸收"    # CVD升但价格持稳于阻力
    NONE = "无信号"


@dataclass
class CVDResult:
    """CVD分析结果"""
    signal: SignalType = SignalType.NONE
    confidence: float = 0.0          # 0.0-1.0
    cvd_value: float = 0.0
    cvd_slope: float = 0.0           # 近期CVD斜率
    price_trend: str = "中性"        # 上涨/下跌/横盘
    cvd_trend: str = "中性"          # 上升/下降/横盘
    description: str = ""
    raw_cvd: list[float] = field(default_factory=list)


class CVDAnalyzer:
    """
    CVD高级分析器

    检测三种关键模式:
    1. Divergence: 价格与CVD趋势不一致 → 反转预警
    2. Exhaustion: CVD激增但价格停滞 → 动能耗尽
    3. Absorption: CVD单边但价格持稳 → 被动吸收
    """

    def __init__(self, lookback: int = 20, divergence_window: int = 10):
        self.lookback = lookback              # CVD计算回看窗口
        self.divergence_window = divergence_window  # 背离检测窗口
        # 阈值
        self.price_stall_threshold = 0.002    # 价格停滞阈值 (0.2%)
        self.cvd_spike_threshold = 2.0        # CVD激增倍数 (vs 均值)
        self.absorption_hold_threshold = 0.003  # 吸收持稳阈值 (0.3%)

    def compute_cvd_series(
        self,
        volumes: list[float],
        taker_buy_vols: list[float],
    ) -> list[float]:
        """
        从taker买卖量计算CVD序列

        CVD = Σ(taker_buy_volume - taker_sell_volume)
        taker_sell_volume = total_volume - taker_buy_volume
        """
        cvd = []
        running = 0.0
        for i in range(len(volumes)):
            sell_vol = volumes[i] - taker_buy_vols[i]
            running += taker_buy_vols[i] - sell_vol
            cvd.append(running)
        return cvd

    def compute_cvd_from_klines(self, symbol: str, interval: str = "1m", limit: int = 50) -> CVDResult:
        """
        从Binance K线API实时计算CVD

        Args:
            symbol: 交易对 (BTCUSDT)
            interval: K线周期
            limit: K线数量
        """
        try:
            r = requests.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=5,
            )
            r.raise_for_status()
            klines = r.json()

            closes = [float(k[4]) for k in klines]
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            volumes = [float(k[5]) for k in klines]
            taker_buy_vols = [float(k[9]) for k in klines]

            return self.analyze(closes, highs, lows, volumes, taker_buy_vols)
        except Exception as e:
            return CVDResult(description=f"CVD获取失败: {e}")

    def analyze(
        self,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        volumes: list[float],
        taker_buy_vols: list[float],
    ) -> CVDResult:
        """
        完整CVD分析 — 检测divergence/exhaustion/absorption

        Returns:
            CVDResult with signal, confidence, trends
        """
        n = len(closes)
        if n < self.lookback:
            return CVDResult(description=f"数据不足: {n} < {self.lookback}")

        # 计算CVD序列
        cvd = self.compute_cvd_series(volumes, taker_buy_vols)

        # 取最近窗口
        window = min(self.divergence_window, n)
        recent_closes = closes[-window:]
        recent_highs = highs[-window:]
        recent_lows = lows[-window:]
        recent_cvd = cvd[-window:]

        # 趋势判断
        price_trend = self._trend(recent_closes)
        cvd_trend = self._trend(recent_cvd)
        cvd_slope = (recent_cvd[-1] - recent_cvd[0]) / window if window > 0 else 0

        result = CVDResult(
            cvd_value=cvd[-1],
            cvd_slope=cvd_slope,
            price_trend=price_trend,
            cvd_trend=cvd_trend,
            raw_cvd=cvd[-window:],
        )

        # ① 检测Divergence
        div_signal, div_conf, div_desc = self._check_divergence(
            recent_closes, recent_highs, recent_lows, recent_cvd
        )

        # ② 检测Exhaustion
        exh_signal, exh_conf, exh_desc = self._check_exhaustion(
            recent_closes, recent_cvd, volumes[-window:]
        )

        # ③ 检测Absorption
        abs_signal, abs_conf, abs_desc = self._check_absorption(
            recent_closes, recent_highs, recent_lows, recent_cvd
        )

        # 取最高置信度信号
        signals = [
            (div_signal, div_conf, div_desc),
            (exh_signal, exh_conf, exh_desc),
            (abs_signal, abs_conf, abs_desc),
        ]
        best = max(signals, key=lambda x: x[1])
        result.signal = best[0]
        result.confidence = best[1]
        result.description = best[2]

        return result

    def _trend(self, values: list[float]) -> str:
        """判断趋势方向"""
        if len(values) < 3:
            return "中性"
        first_half = sum(values[:len(values) // 2]) / (len(values) // 2)
        second_half = sum(values[len(values) // 2:]) / (len(values) - len(values) // 2)
        change_pct = (second_half - first_half) / abs(first_half) if first_half != 0 else 0
        if change_pct > 0.01:
            return "上升"
        elif change_pct < -0.01:
            return "下降"
        return "横盘"

    def _check_divergence(
        self,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        cvd: list[float],
    ) -> tuple[SignalType, float, str]:
        """
        CVD背离检测（Bookmap核心建议）

        看跌背离: 价格创新高 + CVD走低
        看涨背离: 价格创新低 + CVD走高
        """
        n = len(closes)
        if n < 5:
            return SignalType.NONE, 0.0, ""

        # 找前半段和后半段的极值
        mid = n // 2
        price_high1 = max(highs[:mid]) if mid > 0 else highs[0]
        price_high2 = max(highs[mid:])
        price_low1 = min(lows[:mid]) if mid > 0 else lows[0]
        price_low2 = min(lows[mid:])
        cvd_at_mid = cvd[mid] if mid < len(cvd) else cvd[-1]
        cvd_now = cvd[-1]

        # 看跌背离: 价格新高 + CVD走低
        if price_high2 > price_high1 and cvd_now < cvd_at_mid:
            strength = min(1.0, (price_high2 - price_high1) / price_high1 * 100)
            conf = 0.6 + strength * 0.3
            return (SignalType.BEARISH_DIVERGENCE, conf,
                    f"看跌背离: 价格新高{price_high2:.0f}>{price_high1:.0f} 但CVD走低{cvd_now:.0f}<{cvd_at_mid:.0f}")

        # 看涨背离: 价格新低 + CVD走高
        if price_low2 < price_low1 and cvd_now > cvd_at_mid:
            strength = min(1.0, (price_low1 - price_low2) / price_low1 * 100)
            conf = 0.6 + strength * 0.3
            return (SignalType.BULLISH_DIVERGENCE, conf,
                    f"看涨背离: 价格新低{price_low2:.0f}<{price_low1:.0f} 但CVD走高{cvd_now:.0f}>{cvd_at_mid:.0f}")

        return SignalType.NONE, 0.0, ""

    def _check_exhaustion(
        self,
        closes: list[float],
        cvd: list[float],
        volumes: list[float],
    ) -> tuple[SignalType, float, str]:
        """
        CVD耗尽检测

        买方耗尽: CVD大幅激增 但价格几乎不动
        卖方耗尽: CVD大幅下降 但价格几乎不动
        """
        n = len(closes)
        if n < 5:
            return SignalType.NONE, 0.0, ""

        # 最近几根K线的CVD delta
        recent_deltas = [cvd[i] - cvd[i-1] for i in range(max(1, n-5), n)]
        avg_delta = sum(abs(d) for d in recent_deltas) / len(recent_deltas) if recent_deltas else 0
        last_delta = recent_deltas[-1] if recent_deltas else 0

        # 价格变动
        price_change_pct = abs(closes[-1] - closes[-5]) / closes[-5] if n >= 5 and closes[-5] > 0 else 0

        # CVD激增但价格不动
        if avg_delta > 0 and abs(last_delta) > avg_delta * self.cvd_spike_threshold:
            if price_change_pct < self.price_stall_threshold:
                if last_delta > 0:
                    conf = min(0.9, abs(last_delta) / (avg_delta + 1) * 0.15)
                    return (SignalType.EXHAUSTION_BUY, conf,
                            f"买方耗尽: CVD激增{last_delta:.0f}>{avg_delta:.0f}×{self.cvd_spike_threshold} 但价格仅动{price_change_pct:.2%}")
                else:
                    conf = min(0.9, abs(last_delta) / (avg_delta + 1) * 0.15)
                    return (SignalType.EXHAUSTION_SELL, conf,
                            f"卖方耗尽: CVD骤降{last_delta:.0f} 但价格仅动{price_change_pct:.2%}")

        return SignalType.NONE, 0.0, ""

    def _check_absorption(
        self,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        cvd: list[float],
    ) -> tuple[SignalType, float, str]:
        """
        CVD吸收检测

        看涨吸收: CVD持续下降(卖压) 但价格在支撑位持稳 → 被动买盘吸收
        看跌吸收: CVD持续上升(买压) 但价格在阻力位持稳 → 被动卖盘吸收
        """
        n = len(closes)
        if n < 5:
            return SignalType.NONE, 0.0, ""

        cvd_slope = (cvd[-1] - cvd[-5]) / 5 if n >= 5 else 0
        price_range_pct = (max(highs[-5:]) - min(lows[-5:])) / closes[-1] if closes[-1] > 0 else 0

        # CVD下降但价格持稳 → 看涨吸收
        if cvd_slope < -0.01 * abs(cvd[-1]) and price_range_pct < self.absorption_hold_threshold:
            conf = min(0.8, abs(cvd_slope) / (abs(cvd[-1]) + 1) * 50)
            return (SignalType.ABSORPTION_BULLISH, conf,
                    f"看涨吸收: CVD下降{slope_pct(cvd_slope):.1%} 但价格持稳{price_range_pct:.2%}")

        # CVD上升但价格持稳 → 看跌吸收
        if cvd_slope > 0.01 * abs(cvd[-1]) and price_range_pct < self.absorption_hold_threshold:
            conf = min(0.8, abs(cvd_slope) / (abs(cvd[-1]) + 1) * 50)
            return (SignalType.ABSORPTION_BEARISH, conf,
                    f"看跌吸收: CVD上升{slope_pct(cvd_slope):.1%} 但价格持稳{price_range_pct:.2%}")

        return SignalType.NONE, 0.0, ""


def slope_pct(slope: float) -> float:
    """斜率转百分比"""
    if slope == 0:
        return 0.0
    return slope


def check_cvd_confluence(cvd_result: CVDResult, vwap: float, price: float) -> dict:
    """
    CVD+VWAP共振检测（Bookmap建议: CVD是确认层）

    Returns:
        {"confluence": bool, "direction": str, "confidence": float, "reason": str}
    """
    confluence = False
    direction = "中性"
    confidence = 0.0
    reasons = []

    # 价格在VWAP上方 + CVD看涨 → 多头共振
    if price > vwap and cvd_result.cvd_trend in ("上升", "横盘") and cvd_result.cvd_slope > 0:
        confluence = True
        direction = "多"
        confidence = 0.7
        reasons.append("价格在VWAP上方+CVD上升")

    # 价格在VWAP下方 + CVD看跌 → 空头共振
    elif price < vwap and cvd_result.cvd_trend in ("下降",) and cvd_result.cvd_slope < 0:
        confluence = True
        direction = "空"
        confidence = 0.7
        reasons.append("价格在VWAP下方+CVD下降")

    # 背离信号增强
    if cvd_result.signal != SignalType.NONE and cvd_result.confidence > 0.5:
        confidence = max(confidence, cvd_result.confidence)
        reasons.append(f"CVD{cvd_result.signal.value}@{cvd_result.confidence:.0%}")

    return {
        "confluence": confluence,
        "direction": direction,
        "confidence": round(confidence, 2),
        "reason": "; ".join(reasons) if reasons else "无共振",
        "cvd_signal": cvd_result.signal.value,
        "cvd_confidence": round(cvd_result.confidence, 2),
    }
