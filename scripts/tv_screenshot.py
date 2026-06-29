#!/usr/bin/env python3
"""
Take a TradingView screenshot via MCP and compose the BTC analysis card.
"""
import json
import sys
import asyncio
import os
from pathlib import Path
import re

hermes_venv = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))
sys.path.insert(0, str(hermes_venv))

from mcp.client.stdio import stdio_client, StdioServerParameters

DATA_DIR = Path(os.path.expanduser("~/AppData/Local/hermes/data"))
SCREENSHOT_DIR = Path("D:/Hermes agent/tools/tradingview-mcp/screenshots")

async def call_tool(session, tool_name, arguments=None):
    result = await session.call_tool(tool_name, arguments or {})
    return result

def parse_text(result):
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

async def main():
    server_dir = Path("D:/Hermes agent/tools/tradingview-mcp")
    server_script = server_dir / "src/server.js"
    
    server_params = StdioServerParameters(
        command="node",
        args=[str(server_script)],
    )
    
    async with stdio_client(server_params) as (read, write):
        from mcp import ClientSession
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("MCP session initialized!", flush=True)
            
            # Take screenshot
            print("Taking screenshot...", flush=True)
            try:
                screenshot_result = await call_tool(session, "capture_screenshot", {})
                screenshot_text = parse_text(screenshot_result)
                print(f"Screenshot result: {screenshot_text[:300]}", flush=True)
                
                # Try to extract the screenshot path
                try:
                    result_json = json.loads(screenshot_text)
                    if isinstance(result_json, dict):
                        screenshot_path = result_json.get('path') or result_json.get('filepath') or result_json.get('screenshot')
                        print(f"Screenshot path: {screenshot_path}", flush=True)
                except:
                    pass
            except Exception as e:
                print(f"Screenshot error: {e}", flush=True)
            
            # Now do all TV data gathering to produce the card
            # First ensure we're on 15m
            print("Setting timeframe to 15m...", flush=True)
            await call_tool(session, "chart_set_timeframe", {"timeframe": "15"})
            await asyncio.sleep(3)
            
            # Get current state for all timeframes
            results = {}
            for tf, label in [("15", "15m"), ("60", "1h"), ("240", "4h")]:
                print(f"Getting {label} data...", flush=True)
                await call_tool(session, "chart_set_timeframe", {"timeframe": tf})
                await asyncio.sleep(3)
                
                # Get study values
                studies = parse_text(await call_tool(session, "data_get_study_values", {}))
                lines = parse_text(await call_tool(session, "data_get_pine_lines", {}))
                labels = parse_text(await call_tool(session, "data_get_pine_labels", {}))
                
                results[tf] = {"studies": studies, "lines": lines, "labels": labels}
            
            # Output all results as JSON
            print("\n=== ALL DATA ===", flush=True)
            print(json.dumps(results, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    asyncio.run(main())
