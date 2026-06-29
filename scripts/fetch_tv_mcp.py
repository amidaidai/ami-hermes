#!/usr/bin/env python3
"""
Call TradingView MCP tools via direct stdio MCP protocol to get multi-timeframe data.
Uses the MCP client library from the venv.
"""
import json
import sys
import asyncio
import os
from pathlib import Path

# Add the hermes venv to path
hermes_venv = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))
sys.path.insert(0, str(hermes_venv))

from mcp.client.stdio import stdio_client, StdioServerParameters

DATA_DIR = Path(os.path.expanduser("~/AppData/Local/hermes/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

async def call_tool(session, tool_name, arguments=None):
    """Call an MCP tool and return the result."""
    result = await session.call_tool(tool_name, arguments or {})
    return result

async def get_ohlcv(session, summary=True):
    """Get OHLCV data."""
    result = await call_tool(session, "data_get_ohlcv", {"summary": summary})
    return result

async def get_study_values(session):
    """Get indicator study values."""
    result = await call_tool(session, "data_get_study_values", {})
    return result

async def get_pine_lines(session):
    """Get Pine Script horizontal lines."""
    result = await call_tool(session, "data_get_pine_lines", {})
    return result

async def get_pine_labels(session):
    """Get Pine Script labels."""
    result = await call_tool(session, "data_get_pine_labels", {})
    return result

async def get_chart_state(session):
    """Get current chart state."""
    result = await call_tool(session, "chart_get_state", {})
    return result

async def set_symbol(session, symbol):
    """Set chart symbol."""
    result = await call_tool(session, "chart_set_symbol", {"symbol": symbol})
    return result

async def set_timeframe(session, timeframe):
    """Set chart timeframe."""
    result = await call_tool(session, "chart_set_timeframe", {"timeframe": timeframe})
    return result

def parse_result(result):
    """Extract text content from MCP result."""
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
    """Fetch data for a specific timeframe."""
    print(f"\n=== Fetching {label} ({resolution}) ===", flush=True)
    
    # Set timeframe
    tf_result = await set_timeframe(session, resolution)
    print(f"Set timeframe: {parse_result(tf_result)[:200]}", flush=True)
    await asyncio.sleep(3)
    
    # Get chart state
    state = await get_chart_state(session)
    state_text = parse_result(state)
    print(f"Chart state: {state_text[:200]}", flush=True)
    
    # Get study values
    studies = await get_study_values(session)
    studies_text = parse_result(studies)
    print(f"Studies: {studies_text[:500]}", flush=True)
    
    # Get OHLCV
    ohlcv = await get_ohlcv(session)
    ohlcv_text = parse_result(ohlcv)
    print(f"OHLCV: {ohlcv_text[:300]}", flush=True)
    
    # Get pine lines
    lines = await get_pine_lines(session)
    lines_text = parse_result(lines)
    print(f"Lines: {lines_text[:300]}", flush=True)
    
    # Get pine labels
    labels = await get_pine_labels(session)
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
    
    # Save per-TF file
    outfile = DATA_DIR / f"BTCUSDT.P_tv_mcp_{resolution}.json"
    with open(outfile, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved to {outfile}", flush=True)
    
    return data

async def main():
    # Find the tradingview MCP server command
    # From hermes mcp list: tradingview uses node D:/Hermes agent/tool...
    # Let's find the exact path
    server_dir = Path("D:/Hermes agent/tools/tradingview-mcp")
    server_script = server_dir / "src/server.js"
    
    if not server_script.exists():
        print(f"Server script not found: {server_script}", flush=True)
        return
    
    print(f"Connecting to MCP server: {server_script}", flush=True)
    
    server_params = StdioServerParameters(
        command="node",
        args=[str(server_script)],
    )
    
    async with stdio_client(server_params) as (read, write):
        from mcp import ClientSession
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("MCP session initialized!", flush=True)
            
            # First set symbol
            print(f"\nSetting symbol to BINANCE:BTCUSDT.P...", flush=True)
            sym_result = await set_symbol(session, "BINANCE:BTCUSDT.P")
            print(f"Symbol result: {parse_result(sym_result)[:200]}", flush=True)
            await asyncio.sleep(2)
            
            # Fetch for each timeframe
            timeframes = [
                ("15", "15m"),
                ("60", "1h"),
                ("240", "4h"),
            ]
            
            all_data = {}
            for res, label in timeframes:
                try:
                    data = await fetch_tf(session, res, label)
                    all_data[res] = data
                except Exception as e:
                    print(f"Error fetching {label}: {e}", flush=True)
            
            # Save combined
            combined = {
                "timestamp": asyncio.get_event_loop().time(),
                "symbol": "BINANCE:BTCUSDT.P",
                "timeframes": all_data,
            }
            outfile = DATA_DIR / "BTCUSDT.P_tv_mcp_all.json"
            with open(outfile, 'w') as f:
                json.dump(combined, f, ensure_ascii=False, indent=2)
            print(f"\nCombined data saved to {outfile}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
