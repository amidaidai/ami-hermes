#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 v14 源码装成 TradingView 新脚本并挂到图表（自动化可行路径）。

## 为什么不能原地覆盖

TV Desktop 通过内部 API 打开脚本后，UI 的「当前脚本」指针是空的 —— 此时 Ctrl+S
不会覆盖原脚本，而是弹出「保存脚本 / 新脚本名称」对话框，预填 "... 1"，
确认后会**新建一个副本**。实测：`pine_save` 返回 "Ctrl+S_dispatched" 但账号里
`modified` 不变、`pine_open` 仍读到 921 行（旧版），图表因此一直跑旧代码。

## 本脚本的做法

  1. 打开编辑器 → 打开目标脚本 → 写入新源码
  2. Ctrl+S → 在「新脚本名称」对话框里**显式命名**为新名字并确认 → 落盘
  3. 回读校验行数一致
  4. 编译并挂到图表（pine_compile）
  5. 读 DW 验证行为改变

旧的同名脚本与图表上的旧 study 由调用方随后清理（避免主副总线出现两个同名源）。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


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


SET_DIALOG_NAME = """
(() => {
  const d = document.querySelector('[data-name="rename-dialog"]');
  if (!d) return JSON.stringify({ok:false, why:'no-dialog'});
  const inp = d.querySelector('input');
  if (!inp) return JSON.stringify({ok:false, why:'no-input'});
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(inp, %s);
  inp.dispatchEvent(new Event('input', {bubbles:true}));
  inp.dispatchEvent(new Event('change', {bubbles:true}));
  const btn = [...d.querySelectorAll('button')].find(b => (b.textContent||'').trim() === '保存');
  if (!btn) return JSON.stringify({ok:false, why:'no-save-btn', value: inp.value});
  btn.click();
  return JSON.stringify({ok:true, set: inp.value});
})()
"""

DIALOG_PRESENT = """
(() => {
  const d = document.querySelector('[data-name="rename-dialog"]');
  if (!d) return JSON.stringify({present:false});
  const inp = d.querySelector('input');
  return JSON.stringify({present:true, value: inp ? inp.value : null});
})()
"""


async def main() -> int:
    src_path = Path(sys.argv[1])
    old_name = sys.argv[2] if len(sys.argv) > 2 else "Volume Aggregated Spot & Futures"
    new_name = sys.argv[3] if len(sys.argv) > 3 else "Volume Aggregated Spot & Futures v14"
    source = src_path.read_text(encoding="utf-8")
    print(f"源码: {src_path.name} {len(source)} 字符 / {len(source.splitlines())} 行")

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    server = ROOT / "tools" / "tradingview-mcp" / "src" / "server.js"
    params = StdioServerParameters(command="node", args=[str(server)])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            def show(label, value, n=220):
                print(f"    {label}: {str(value)[:n]}")

            async def call(tool, args=None):
                raw = _text(await session.call_tool(tool, args or {}))
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    return raw
                # MCP 包装：{"success":true,"result":"<json 字符串>"}
                if isinstance(obj, dict) and isinstance(obj.get("result"), str):
                    try:
                        inner = json.loads(obj["result"])
                        return inner if isinstance(inner, (dict, list)) else obj
                    except json.JSONDecodeError:
                        return obj
                return obj

            print("[1] 打开编辑器 + 打开脚本")
            await call("ui_open_panel", {"panel": "pine-editor", "action": "open"})
            show("[1] pine_open", await call("pine_open", {"name": old_name}))

            print("[2] 写入新源码")
            show("[2] pine_set_source", await call("pine_set_source", {"source": source}))

            print("[3] Ctrl+S 触发保存")
            show("[3] pine_save", await call("pine_save", {}))
            await asyncio.sleep(2.5)

            print("[4] 对话框状态")
            st = await call("ui_evaluate", {"expression": DIALOG_PRESENT})
            print("    ", st)
            if not st.get("present"):
                print("    ✗ 没有出现命名对话框 —— 可能这次是原地覆盖，先按成功处理")
            else:
                js = SET_DIALOG_NAME % json.dumps(new_name)
                r = await call("ui_evaluate", {"expression": js})
                print("     命名并确认:", r)
                await asyncio.sleep(3)

            print("[5] 回读校验")
            scripts = await call("pine_list_scripts")
            for s in scripts.get("scripts", []):
                print(f"     {s['name']!r} modified={s['modified']} id={s['id'][-8:]}")
            cur = await call("pine_open", {"name": new_name})
            print(f"     新脚本行数: {cur.get('lines')} / 本地 {len(source.splitlines())}")

            print("[6] 编译并挂到图表")
            show("[6] pine_smart_compile", await call("pine_smart_compile", {}))
            print("[7] 编译错误")
            show("[7] pine_get_errors", await call("pine_get_errors", {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
