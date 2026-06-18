#!/usr/bin/env python3
"""
棠溪 · 分市态回测分栏 v1.0 (2026-06-19)

解决的问题:
  VWAP反抽在31天单边趋势中胜率94%是趋势送的,不是策略真实期望。
  换震荡月会翻车。混合胜率不能用于仓位计算。

做法:
  消费 backtest_runner.BacktestResult.trades + 原始K线,
  按每笔入场时刻的市态(趋势/震荡)归类,分栏统计期望值。
  市态判定: ADX>=25 且 EMA20斜率明确 -> 趋势; 否则 -> 震荡。

铁律:
  分市态期望值用于判断策略真实边际。趋势栏高胜率不可外推到震荡。
  任何一栏样本<10笔 -> 标注"样本不足·仅供参考",不用于权重调整。
"""
from __future__ import annotations
import sys, json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

import numpy as np

ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))

MIN_SAMPLE = 10  # 单栏最小样本,低于此不用于权重调整


def _ema(vals: list[float], period: int) -> list[float]:
    if not vals:
        return []
    k = 2.0 / (period + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
    """Wilder ADX. 返回与输入等长(前 period*2 为 NaN-ish 0)."""
    n = len(closes)
    if n < period * 2 + 1:
        return [0.0] * n
    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        plus_dm[i] = up if (up > dn and up > 0) else 0.0
        minus_dm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]))

    def wilder(arr):
        out = [0.0] * n
        s = sum(arr[1:period + 1])
        out[period] = s
        for i in range(period + 1, n):
            out[i] = out[i - 1] - (out[i - 1] / period) + arr[i]
        return out

    atr = wilder(tr)
    pdm = wilder(plus_dm)
    mdm = wilder(minus_dm)
    adx = [0.0] * n
    dx = [0.0] * n
    for i in range(period, n):
        if atr[i] == 0:
            continue
        pdi = 100 * pdm[i] / atr[i]
        mdi = 100 * mdm[i] / atr[i]
        denom = pdi + mdi
        dx[i] = 100 * abs(pdi - mdi) / denom if denom else 0.0
    # ADX = smoothed DX
    start = period * 2
    if start < n:
        adx[start] = sum(dx[period:start]) / period if period else 0.0
        for i in range(start + 1, n):
            adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
    return adx


def classify_regime(closes, highs, lows, idx, *, adx_trend=25.0, slope_lookback=20) -> str:
    """
    判定 idx 时刻的市态: 'trend' / 'range'.
    趋势: ADX>=25 且 EMA20斜率方向明确(|斜率%|>0.05%/bar)
    其余: range
    """
    if idx < 30 or idx >= len(closes):
        return "range"
    adx_series = _adx(highs[:idx + 1], lows[:idx + 1], closes[:idx + 1])
    adx_now = adx_series[idx] if idx < len(adx_series) else 0.0
    ema = _ema(closes[:idx + 1], 20)
    if len(ema) <= slope_lookback:
        return "range"
    slope_pct = (ema[-1] - ema[-slope_lookback]) / ema[-slope_lookback] / slope_lookback * 100
    if adx_now >= adx_trend and abs(slope_pct) > 0.05:
        return "trend"
    return "range"


@dataclass
class RegimeStats:
    regime: str
    n: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_r: float = 0.0
    avg_r: float = 0.0          # 期望值(每笔平均R)
    profit_factor: float = 0.0
    by_model: dict = field(default_factory=dict)
    reliable: bool = False      # 样本>=MIN_SAMPLE
    note: str = ""


def _ts_to_index(trades, timestamps):
    """把每笔 trade.entry_time(ISO) 映射到最近的 K线 index."""
    if not timestamps:
        return {}
    # timestamps 可能是 ms 或 ISO; 统一成 epoch 秒
    def to_epoch(t):
        if isinstance(t, (int, float)):
            return float(t) / 1000 if t > 1e12 else float(t)
        try:
            return datetime.fromisoformat(str(t).replace("Z", "+00:00")).timestamp()
        except Exception:
            return None
    ks = [to_epoch(t) for t in timestamps]
    out = {}
    for ti, tr in enumerate(trades):
        te = to_epoch(getattr(tr, "entry_time", None))
        if te is None:
            continue
        # 最近 index
        best, bestd = None, 1e18
        for i, kt in enumerate(ks):
            if kt is None:
                continue
            d = abs(kt - te)
            if d < bestd:
                best, bestd = i, d
        if best is not None:
            out[ti] = best
    return out


def split_by_regime(result, closes, highs, lows, timestamps, **kw) -> dict[str, RegimeStats]:
    """
    主入口。返回 {'trend': RegimeStats, 'range': RegimeStats}.
    result: backtest_runner.BacktestResult
    """
    trades = [t for t in result.trades if getattr(t, "result", "open") in ("win", "loss", "breakeven")]
    idx_map = _ts_to_index(trades, timestamps)

    buckets = {"trend": [], "range": []}
    for ti, tr in enumerate(trades):
        idx = idx_map.get(ti)
        reg = classify_regime(closes, highs, lows, idx, **kw) if idx is not None else "range"
        buckets[reg].append(tr)

    out = {}
    for reg, tl in buckets.items():
        st = RegimeStats(regime=reg, n=len(tl))
        if tl:
            st.wins = sum(1 for t in tl if t.result == "win")
            st.losses = sum(1 for t in tl if t.result == "loss")
            st.win_rate = round(100 * st.wins / len(tl), 1)
            st.total_r = round(sum(t.pnl_r for t in tl), 2)
            st.avg_r = round(st.total_r / len(tl), 3)
            gains = sum(t.pnl_r for t in tl if t.pnl_r > 0)
            pains = abs(sum(t.pnl_r for t in tl if t.pnl_r < 0))
            st.profit_factor = round(gains / pains, 2) if pains else 0.0
            # 按模型再分
            bm = {}
            for t in tl:
                m = bm.setdefault(t.model, {"n": 0, "w": 0, "r": 0.0})
                m["n"] += 1
                m["w"] += 1 if t.result == "win" else 0
                m["r"] += t.pnl_r
            for m, d in bm.items():
                d["win_rate"] = round(100 * d["w"] / d["n"], 1)
                d["avg_r"] = round(d["r"] / d["n"], 3)
            st.by_model = bm
        st.reliable = st.n >= MIN_SAMPLE
        st.note = "稳健样本" if st.reliable else f"样本不足({st.n}<{MIN_SAMPLE})·仅供参考·不用于权重调整"
        out[reg] = st
    return out


def format_regime_report(split: dict, symbol: str = "") -> str:
    """纯纵向·无表格·棠溪卡片风格."""
    lines = [f"分市态回测分栏 — {symbol}".rstrip(" —"), ""]
    order = ["trend", "range"]
    cn = {"trend": "趋势态", "range": "震荡态"}
    for reg in order:
        st = split.get(reg)
        if not st:
            continue
        lines.append(f"【{cn[reg]}】")
        lines.append(f"① 样本：{st.n} 笔 — {st.note}")
        lines.append(f"② 胜率：{st.win_rate}% · 赢{st.wins}/亏{st.losses}")
        lines.append(f"③ 期望：每笔 {st.avg_r:+.3f}R · 累计 {st.total_r:+.2f}R")
        lines.append(f"④ 盈亏比：{st.profit_factor}")
        if st.by_model:
            tops = sorted(st.by_model.items(), key=lambda kv: -kv[1]["n"])[:5]
            for m, d in tops:
                lines.append(f"   {m}：{d['n']}笔 · 胜率{d['win_rate']}% · 期望{d['avg_r']:+.3f}R")
        lines.append("")
    # 跨态对比警示
    t, r = split.get("trend"), split.get("range")
    if t and r and t.n and r.n:
        decay = t.win_rate - r.win_rate
        lines.append("【跨态对比】")
        lines.append(f"① 胜率差：趋势{t.win_rate}% vs 震荡{r.win_rate}% — 衰减{decay:+.1f}%")
        if decay > 25:
            lines.append("② 警示：趋势态胜率显著高于震荡态 — 混合胜率高估真实期望·禁止外推到震荡月")
        elif r.avg_r < 0 <= t.avg_r:
            lines.append("② 警示：震荡态期望为负 — 策略仅在趋势中有效·震荡月应停用或反向")
        else:
            lines.append("② 评估：两态期望接近 — 策略市态稳健性较好")
        lines.append(f"③ 仓位口径：只用震荡态期望({r.avg_r:+.3f}R)作保守基准·不用混合或趋势胜率")
    return "\n".join(lines)


if __name__ == "__main__":
    import backtest_runner as bt
    klp = ROOT / "data" / "btc_klines_30d_merged.json"
    if not klp.exists():
        print(json.dumps({"ok": False, "err": f"缺K线: {klp}"}, ensure_ascii=False))
        sys.exit(0)
    raw = json.loads(klp.read_text(encoding="utf-8"))
    kl = raw if isinstance(raw, list) else raw.get("klines", [])
    closes = [float(k["close"]) for k in kl]
    highs = [float(k["high"]) for k in kl]
    lows = [float(k["low"]) for k in kl]
    opens = [float(k.get("open", k["close"])) for k in kl]
    vols = [float(k.get("volume", 0)) for k in kl]
    ts = [k.get("time") or k.get("timestamp") or k.get("open_time") for k in kl]

    res = bt.run_backtest("BTCUSDT", closes, highs, lows, opens, vols, ts) \
        if hasattr(bt, "run_backtest") else bt.backtest_from_klines("BTCUSDT", kl)
    split = split_by_regime(res, closes, highs, lows, ts)
    print(format_regime_report(split, "BTCUSDT"))
    print()
    print(f"混合胜率(对照): {res.win_rate}% · 混合期望: {res.avg_r:+.3f}R — 不用于仓位")
