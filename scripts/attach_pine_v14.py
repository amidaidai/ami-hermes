#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把新脚本挂到图表，验证行为，然后移除旧实例。

顺序刻意如此：**先确认新实例真的在跑 v14（Feed Mode 变成 1），再摘掉旧的**，
避免中途出现「两个都不工作」的空档。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

NEW = "AggVol v14 修复S0自废"
OLD_ENTITY = "XhCJae"


def _text(result) -> str:
    for attr in ("content", "result"):
        v = getattr(result, attr, None)
        if v is None and isinstance(result, dict):
            v = result.get(attr)
        if v is None:
            continue
        if isinstance(v, str):
            return v
        if isinstance(v, (list, tuple)):
            for item in v:
                t = getattr(item, "text", None) or (item.get("text") if isinstance(item, dict) else None)
                if t:
                    return t
    return str(result)


async def main():
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    server = ROOT / "tools" / "tradingview-mcp" / "src" / "server.js"
    params = StdioServerParameters(command="node", args=[str(server)])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def call(tool, args=None):
                raw = _text(await session.call_tool(tool, args or {}))
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    return raw
                if isinstance(obj, dict) and isinstance(obj.get("result"), str):
                    try:
                        return json.loads(obj["result"])
                    except json.JSONDecodeError:
                        return obj
                return obj

            print("[1] 打开新脚本")
            print("  ", await call("pine_open", {"name": NEW}))

            print("[2] 编译并挂到图表")
            print("  ", await call("pine_smart_compile", {}))

            print("[3] 等待重算 55s")
            await asyncio.sleep(55)

            st = await call("chart_get_state")
            studies = st.get("studies", []) if isinstance(st, dict) else []
            print("[4] 图表上的 study:")
            for s in studies:
                print(f"    {s['id']}  {s['name']}")

            vals = await call("data_get_study_values")
            print("[5] 各 AggVol 实例的 DW:")
            if isinstance(vals, dict):
                for s in vals.get("studies", []):
                    if "Aggregated" not in str(s.get("name", "")):
                        continue
                    v = s.get("values", {})
                    print(f"    {s['id']} {s['name']}")
                    for k in ("Coverage Feed Mode", "Coverage Spot", "Coverage Perp",
                              "Exchange Dominance %", "HALDRO Valid Code",
                              "HALDRO State Pack (0无效/1支持多/2支持空/3冲突/4降权)"):
                        if k in v:
                            print(f"       {k} = {v[k]}")
    return studies


if __name__ == "__main__":
    asyncio.run(main())
