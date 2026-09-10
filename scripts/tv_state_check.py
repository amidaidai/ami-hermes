#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核实 TV 状态 + 清理残留对话框。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

CHECK = """
(() => {
  const d = document.querySelector('[data-name="rename-dialog"]');
  let closed = false;
  if (d) {
    const c = [...d.querySelectorAll('button')].find(b => (b.textContent||'').trim()==='取消');
    if (c) { c.click(); closed = true; }
  }
  return JSON.stringify({dialog_present: !!d, cancelled: closed});
})()
"""


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

            print("== 残留对话框清理 ==")
            print("  ", await call("ui_evaluate", {"expression": CHECK}))

            print("== 账号里的脚本 ==")
            s = await call("pine_list_scripts")
            for x in s.get("scripts", []):
                print(f"   {x['name']!r} modified={x['modified']} id={x['id'][-8:]}")

            print("== 图表 ==")
            print("  ", await call("chart_get_state"))


if __name__ == "__main__":
    asyncio.run(main())
