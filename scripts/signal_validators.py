#!/usr/bin/env python3
"""
棠溪 · 信号独立验证器 signal_validators.py v1.0

从 auto_card.py 抽取两个核心验证逻辑，做成作战室的轻量独立验证闸门
（不跑 auto_card 全量管线，避免每小时 cron 被拖垮）：

  1. 多空比反指 (long_short_contra)：Binance 多空账户比 → 散户拥挤反向警惕
  2. 周期一致性 (tf_alignment)：4h/1h/15m 各自方向 → 相邻周期冲突硬门

两道闸门任一否决 → 作战室不发执行计划（呼应 auto_card 的周期冲突硬门）。
"""
from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import urllib.request
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))


def _get_json(url: str, timeout: int = 8) -> object:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def long_short_contra(symbol: str = "BTCUSDT") -> dict:
    """多空比反指：散户极度拥挤 → 反向警惕。

    返回 {available, signal, ratio, contra, note}
    signal: 'bull_trap' / 'bear_trap' / 'neutral'
    """
    sym = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
    url = (f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
           f"?symbol={sym}&period=5m&limit=1")
    data = _get_json(url)
    if not data or not isinstance(data, list) or not data:
        return {"available": False, "signal": "neutral", "ratio": None,
                "contra": "", "note": "多空比API不可用"}
    try:
        row = data[0]
        long_acc = float(row.get("longAccount", 0))
        short_acc = float(row.get("shortAccount", 0))
        if long_acc + short_acc <= 0:
            return {"available": True, "signal": "neutral", "ratio": 0.0,
                    "contra": "", "note": "数据异常"}
        ratio = long_acc / max(1e-9, short_acc)
        if ratio >= 2.0:
            signal, contra = "bear_trap", "散户极度拥挤多→反向警惕顶"
        elif ratio <= 0.5:
            signal, contra = "bull_trap", "散户极度拥挤空→反向警惕底"
        else:
            signal, contra = "neutral", ""
        return {"available": True, "signal": signal, "ratio": round(ratio, 2),
                "contra": contra, "note": f"多空比{ratio:.2f}"}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "signal": "neutral", "ratio": None,
                "contra": "", "note": f"解析失败:{e}"}


def _tf_direction(symbol: str, interval: str) -> int:
    """单个周期方向：收盘相对开盘。1=多 -1=空 0=中性。"""
    sym = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
    url = (f"https://api.binance.com/api/v3/klines?symbol={sym}"
           f"&interval={interval}&limit=3")
    data = _get_json(url)
    if not data or len(data) < 2:
        return 0
    try:
        # 取最近一根的 开/收
        o = float(data[-1][1]); c = float(data[-1][4])
        if c > o * 1.0005:
            return 1
        if c < o * 0.9995:
            return -1
        return 0
    except Exception:
        return 0


def tf_alignment(symbol: str = "BTCUSDT") -> dict:
    """周期一致性：4h/1h/15m 方向 → 相邻冲突硬门。

    返回 {available, d4, d1, d15, conflict, aligned, note}
    conflict=True → 相邻周期明确反向（4h≠1h 或 1h≠15m），应否决交易。
    """
    d4 = _tf_direction(symbol, "4h")
    d1 = _tf_direction(symbol, "1h")
    d15 = _tf_direction(symbol, "15m")
    if d4 == 0 and d1 == 0 and d15 == 0:
        return {"available": False, "d4": d4, "d1": d1, "d15": d15,
                "conflict": False, "aligned": False, "note": "周期方向数据不足"}
    conflict = (d4 != 0 and d1 != 0 and d4 * d1 == -1) or \
               (d1 != 0 and d15 != 0 and d1 * d15 == -1)
    aligned = (d4 != 0 and d4 == d1 == d15)
    names = {1: "多", -1: "空", 0: "中性"}
    note = f"4h{names[d4]}/1h{names[d1]}/15m{names[d15]}" + (" · 冲突" if conflict else " · 同向" if aligned else "")
    return {"available": True, "d4": d4, "d1": d1, "d15": d15,
            "conflict": conflict, "aligned": aligned, "note": note}


def validate_plan(symbol: str, side: str) -> dict:
    """综合两道闸门，返回是否通过。side: '🟢做多'/'🔴做空'/'⚪观望'。

    返回 {pass: bool, blockers: [str], notes: [str]}
    """
    blockers = []
    notes = []

    ls = long_short_contra(symbol)
    if ls.get("available"):
        notes.append(f"多空比{ls['ratio']}({ls['contra'] or '正常'})")
        # 做多时散户极度拥挤多 = 顶风险；做空时散户极度拥挤空 = 底风险
        if ls["signal"] == "bear_trap" and side == "🟢做多":
            blockers.append(f"多空比{ls['ratio']}散户拥挤多→警惕做多顶部")
        elif ls["signal"] == "bull_trap" and side == "🔴做空":
            blockers.append(f"多空比{ls['ratio']}散户拥挤空→警惕做空底部")

    tf = tf_alignment(symbol)
    if tf.get("available"):
        notes.append(tf["note"])
        if tf["conflict"]:
            blockers.append(f"周期冲突({tf['note']})→方向矛盾不交易")

    return {"pass": len(blockers) == 0, "blockers": blockers, "notes": notes}


if __name__ == "__main__":
    import pprint
    pprint.pprint({"long_short": long_short_contra(), "tf": tf_alignment(),
                   "validate": validate_plan("BTCUSDT", "🟢做多")})
