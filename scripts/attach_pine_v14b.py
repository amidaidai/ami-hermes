#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 Pine 编辑器里找并点击「添加到图表」，把当前脚本挂到图表上。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LIST_BTNS = """
(() => {
  const out = [];
  document.querySelectorAll('button,[role=button]').forEach(b => {
    const t = (b.textContent||'').trim();
    if (!t || t.length > 24) return;
    if (/添加|图表|保存|编译|save|add|compile|chart/i.test(t)) {
      const r = b.getBoundingClientRect();
      out.push({t: t, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), dis: b.disabled,
                dn: b.getAttribute('data-name')||'', al: b.getAttribute('aria-label')||''});
    }
  });
  return JSON.stringify(out.slice(0, 30));
})()
"""

CLICK_ADD = """
(() => {
  const cands = [...document.querySelectorAll('button,[role=button]')]
    .filter(b => /添加到图表|Add to chart|加入图表/i.test((b.textContent||'').trim()));
  if (!cands.length) return JSON.stringify({ok:false, why:'no-add-button'});
  cands[0].click();
  return JSON.stringify({ok:true, clicked: cands[0].textContent.trim()});
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

            await call("ui_open_panel", {"panel": "pine-editor", "action": "open"})
            print("[1] 编辑器按钮:")
            btns = await call("ui_evaluate", {"expression": LIST_BTNS})
            try:
                for b in json.loads(btns) if isinstance(btns, str) else btns:
                    print(f"    {b.get('t')!r:26s} dn={b.get('dn')!r} dis={b.get('dis')} @({b.get('x')},{b.get('y')})")
            except Exception as e:
                print("   ", btns, e)

            print("[2] 点击「添加到图表」")
            r = await call("ui_evaluate", {"expression": CLICK_ADD})
            print("   ", r)

            print("[3] 等待 50s 后看图表 study")
            await asyncio.sleep(50)
            st = await call("chart_get_state")
            if isinstance(st, dict):
                for s in st.get("studies", []):
                    print(f"    {s['id']}  {s['name']}")


if __name__ == "__main__":
    asyncio.run(main())
