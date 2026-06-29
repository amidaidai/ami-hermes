#!/usr/bin/env python3
"""
棠溪 · 实时指标喂料 v1.0
拉真实 K 线 → 算 VWAP/VAH/VAL/POC/EMA/ATR/recent_high/low/CVD →
组装成 five_model_matcher.generate_all_setups 需要的指标 dict。

解决的问题：build_levels_v2 原本从 _MCACHE[symbol]['tv'] 取指标，
但 _LAST/_MCACHE 现在只存方向字符串，没有 tv 字段 → 五模型从不触发 →
监控位永远退化到 price*1.002 硬编码假位。本模块用真实 K 线补齐指标。

用法：
  from indicator_feed import build_indicators
  ind = build_indicators("BTCUSDT")   # 返回 dict 或 None
"""

from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0"

# 复用 backtest_runner 的向量化指标计算
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from backtest_runner import calc_ema, calc_atr, calc_vwap
except Exception:
    calc_ema = calc_atr = calc_vwap = None


def _binance_klines(symbol: str, interval: str = "15m", limit: int = 100) -> list[list]:
    """Binance 公开 K 线（无需签名）。返回 [[open_time, o, h, l, c, vol, ...], ...]"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _gold_klines(interval: str = "15m", limit: int = 100) -> list[list]:
    """黄金用 Yahoo GC=F 期货 K 线代理（现货无K线源）。减 $20 溢价近似现货。
    返回与 Binance 同构的 [[t, o, h, l, c, vol], ...]。"""
    rng_map = {"15m": ("15m", "5d"), "5m": ("5m", "5d"), "1h": ("60m", "1mo")}
    iv, rng = rng_map.get(interval, ("15m", "5d"))
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
           f"?interval={iv}&range={rng}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    res = d["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    PREMIUM = 20.0  # 期货对现货溢价近似
    out = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c):
            continue
        out.append([t * 1000, o - PREMIUM, h - PREMIUM, l - PREMIUM, c - PREMIUM, v or 0])
    return out[-limit:]


def _volume_profile(highs, lows, closes, volumes, bins: int = 24):
    """用成交量分布算 POC/VAH/VAL（70% value area）。"""
    lo, hi = min(lows), max(highs)
    if hi <= lo:
        return closes[-1], closes[-1], closes[-1]
    width = (hi - lo) / bins
    vol_at = [0.0] * bins
    for h, l, c, v in zip(highs, lows, closes, volumes):
        idx = min(bins - 1, max(0, int((c - lo) / width)))
        vol_at[idx] += v
    poc_idx = max(range(bins), key=lambda i: vol_at[i])
    poc = lo + (poc_idx + 0.5) * width
    total = sum(vol_at)
    if total <= 0:
        return poc, hi, lo
    # 从 POC 向两侧扩张到 70% 成交量
    target = total * 0.70
    acc = vol_at[poc_idx]
    lo_i = hi_i = poc_idx
    while acc < target and (lo_i > 0 or hi_i < bins - 1):
        left = vol_at[lo_i - 1] if lo_i > 0 else -1
        right = vol_at[hi_i + 1] if hi_i < bins - 1 else -1
        if right >= left:
            hi_i += 1
            acc += vol_at[hi_i]
        else:
            lo_i -= 1
            acc += vol_at[lo_i]
    vah = lo + (hi_i + 1) * width
    val = lo + lo_i * width
    return poc, vah, val


def build_indicators(symbol: str, interval: str = "15m") -> dict | None:
    """拉真实 K 线 → 全套指标 dict，供 five_model_matcher 使用。失败返回 None。"""
    if calc_ema is None:
        return None
    try:
        if "XAU" in symbol.upper():
            kl = _gold_klines(interval, 100)
        else:
            kl = _binance_klines(symbol, interval, 100)
        if not kl or len(kl) < 30:
            return None
        opens = [float(k[1]) for k in kl]
        highs = [float(k[2]) for k in kl]
        lows = [float(k[3]) for k in kl]
        closes = [float(k[4]) for k in kl]
        vols = [float(k[5]) for k in kl]
        price = closes[-1]

        vwap_series = calc_vwap(highs, lows, closes, vols)
        atr_series = calc_atr(highs, lows, closes, 14)
        ema9_series = calc_ema(closes, 9)
        ema21_series = calc_ema(closes, 21)
        vwap = vwap_series[-1]
        atr = atr_series[-1]
        ema9 = ema9_series[-1]
        ema21 = ema21_series[-1]
        poc, vah, val = _volume_profile(highs, lows, closes, vols)
        recent_high = max(highs[-50:])
        recent_low = min(lows[-50:])

        # CVD 近似：用每根K线方向×成交量累加（收>开记买，收<开记卖）
        cvd = 0.0
        cvd_pts = []
        for o, c, v in zip(opens, closes, vols):
            cvd += v if c >= o else -v
            cvd_pts.append(cvd)
        cvd_slope = (cvd_pts[-1] - cvd_pts[-6]) / 5 if len(cvd_pts) >= 6 else 0.0

        return {
            "price": price,
            "S VWAP": vwap,
            "S VWAP -Band1": vwap - atr,
            "S VWAP -Band2": vwap - 2 * atr,
            "VAH Price": vah,
            "VAL Price": val,
            "POC Price": poc,
            "EMA 9": ema9,
            "EMA 21": ema21,
            "recent_high": recent_high,
            "recent_low": recent_low,
            "atr": atr,
            "CVD Value": cvd_pts[-1],
            "CVD Slope": cvd_slope,
            "_source": "binance_klines" if "XAU" not in symbol.upper() else "yahoo_gc_proxy",
        }
    except Exception:
        return None


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    ind = build_indicators(sym)
    print(json.dumps(ind, indent=2, ensure_ascii=False, default=str))
