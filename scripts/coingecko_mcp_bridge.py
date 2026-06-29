#!/usr/bin/env python3
"""
CoinGecko MCP Bridge — stdio ↔ Streamable HTTP 协议桥
用于将 CoinGecko 的远程 MCP (Streamable HTTP) 转为 Hermes 可用的 stdio 协议。

用法: python coingecko_mcp_bridge.py [--key KEY]
默认使用 keyless 端点: https://mcp.api.coingecko.com/mcp
如有 Pro/Demo Key: --key 参数或 COINGECKO_DEMO_API_KEY 环境变量
"""

import json
import os
import sys
import urllib.request
import urllib.error

MCP_URL = "https://mcp.api.coingecko.com/mcp"
API_KEY = os.environ.get("COINGECKO_DEMO_API_KEY", "") or "CG-tkuaqHxNbpTQ92HgpvEc4QXY"

def call_mcp(method, params=None):
    """Send JSON-RPC request to CoinGecko MCP via Streamable HTTP."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Hermes/1.0"
    }
    if API_KEY:
        headers["x-cg-pro-api-key"] = API_KEY
    
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"error": {"code": e.code, "message": str(e), "body": body[:200]}}
    except Exception as e:
        return {"error": {"code": -1, "message": str(e)[:200]}}


def main():
    """MCP stdio loop — reads JSON-RPC from stdin, sends to HTTP MCP, writes to stdout."""
    # First, fetch tools list on startup for discovery
    tools_resp = call_mcp("tools/list")
    tools = tools_resp.get("result", {}).get("tools", [])
    
    # Map search_docs results to a simpler tool schema
    mapped_tools = []
    for t in tools:
        mapped_tools.append({
            "name": t["name"],
            "description": t.get("description", ""),
            "inputSchema": t.get("inputSchema", {"type": "object", "properties": {}})
        })
    
    # Send initialize response
    init_resp = {
        "jsonrpc": "2.0",
        "id": "init",
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "coingecko-mcp-bridge", "version": "1.0.0"}
        }
    }
    print(json.dumps(init_resp))
    sys.stdout.flush()
    
    # Main loop
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        
        req_id = req.get("id", 0)
        method = req.get("method", "")
        params = req.get("params", {})
        
        if method == "tools/list":
            result = {"tools": mapped_tools}
            print(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}))
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            
            # Call the remote MCP
            resp = call_mcp("tools/call", {
                "name": tool_name,
                "arguments": tool_args
            })
            
            if "result" in resp:
                print(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": resp["result"]}))
            elif "error" in resp:
                err = resp["error"]
                print(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {
                    "code": err.get("code", -32000),
                    "message": err.get("message", "unknown error")
                }}))
            else:
                print(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": resp}))
        elif method == "ping":
            print(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}))
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}))
        
        sys.stdout.flush()


if __name__ == "__main__":
    main()
