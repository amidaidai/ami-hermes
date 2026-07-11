#!/usr/bin/env python3
"""从真实闭柱OHLCV与TV结构位构建统一体制特征。"""
from __future__ import annotations

from typing import Any

from regime_backtest import _adx, _ema


def _array(data: dict[str, Any], plural: str, singular: str) -> list[float]:
    raw = data.get(plural) or data.get(singular) or []
    try:
        return [float(v) for v in raw]
    except (TypeError, ValueError):
        return []


def _f(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ohlcv_from_binance_klines(rows: list[Any], *, drop_open_bar: bool = True) -> dict[str, list[float]]:
    """把Binance K线数组转成统一OHLCV；默认移除最后一根尚未闭合K线。"""
    usable = list(rows or [])
    if drop_open_bar and usable:
        usable = usable[:-1]
    parsed = {"opens": [], "highs": [], "lows": [], "closes": [], "volumes": []}
    for row in usable:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            continue
        try:
            parsed["opens"].append(float(row[1]))
            parsed["highs"].append(float(row[2]))
            parsed["lows"].append(float(row[3]))
            parsed["closes"].append(float(row[4]))
            parsed["volumes"].append(float(row[5]))
        except (TypeError, ValueError):
            continue
    return parsed


def build_regime_features(ohlcv: dict[str, Any], tv_main: dict[str, Any] | None = None) -> dict[str, float | int | None] | None:
    """构建体制分类器特征；历史不足50根时返回None，禁止用演示值填充。"""
    tv_main = tv_main or {}
    opens = _array(ohlcv, "opens", "open")
    highs = _array(ohlcv, "highs", "high")
    lows = _array(ohlcv, "lows", "low")
    closes = _array(ohlcv, "closes", "close")
    volumes = _array(ohlcv, "volumes", "volume")
    n = min(len(opens), len(highs), len(lows), len(closes), len(volumes))
    if n < 50:
        return None
    opens, highs, lows, closes, volumes = (x[-n:] for x in (opens, highs, lows, closes, volumes))

    true_ranges: list[float] = []
    for i in range(n):
        prev = closes[i - 1] if i else closes[i]
        true_ranges.append(max(highs[i] - lows[i], abs(highs[i] - prev), abs(lows[i] - prev)))
    atr14 = sum(true_ranges[-14:]) / 14
    atr_series: list[float] = []
    for i in range(13, n):
        atr_series.append(sum(true_ranges[i - 13:i + 1]) / 14)
    atr_avg50 = sum(atr_series[-50:]) / min(50, len(atr_series)) if atr_series else 0.0
    atr_ratio = atr14 / atr_avg50 if atr_avg50 > 0 else 1.0

    ema21 = _ema(closes, 21)
    ema55 = _ema(closes, 55)
    ema_spread_atr = abs(ema21[-1] - ema55[-1]) / atr14 if atr14 > 0 else 0.0
    adx_series = _adx(highs, lows, closes, 14)
    adx = adx_series[-1] if adx_series else 0.0

    vol20 = sum(volumes[-20:]) / 20
    rvol = volumes[-1] / vol20 if vol20 > 0 else 0.0
    displacement_atr = abs(closes[-1] - opens[-1]) / atr14 if atr14 > 0 else 0.0

    tv_vwap = _f(tv_main.get("vwap"))
    if tv_vwap is None:
        pv = sum(((highs[i] + lows[i] + closes[i]) / 3) * volumes[i] for i in range(n - 20, n))
        vv = sum(volumes[-20:])
        tv_vwap = pv / vv if vv > 0 else closes[-1]
    crosses = 0
    prev_side = 0
    for close in closes[-20:]:
        side = 1 if close > tv_vwap else -1 if close < tv_vwap else 0
        if prev_side and side and side != prev_side:
            crosses += 1
        if side:
            prev_side = side

    vah = _f(tv_main.get("vah"))
    val = _f(tv_main.get("val"))
    if vah is not None and val is not None and vah >= val:
        va_stay = sum(1 for close in closes[-20:] if val <= close <= vah) / 20
    else:
        va_stay = 0.0

    vwap_distance = (closes[-1] - tv_vwap) / atr14 if atr14 > 0 and tv_vwap is not None else None
    return {
        "adx": round(adx, 4),
        "atr": round(atr14, 8),
        "atr_ratio": round(atr_ratio, 4),
        "ema_spread_atr": round(ema_spread_atr, 4),
        "vwap_crosses_20": crosses,
        "va_stay_ratio_20": round(va_stay, 4),
        "displacement_atr": round(displacement_atr, 4),
        "rvol": round(rvol, 4),
        "adr_remaining_ratio": _f(tv_main.get("adr_remaining_ratio")),
        "vwap_distance_atr": round(vwap_distance, 4) if vwap_distance is not None else None,
    }
