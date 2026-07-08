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
    """周期一致性：1D/4h/1h/15m/5m 方向 → 相邻冲突硬门。

    返回 {available, d1d, d4, d1, d15, d5m, conflict, aligned, note}
    conflict=True → 相邻周期明确反向（1D≠4h 或 4h≠1h 或 1h≠15m 或 15m≠5m），应否决交易。
    """
    d1d = _tf_direction(symbol, "1d")
    d4 = _tf_direction(symbol, "4h")
    d1 = _tf_direction(symbol, "1h")
    d15 = _tf_direction(symbol, "15m")
    d5m = _tf_direction(symbol, "5m")
    if d1d == 0 and d4 == 0 and d1 == 0 and d15 == 0 and d5m == 0:
        return {"available": False, "d1d": d1d, "d4": d4, "d1": d1, "d15": d15, "d5m": d5m,
                "conflict": False, "aligned": False, "note": "周期方向数据不足"}
    # 相邻冲突：1D≠4h 或 4h≠1h 或 1h≠15m 或 15m≠5m
    conflict = ((d1d != 0 and d4 != 0 and d1d * d4 == -1) or
                (d4 != 0 and d1 != 0 and d4 * d1 == -1) or
                (d1 != 0 and d15 != 0 and d1 * d15 == -1) or
                (d15 != 0 and d5m != 0 and d15 * d5m == -1))
    aligned = (d1d != 0 and d1d == d4 == d1 == d15 == d5m)
    names = {1: "多", -1: "空", 0: "中性"}
    note = f"1D{names[d1d]}/4h{names[d4]}/1h{names[d1]}/15m{names[d15]}/5m{names[d5m]}" + (" · 冲突" if conflict else " · 同向" if aligned else "")
    return {"available": True, "d1d": d1d, "d4": d4, "d1": d1, "d15": d15, "d5m": d5m,
            "conflict": conflict, "aligned": aligned, "note": note}


def tf_alignment_tv(symbol: str = "BTCUSDT", wait: float = 3.0) -> dict:
    """TV MCP 多周期方向（1D/4h/1h/15m/5m）。

    严格按你的要求：每个周期 set_timeframe 后等 wait 秒让指标完全加载，
    再读 OHLCV summary 判方向。

    关键修复：TV Desktop CDP 在单会话里连续切周期会断连（Connection closed），
    改为【每周期独立 MCP 会话】（开→切品种→切周期→等加载→读→关）。

    symbol：BINANCE:BTCUSDT.P（加密）或 OANDA:XAUUSD（贵金属）等。

    降级：TV Desktop 调试端口(9222)未开放时直接返回 available=False，
    由调用方回落 Binance REST（环境无 TV 时不卡死）。
    """
    # 端口探测：TV Desktop CDP 未开则跳过（避免无谓的 node 启动+超时）
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", 9222)) != 0:
                return {"available": False, "conflict": False,
                        "note": "TV Desktop(9222)未运行→降级REST"}
    except Exception:
        return {"available": False, "conflict": False, "note": "TV端口探测失败→降级REST"}

    try:
        import asyncio
        import fetch_tv_mcp as tv
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from mcp import ClientSession
        from pathlib import Path as _P
        server_script = _P("D:/Hermes agent/tools/tradingview-mcp/src/server.js")
        if not server_script.exists():
            return {"available": False, "conflict": False, "note": "TV MCP server 未找到"}

        async def _one_tf(res: str) -> int:
            """单个周期的独立会话：开→切品种→切周期→等→读→关。返回方向 1/-1/0。"""
            sp = StdioServerParameters(command="node", args=[str(server_script)])
            async with stdio_client(sp) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    await tv.set_symbol(s, symbol)
                    await asyncio.sleep(wait)
                    await tv.set_timeframe(s, res)
                    await asyncio.sleep(wait)  # 等指标完全加载
                    raw = await tv.get_ohlcv(s, summary=True)
                    txt = tv.parse_result(raw)
                    return _dir_from_ohlcv_summary(txt)

        async def _run():
            dirs = {}
            for res in ("1D", "240", "60", "15", "5"):  # 1D / 4h / 1h / 15m / 5m
                try:
                    dirs[res] = await _one_tf(res)
                except Exception:  # noqa: BLE001
                    dirs[res] = 0
            return dirs

        dirs = asyncio.run(_run())
        d1d = dirs.get("1D", 0); d4 = dirs.get("240", 0); d1 = dirs.get("60", 0); d15 = dirs.get("15", 0); d5m = dirs.get("5", 0)
        if d1d == 0 and d4 == 0 and d1 == 0 and d15 == 0 and d5m == 0:
            return {"available": False, "conflict": False, "note": "TV多周期方向全空"}
        # 相邻冲突：1D≠4h 或 4h≠1h 或 1h≠15m 或 15m≠5m
        conflict = ((d1d != 0 and d4 != 0 and d1d * d4 == -1) or
                    (d4 != 0 and d1 != 0 and d4 * d1 == -1) or
                    (d1 != 0 and d15 != 0 and d1 * d15 == -1) or
                    (d15 != 0 and d5m != 0 and d15 * d5m == -1))
        aligned = (d1d != 0 and d1d == d4 == d1 == d15 == d5m)
        names = {1: "多", -1: "空", 0: "中性"}
        note = f"TV 1D{names[d1d]}/4h{names[d4]}/1h{names[d1]}/15m{names[d15]}/5m{names[d5m]}" + (" · 冲突" if conflict else " · 同向" if aligned else "")
        return {"available": True, "d1d": d1d, "d4": d4, "d1": d1, "d15": d15, "d5m": d5m,
                "conflict": conflict, "aligned": aligned, "note": note, "source": "TV"}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "conflict": False, "note": f"TV多周期异常:{e}"}


def _dir_from_ohlcv_summary(txt: str) -> int:
    """从 OHLCV summary 文本判方向：TV 返回的是 JSON，含 change_pct 字段。1多/-1空/0中性。

    真实结构示例：
      {"success":true,"bar_count":100,"open":63309.2,"close":61984,
       "high":64234.1,"low":61615,"change":-1325.2,"change_pct":"-2.09%",...}
    """
    import re, json
    # 优先：JSON 解析取 change_pct（TV 实际返回格式）
    try:
        # 可能包裹在 MCP content 文本里，先找第一个 { 起的 JSON
        s = txt.strip()
        if s.startswith("{"):
            obj = json.loads(s)
        else:
            # 文本里嵌 JSON，找 success 开头对象
            m = re.search(r'\{[^{}]*"change_pct"[^{}]*\}', s)
            if m:
                obj = json.loads(m.group(0))
            else:
                obj = None
        if obj and "change_pct" in obj:
            ch = float(str(obj["change_pct"]).replace("%", "").strip())
            if ch > 0.05:
                return 1
            if ch < -0.05:
                return -1
            return 0
    except Exception:
        pass
    # 退化：正则匹配 change%
    m = re.search(r"change[_%]?pct?[:\s]*[\"']?([+-]?\d+(?:\.\d+)?)\s*%", txt, re.IGNORECASE)
    if m:
        ch = float(m.group(1))
        if ch > 0.05:
            return 1
        if ch < -0.05:
            return -1
        return 0
    return 0


def validate_plan(symbol: str, side: str, tf_override: dict = None) -> dict:
    """综合两道闸门，返回是否通过。side: '🟢做多'/'🔴做空'/'⚪观望'。

    周期方向优先 TV MCP（等加载完再读），不可用降级 Binance REST。
    tf_override: 传入已算好的周期方向（避免重复调用 Binance 导致数据漂移），
    不传则自行获取（TV优先→REST降级）。
    """
    blockers = []
    notes = []

    ls = long_short_contra(symbol)
    if ls.get("available"):
        notes.append(f"多空比{ls['ratio']}({ls['contra'] or '正常'})")
        if ls["signal"] == "bear_trap" and side == "🟢做多":
            blockers.append(f"多空比{ls['ratio']}散户拥挤多→警惕做多顶部")
        elif ls["signal"] == "bull_trap" and side == "🔴做空":
            blockers.append(f"多空比{ls['ratio']}散户拥挤空→警惕做空底部")

    # 周期一致性：优先用传入快照（展示与闸门同源），否则 TV→REST
    tf = tf_override if (tf_override and tf_override.get("available")) else None
    tf_src = "快照" if tf else None
    if tf is None:
        tf = tf_alignment_tv(symbol)
        tf_src = "TV"
        if not tf.get("available"):
            tf = tf_alignment(symbol)
            tf_src = "REST"
    if tf.get("available"):
        notes.append(f"{tf_src} {tf['note']}")
        if tf["conflict"]:
            blockers.append(f"周期冲突({tf['note']})→方向矛盾不交易")

    return {"pass": len(blockers) == 0, "blockers": blockers, "notes": notes}


if __name__ == "__main__":
    import pprint
    pprint.pprint({"long_short": long_short_contra(), "tf_tv": tf_alignment_tv(),
                   "validate": validate_plan("BTCUSDT", "🟢做多")})
