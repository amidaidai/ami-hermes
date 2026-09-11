#!/usr/bin/env python3
"""Fetch fresh TV MCP data for BTC multi-timeframe analysis."""
import json
import sys
import asyncio
import os
from pathlib import Path

hermes_venv = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))
sys.path.insert(0, str(hermes_venv))

from mcp.client.stdio import stdio_client, StdioServerParameters

DATA_DIR = Path(os.path.expanduser("~/AppData/Local/hermes/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

async def call_tool(session, tool_name, arguments=None):
    result = await session.call_tool(tool_name, arguments or {})
    return result

def parse_result(result):
    if hasattr(result, 'content'):
        texts = []
        for item in result.content:
            if hasattr(item, 'text'):
                texts.append(item.text)
            elif isinstance(item, dict) and 'text' in item:
                texts.append(item['text'])
        return "\n".join(texts)
    elif isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    return str(result)

async def fetch_tf(session, resolution, label):
    print(f"\n=== {label} ({resolution}) ===", flush=True)
    tf_result = await call_tool(session, "chart_set_timeframe", {"timeframe": resolution})
    print(f"TF set: {parse_result(tf_result)[:200]}", flush=True)
    await asyncio.sleep(3)
    
    state = await call_tool(session, "chart_get_state", {})
    state_text = parse_result(state)
    print(f"State: {state_text[:300]}", flush=True)
    
    studies = await call_tool(session, "data_get_study_values", {})
    studies_text = parse_result(studies)
    print(f"Studies: {studies_text[:800]}", flush=True)
    
    ohlcv = await call_tool(session, "data_get_ohlcv", {"summary": True})
    ohlcv_text = parse_result(ohlcv)
    print(f"OHLCV: {ohlcv_text[:500]}", flush=True)
    
    lines = await call_tool(session, "data_get_pine_lines", {})
    lines_text = parse_result(lines)
    print(f"Lines: {lines_text[:500]}", flush=True)
    
    labels = await call_tool(session, "data_get_pine_labels", {})
    labels_text = parse_result(labels)
    print(f"Labels: {labels_text[:500]}", flush=True)
    
    data = {
        "resolution": resolution,
        "label": label,
        "chart_state": state_text,
        "studies": studies_text,
        "ohlcv": ohlcv_text,
        "lines": lines_text,
        "labels": labels_text,
    }
    outfile = DATA_DIR / f"BTCUSDT.P_tv_mcp_{resolution}.json"
    with open(outfile, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {outfile}", flush=True)
    return data

async def main():
    server_dir = Path("D:/Hermes agent/tools/tradingview-mcp")
    server_script = server_dir / "src/server.js"
    if not server_script.exists():
        print(f"Server not found: {server_script}", flush=True)
        return
    
    server_params = StdioServerParameters(
        command="node",
        args=[str(server_script)],
    )
    
    async with stdio_client(server_params) as (read, write):
        from mcp import ClientSession
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("MCP session initialized!", flush=True)
            
            sym_result = await call_tool(session, "chart_set_symbol", {"symbol": "BINANCE:BTCUSDT.P"})
            print(f"Symbol set: {parse_result(sym_result)[:200]}", flush=True)
            await asyncio.sleep(2)
            
            timeframes = [("15", "15m"), ("60", "1h"), ("240", "4h")]
            all_data = {}
            for res, label in timeframes:
                try:
                    data = await fetch_tf(session, res, label)
                    all_data[res] = data
                except Exception as e:
                    print(f"Error {label}: {e}", flush=True)
            
            combined = {"timestamp": asyncio.get_event_loop().time(), "symbol": "BINANCE:BTCUSDT.P", "timeframes": all_data}
            outfile = DATA_DIR / "BTCUSDT.P_tv_mcp_all.json"
            with open(outfile, 'w') as f:
                json.dump(combined, f, ensure_ascii=False, indent=2)
            print(f"\nCombined saved: {outfile}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
