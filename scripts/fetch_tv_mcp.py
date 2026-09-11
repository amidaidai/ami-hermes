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

# TANGXI-FIX 2026-08-29: 禁用错误的 hermes venv site-packages 注入（会导致 pydantic_core 二进制不匹配）
# hermes_venv = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))
# sys.path.insert(0, str(hermes_venv))

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

async def get_pine_boxes(session, study_filter=None):
    """Get Pine Script boxes (FVG/OB/breaker zones)."""
    args = {}
    if study_filter:
        args["study_filter"] = study_filter
    result = await call_tool(session, "data_get_pine_boxes", args)
    return result

async def get_pine_tables(session, study_filter=None):
    """Get Pine Script action grid tables."""
    args = {}
    if study_filter:
        args["study_filter"] = study_filter
    result = await call_tool(session, "data_get_pine_tables", args)
    return result

# 20260911：切图去冗余。
# 多个定时任务抢同一张图，每次 set_symbol/set_timeframe 都会让 TV 重新拉数据、
# 重绘指标（用户看到图表闪一下）。大量调用下发的其实已经是当前状态 ——
# 例如 _prepare_xau_main_chart 在 _run_with_retry 刚切完之后又切一遍。
# 已经是目标的就跳过：不改变任何数据语义，只去掉无谓重绘。
SWITCH_STATS = {"symbol_skipped": 0, "symbol_set": 0,
                "timeframe_skipped": 0, "timeframe_set": 0}


async def _current_chart_state(session):
    """读当前图表状态；失败返回 {}（失败时宁可不跳过，绝不误跳过）。"""
    try:
        raw = parse_result(await get_chart_state(session))
        payload = json.loads(raw)
        if isinstance(payload.get("result"), str):
            payload = json.loads(payload["result"])
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


async def set_symbol(session, symbol):
    """切换品种；已经是该品种则跳过（避免无谓重绘）。"""
    want = str(symbol or "").strip()
    if want:
        cur = str((await _current_chart_state(session)).get("symbol") or "").strip()
        if cur and cur.upper() == want.upper():
            SWITCH_STATS["symbol_skipped"] += 1
            return {"success": True, "skipped": True, "symbol": cur}
    SWITCH_STATS["symbol_set"] += 1
    result = await call_tool(session, "chart_set_symbol", {"symbol": symbol})
    return result

async def set_timeframe(session, timeframe):
    """切换周期；已经是该周期则跳过（避免无谓重绘）。"""
    want = str(timeframe or "").strip().upper()
    if want:
        cur = str((await _current_chart_state(session)).get("resolution") or "").strip().upper()
        if cur and _tf_alias(cur) == _tf_alias(want):
            SWITCH_STATS["timeframe_skipped"] += 1
            return {"success": True, "skipped": True, "resolution": cur}
    SWITCH_STATS["timeframe_set"] += 1
    result = await call_tool(session, "chart_set_timeframe", {"timeframe": timeframe})
    return result


def _tf_alias(tf):
    """把 TV 的周期写法归一，避免用不同写法表达同一个周期而误判为『不同』。"""
    tf = str(tf or "").strip().upper()
    return {"D": "1D", "1D": "1D", "W": "1W", "1W": "1W",
            "60": "60", "1H": "60", "240": "240", "4H": "240",
            "15": "15", "15M": "15", "5": "5", "5M": "5",
            "1": "1", "1M": "1", "30": "30", "30M": "30"}.get(tf, tf)

def switch_stats_line():
    """一行汇总本轮图表切换/跳过次数（用于验证去冗余效果）。"""
    s = SWITCH_STATS
    return (f"图表切换 品种(实切{s['symbol_set']}/跳过{s['symbol_skipped']}) "
            f"周期(实切{s['timeframe_set']}/跳过{s['timeframe_skipped']})")


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
