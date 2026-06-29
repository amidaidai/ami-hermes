#!/usr/bin/env python3
"""
QLib启发式因子库 v1.1 — 表格化输出
"""
from __future__ import annotations
import json, sys, os, math
from datetime import datetime, timezone, timedelta
import urllib.request

TZ = timezone(timedelta(hours=8))
UA = "Hermes/1.0"
DATA_DIR = os.path.expanduser("~/AppData/Local/hermes/data")
os.makedirs(DATA_DIR, exist_ok=True)


def fetch_klines(symbol="BTCUSDT", interval="1h", limit=200) -> list:
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    for ph in [None, {}]:
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler(ph)) if ph is not None else urllib.request.build_opener()
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with opener.open(req, timeout=10) as r:
                return json.loads(r.read())
        except Exception:
            continue
    return []


def _sma(values: list, period: int) -> list:
    if len(values) < period: return [None] * len(values)
    result = [None] * (period - 1)
    window = sum(values[:period])
    result.append(window / period)
    for i in range(period, len(values)):
        window += values[i] - values[i - period]
        result.append(window / period)
    return result


def _ema(values: list, period: int) -> list:
    if len(values) < period: return [None] * len(values)
    k = 2.0 / (period + 1)
    result = [None] * len(values)
    result[period - 1] = sum(values[:period]) / period
    for i in range(period, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def _std(values: list, period: int) -> list:
    sma = _sma(values, period)
    result = [None] * len(values)
    for i in range(period - 1, len(values)):
        avg = sma[i]
        sq_sum = sum((v - avg) ** 2 for v in values[i - period + 1:i + 1])
        result[i] = math.sqrt(sq_sum / period)
    return result


def _max(values: list, period: int) -> list:
    result = [None] * len(values)
    for i in range(period - 1, len(values)):
        result[i] = max(values[i - period + 1:i + 1])
    return result


def _min(values: list, period: int) -> list:
    result = [None] * len(values)
    for i in range(period - 1, len(values)):
        result[i] = min(values[i - period + 1:i + 1])
    return result


def _roc(values: list, period: int) -> list:
    result = [None] * period
    for i in range(period, len(values)):
        if values[i - period] and values[i]:
            result.append((values[i] - values[i - period]) / values[i - period] * 100)
        else:
            result.append(None)
    return result


def last(arr, default=None):
    for v in reversed(arr):
        if v is not None: return v
    return default


def compute_factors(klines: list) -> dict:
    if not klines or len(klines) < 60:
        return {"error": "insufficient data", "count": len(klines) if klines else 0}
    
    opens = [float(k[1]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    closes = [float(k[4]) for k in klines]
    volumes = [float(k[5]) for k in klines]
    n = len(closes)
    factors = {}
    
    # Momentum
    hh_20, ll_20 = _max(highs, 20), _min(lows, 20)
    factors["KMID"] = last([(c - ll) / (hh - ll) if hh and ll and hh != ll else None for c, hh, ll in zip(closes, hh_20, ll_20)])
    
    deltas = [closes[i] - closes[i - 1] for i in range(1, n)]
    gains, losses = [max(d, 0) for d in deltas], [max(-d, 0) for d in deltas]
    avg_gain, avg_loss = _ema(gains, 14), _ema(losses, 14)
    factors["RSI"] = last([100 - 100 / (1 + (g / (l + 1e-10))) if g and l else None for g, l in zip(avg_gain, avg_loss)])
    
    ema12, ema26 = _ema(closes, 12), _ema(closes, 26)
    dif_vals = [(e12 - e26) if e12 and e26 else None for e12, e26 in zip(ema12, ema26)]
    dea_vals = _ema([v or 0 for v in dif_vals], 9)
    factors["MACD"] = last([(dif - dea) * 2 if dif and dea else None for dif, dea in zip(dif_vals, dea_vals)])
    
    factors["ROC6"] = last(_roc(closes, 6))
    factors["ROC20"] = last(_roc(closes, 20))
    
    hh_9, ll_9 = _max(highs, 9), _min(lows, 9)
    rsv_vals = [(c - ll) / (hh - ll) * 100 if hh and ll and hh != ll else 50 for c, hh, ll in zip(closes, hh_9, ll_9)]
    k_vals, d_vals = _ema(rsv_vals, 3), _ema([v or 50 for v in _ema(rsv_vals, 3)], 3)
    factors["KDJ_K"] = last(k_vals)
    factors["KDJ_D"] = last(d_vals)
    
    # Trend
    sma5, sma60 = _sma(closes, 5), _sma(closes, 60)
    factors["MA5"] = last(sma5)
    factors["MA60"] = last(sma60)
    factors["MOM5"] = closes[-1] - closes[-6] if n > 5 else None
    factors["MOM20"] = closes[-1] - closes[-21] if n > 20 else None
    
    # Volatility
    tr_vals = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]) if i > 0 else 0, abs(lows[i] - closes[i - 1]) if i > 0 else 0) for i in range(n)]
    factors["ATR"] = last(_ema(tr_vals, 14))
    sma20, std20 = _sma(closes, 20), _std(closes, 20)
    factors["BBW"] = last(std20) / (last(sma20) + 1e-10) if last(std20) and last(sma20) else None
    
    # Volume
    vol_ema5, vol_ema20 = _ema(volumes, 5), _ema(volumes, 20)
    factors["VRATIO"] = last(vol_ema5) / (last(vol_ema20) + 1e-10) if last(vol_ema5) else None
    
    # Composite signal
    score = 0
    score += 1 if (factors.get("KMID") or 0.5) > 0.7 else -1 if (factors.get("KMID") or 0.5) < 0.3 else 0
    score += 1 if (factors.get("RSI") or 50) > 60 else -1 if (factors.get("RSI") or 50) < 40 else 0
    score += 1 if (factors.get("MACD") or 0) > 0 else -1
    score += 1 if (factors.get("ROC6") or 0) > 0 else -1
    score += 1 if closes[-1] > (factors.get("MA5") or closes[-1]) else -1
    factors["SIGNAL"] = score
    factors["BIAS"] = "偏多" if score >= 3 else "偏空" if score <= -3 else "观望"
    
    return factors


def main():
    now = datetime.now(TZ)
    ts = now.strftime("%Y-%m-%d %H:%M BJT")
    
    klines = fetch_klines("BTCUSDT", "1h", 200)
    if not klines:
        print(f"因子信号 {ts} | 数据获取失败")
        return 1
    
    f = compute_factors(klines)
    price = float(klines[-1][4])
    
    lines = [f"BTC量化因子 {ts} | ${price:,.0f}"]
    lines.append("")
    lines.append("| 类别 | 因子 | 数值 | 方向 |")
    lines.append("|------|------|------|------|")
    
    def arrow(v, bullish, bearish):
        return "↑" if v is not None and v > bullish else "↓" if v is not None and v < bearish else "→"
    
    lines.append(f"| 动量 | RSI(14) | {f.get('RSI', '?'):.0f}" + (f" | {arrow(f.get('RSI'), 60, 40)} |" if f.get('RSI') else " | - |"))
    lines.append(f"| 动量 | MACD | {f.get('MACD', '?'):+.1f}" + (f" | {arrow(f.get('MACD'), 0, -0.1)} |" if f.get('MACD') is not None else " | - |"))
    lines.append(f"| 动量 | ROC6 | {f.get('ROC6', '?'):+.1f}% | {arrow(f.get('ROC6'), 0, -0.1)} |")
    lines.append(f"| 趋势 | MA5偏离 | {(price - (f.get('MA5') or price)) / (f.get('MA5') or price) * 100:+.2f}% | {arrow(price, f.get('MA5') or price + 1, f.get('MA5') or price - 1)} |")
    lines.append(f"| 趋势 | MOM20 | {f.get('MOM20', '?'):+.0f} | {arrow(f.get('MOM20'), 0, -0.1)} |")
    lines.append(f"| 波动 | ATR(14) | {f.get('ATR', '?'):.0f} | - |")
    lines.append(f"| 成交量 | VRATIO | {f.get('VRATIO', '?'):.2f} | {arrow(f.get('VRATIO'), 1.2, 0.8)} |")
    
    score = f.get("SIGNAL", 0)
    bias = f.get("BIAS", "?")
    direction_arrow = "↑" if score > 0 else "↓" if score < 0 else "→"
    lines.append("")
    lines.append(f"综合信号: {direction_arrow} {bias} (评分{score}/5)")
    
    output = "\n".join(lines)
    try:
        from alert_dedup import dedup_wrapper
        dedup_wrapper("qlib_factors", output, force_seconds=3600)
    except ImportError:
        print(output)
    
    # 保存 — 双落盘
    result_json = {"ts": now.isoformat(), "price": price, "factors": {k: (round(v, 4) if isinstance(v, float) and not math.isnan(v) else v) for k, v in f.items()}}
    
    # 落盘1: hermes data
    with open(os.path.join(DATA_DIR, "qlib_factors.json"), "w") as fh:
        json.dump(result_json, fh, ensure_ascii=False)
    
    # 落盘2: 项目data（cron_read 读取）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    proj_data = os.path.join(script_dir, "..", "data")
    os.makedirs(proj_data, exist_ok=True)
    with open(os.path.join(proj_data, "qlib_factors.json"), "w") as fh:
        json.dump(result_json, fh, ensure_ascii=False)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
