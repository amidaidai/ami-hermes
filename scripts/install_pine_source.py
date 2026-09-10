#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本地 AggVol v14 源码装进 TradingView 已保存脚本（走 MCP stdio，源码不过模型上下文）。

为什么需要它：v14 源码 87KB，无法作为工具参数贴进对话；而且手工粘贴容易截断。
这里直接从磁盘读、直传 MCP，并做安装后校验。

用法: python scripts/install_pine_source.py <本地文件> "<TV脚本名>"
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _text(result) -> str:
    """把 MCP 返回值里的文本抠出来（不同版本包装不一）。"""
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


async def main() -> int:
    src_path = Path(sys.argv[1])
    script_name = sys.argv[2] if len(sys.argv) > 2 else "Volume Aggregated Spot & Futures"
    source = src_path.read_text(encoding="utf-8")
    print(f"本地源码: {src_path.name} {len(source)} 字符 / {len(source.splitlines())} 行")

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    server = ROOT / "tools" / "tradingview-mcp" / "src" / "server.js"
    params = StdioServerParameters(command="node", args=[str(server)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("[1] 打开 Pine 编辑器")
            print("    ", _text(await session.call_tool("ui_open_panel",
                                                          {"panel": "pine-editor", "action": "open"}))[:160])

            print("[2] 打开目标脚本")
            print("    ", _text(await session.call_tool("pine_open", {"name": script_name}))[:200])

            print("[3] 写入新源码（set_source）")
            r = _text(await session.call_tool("pine_set_source", {"source": source}))
            print("    ", r[:400])

            print("[4] 保存（Ctrl+S）")
            r = _text(await session.call_tool("pine_save", {}))
            print("    ", r[:400])

            print("[5] 校验：编辑器里的行数")
            got = _text(await session.call_tool("pine_get_source", {}))
            try:
                inner = json.loads(got) if got.strip().startswith("{") else {}
                cur = inner.get("source", "")
            except json.JSONDecodeError:
                cur = ""
            if cur:
                same = cur.replace("\r\n", "\n").strip() == source.replace("\r\n", "\n").strip()
                print(f"     编辑器 {len(cur.splitlines())} 行 / 本地 {len(source.splitlines())} 行 → "
                      f"{'一致 ✓' if same else '不一致 ✗'}")
                if not same:
                    return 1
            else:
                print("     无法回读编辑器内容（不影响保存）")

            print("[6] 检查编译错误")
            r = _text(await session.call_tool("pine_get_errors", {}))
            print("    ", r[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
