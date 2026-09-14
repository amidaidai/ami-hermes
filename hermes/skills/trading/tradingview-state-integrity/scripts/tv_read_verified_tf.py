#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多周期 TV 读取器 —— 带「周期锁定 + K线间距校验 + 重试」。

为什么需要它
------------
共享的 TradingView 图表会被后台任务（btc_tv_refresh.py / xau_tv_sync.py 等）
借走并循环切周期。此时：

  * `chart_set_timeframe` 恒返回 {"success": true, "chart_ready": true}；
  * `chart_get_state` 的 resolution 也可能只是**回显你请求的值**；
  * `studies[].resolution` 字段会滞后一两拍。

三者都拦不住「你请求 4h，读回来的其实是 5m」这种静默污染 —— 实测会出现
「1D」与「4h」两组数值一模一样、相邻 K 线间距都是 300s。

唯一可信判据是**数据本身**：OHLCV 的 (period.to - period.from) / (bar_count - 1)
必须等于该周期一根 K 线的秒数。本脚本把这件事做成硬门：每个周期都要
「切 → 校验 resolution → 读 OHLCV → 验间距 → 不符则重试」，全部过了才落盘。

用法
----
    python tv_read_verified_tf.py --symbol BINANCE:BTCUSDT.P \\
        --out outputs/btc_5tf_verified.json
    python tv_read_verified_tf.py --symbol OANDA:XAUUSD --timeframes 1D,240,60,15,5

可选：--server <tradingview-mcp/src/server.js>（默认自动探测常见路径）
      --tries N（每周期最多锁定尝试次数，默认 4）

退出码：0 = 全部周期校验通过；1 = 有周期未通过（输出里带 verified=false）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

try:
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp import ClientSession
except ImportError:  # pragma: no cover
    print("需要 mcp 客户端库（Hermes venv / 项目环境内可用）", file=sys.stderr)
    raise

# 周期 → 一根 K 线应有的秒数
TF_SECONDS = {"1D": 86400, "240": 14400, "60": 3600, "30": 1800,
              "15": 900, "5": 300, "1": 60}
# TV 可能回报的别名 → 规范形
ALIAS = {"D": "1D", "1D": "1D", "4H": "240", "240": "240", "1H": "60",
         "60": "60", "30M": "30", "30": "30", "15M": "15", "15": "15",
         "5M": "5", "5": "5", "1M": "1", "1": "1"}
TOLERANCE = 0.05


def txt(result) -> str:
    if hasattr(result, "content"):
        parts = []
        for item in result.content:
            t = getattr(item, "text", None)
            if t is None and isinstance(item, dict):
                t = item.get("text")
            if t:
                parts.append(t)
        return "\n".join(parts)
    return json.dumps(result, ensure_ascii=False)


def jload(raw: str) -> dict:
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    if isinstance(payload, dict) and isinstance(payload.get("result"), str):
        try:
            payload = json.loads(payload["result"])
        except Exception:
            return {}
    return payload if isinstance(payload, dict) else {}


async def call(session, name, args=None):
    return txt(await session.call_tool(name, args or {}))


async def chart_state(session) -> dict:
    return jload(await call(session, "chart_get_state"))


async def lock_timeframe(session, want: str, tries: int = 8):
    """切到目标周期并确认。返回 (ok, 实际回报的 resolution, 尝试次数)。"""
    target = ALIAS.get(want.upper(), want.upper())
    for attempt in range(tries):
        cur = str((await chart_state(session)).get("resolution") or "").upper()
        if ALIAS.get(cur, cur) == target:
            return True, cur, attempt
        # 一律用纯数字/1D 写法；带单位的 "4h"/"5m" 可能静默不生效
        await call(session, "chart_set_timeframe", {"timeframe": target})
        await asyncio.sleep(5 if target in ("1D", "240") else 4)
        cur = str((await chart_state(session)).get("resolution") or "").upper()
        if ALIAS.get(cur, cur) == target:
            return True, cur, attempt + 1
    return False, cur, tries


def bar_seconds(ohlcv: dict) -> float:
    """相邻 K 线间隔秒数 —— 判断「读到的到底是不是这个周期」的硬判据。"""
    period = ohlcv.get("period") or {}
    bars = int(ohlcv.get("bar_count") or 0)
    if bars < 2:
        return 0.0
    span = float(period.get("to", 0)) - float(period.get("from", 0))
    return span / (bars - 1)


async def read_one(session, want: str, tries: int, with_studies: bool) -> dict:
    entry: dict = {"requested": want, "expected_bar_seconds": TF_SECONDS.get(want)}
    expected = TF_SECONDS.get(want)
    for attempt in range(1, tries + 1):
        ok, actual, lock_tries = await lock_timeframe(session, want)
        if not ok:
            entry[f"lock_fail_{attempt}"] = actual
            continue
        await asyncio.sleep(3)  # 等指标重算
        ohlcv = jload(await call(session, "data_get_ohlcv", {"summary": True}))
        per = bar_seconds(ohlcv)
        entry["bar_seconds"] = round(per, 1)
        entry["actual_resolution"] = actual
        entry["lock_tries"] = lock_tries
        entry["attempt"] = attempt
        if expected and abs(per - expected) <= expected * TOLERANCE:
            entry["verified"] = True
            entry["ohlcv"] = ohlcv
            if with_studies:
                entry["studies"] = jload(await call(session, "data_get_study_values"))
                entry["pine_tables_main"] = jload(await call(
                    session, "data_get_pine_tables", {"study_filter": "SVP+ICT+VWAP+CVD"}))
                entry["pine_tables_sub"] = jload(await call(
                    session, "data_get_pine_tables", {"study_filter": "Volume Aggregated"}))
                entry["pine_labels"] = jload(await call(session, "data_get_pine_labels"))
                entry["pine_lines"] = jload(await call(session, "data_get_pine_lines"))
            return entry
        # 数据间距和周期对不上 → 重新锁定重读（典型：报 4h 实读 5m）
        entry[f"mismatch_bar_seconds_{attempt}"] = round(per, 1)
        await asyncio.sleep(4)
    entry["verified"] = False
    entry["error"] = "周期数据校验失败：OHLCV 的K线间距与目标周期不符"
    return entry


def find_server(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    for cand in (Path("D:/Hermes agent/tools/tradingview-mcp/src/server.js"),
                 Path.home() / "tools/tradingview-mcp/src/server.js"):
        if cand.exists():
            return cand
    return Path("D:/Hermes agent/tools/tradingview-mcp/src/server.js")


async def run(args) -> int:
    server = find_server(args.server)
    if not server.exists():
        print(f"找不到 tradingview-mcp server: {server}", file=sys.stderr)
        return 2
    timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    params = StdioServerParameters(command="node", args=[str(server)])
    result = {"ts_bjt": time.strftime("%Y-%m-%d %H:%M:%S"), "symbol": None, "tf": {}}

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            symbol = str((await chart_state(session)).get("symbol") or "")
            if args.symbol and symbol.upper() != args.symbol.upper():
                await call(session, "chart_set_symbol", {"symbol": args.symbol})
                await asyncio.sleep(5)
                symbol = str((await chart_state(session)).get("symbol") or "")
            result["symbol"] = symbol

            for want in timeframes:
                label = {v: k for k, v in TF_SECONDS.items()}.get(TF_SECONDS.get(want), want)
                entry = await read_one(session, want, args.tries,
                                       with_studies=(want != "1D"))
                result["tf"][want] = entry
                if entry.get("verified"):
                    print(f"[{want}] OK bar_s={entry['bar_seconds']} "
                          f"actual={entry.get('actual_resolution')} attempt={entry['attempt']}")
                else:
                    print(f"[{want}] FAIL bar_s={entry.get('bar_seconds')} "
                          f"expected={entry.get('expected_bar_seconds')} "
                          f"→ {entry.get('error')}")

            # 回主执行周期（加密15m / 黄金5m），便于随后截图
            await lock_timeframe(session, args.back_to)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [k for k, v in result["tf"].items() if not v.get("verified")]
    print(f"SAVED {out}" + (f"  ⚠ 未通过周期: {bad}" if bad else "  ✅ 全部周期校验通过"))
    return 1 if bad else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="多周期 TV 读取（周期锁定+K线间距校验）")
    parser.add_argument("--symbol", default="BINANCE:BTCUSDT.P", help="目标品种，如 BINANCE:BTCUSDT.P")
    parser.add_argument("--timeframes", default="1D,240,60,15,5", help="逗号分隔，默认五层")
    parser.add_argument("--out", default="outputs/tv_read_verified_tf.json", help="输出 JSON 路径")
    parser.add_argument("--back-to", default="15", help="结束时回到的周期（加密15/黄金5）")
    parser.add_argument("--tries", type=int, default=4, help="每周期最多重试次数")
    parser.add_argument("--server", default=None, help="tradingview-mcp/src/server.js 路径")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
