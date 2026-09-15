#!/usr/bin/env python3
"""切到指定品种/周期并截全屏图（含价格轴+副指标窗格），返回 PNG 路径。

用法: python scripts/tv_shot.py [SYMBOL] [TF=15] [--wait 20]
"""
import sys, json, asyncio, argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(r"D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_tv_mcp import stdio_client, StdioServerParameters, call_tool, parse_result, set_symbol, set_timeframe  # noqa


async def main(symbol, tf, wait):
    params = StdioServerParameters(command="node", args=[str(ROOT / "tools/tradingview-mcp/src/server.js")])
    async with stdio_client(params) as (read, write):
        from mcp import ClientSession
        async with ClientSession(read, write) as session:
            await session.initialize()
            await set_symbol(session, symbol)
            await asyncio.sleep(2)
            await set_timeframe(session, tf)
            await asyncio.sleep(wait)
            st = json.loads(parse_result(await call_tool(session, "chart_get_state", {})))
            print("state:", json.dumps({k: st.get(k) for k in ("symbol", "resolution")}, ensure_ascii=False))
            try:
                await call_tool(session, "ui_fullscreen", {})
                await asyncio.sleep(2)
            except Exception as e:
                print("fullscreen skip:", e)
            r = await call_tool(session, "capture_screenshot", {"region": "full"})
            t = parse_result(r)
            print("shot:", t[:600])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", default="BINANCE:BTCUSDT.P")
    ap.add_argument("tf", nargs="?", default="15")
    ap.add_argument("--wait", type=int, default=20)
    a = ap.parse_args()
    asyncio.run(main(a.symbol, a.tf, a.wait))
