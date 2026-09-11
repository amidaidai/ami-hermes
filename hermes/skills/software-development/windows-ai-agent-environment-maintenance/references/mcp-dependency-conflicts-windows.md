# MCP Server Python Dependency Conflicts on Windows

## Binance MCP: `websockets` Version Conflict

### Symptom
Binance MCP (`mcp_servers.binance` in `config.yaml`) configured as `enabled: true` but tools never appear in the agent's available tool list. Manual launch crashes with:
```
ImportError: cannot import name 'WebSocketClientProtocol' from 'websockets'
```

### Root Cause
`python-binance==1.0.37` requires `websockets<14.0`, but Hermes Desktop ships `websockets==15.0.1`. When Hermes launches the MCP subprocess in its venv, the import chain `binance.client.Client → binance/__init__.py → binance.async_client → binance.ws.websocket_api` triggers the websocket import, which crashes on the version mismatch.

### Wrong Fixes (Don't Do These)
- ❌ Downgrade websockets — Hermes itself needs 15.0.1, downgrading breaks Hermes
- ❌ `pip install websockets==13.1` — creates a permanent version conflict with Hermes
- ❌ Delete and reinstall — the file lock from Hermes process prevents writes

### Correct Fix: Eliminate `python-binance` Dependency
The binance MCP server (`tools/binance-mcp/server.py`) only uses REST API calls — it never opens websockets. The crash comes from the transitive import chain, not from real usage. The fix is to rewrite the MCP to use pure `urllib.request` REST calls, dropping `from binance.client import Client` entirely.

The v1.1 extension in `server.py` already does this correctly for signed futures endpoints (`_signed_futures_get`). The same pattern should be applied to the remaining REST endpoints (`get_price`, `get_klines`, `get_balance`, `get_account_summary`, etc.).

### Pattern: Drop `Client` for Raw REST
```python
# Before (imports python-binance, triggers websocket crash):
from binance.client import Client
c = Client(api_key, secret_key)
ticker = c.get_symbol_ticker(symbol="BTCUSDT")

# After (pure urllib, no python-binance dependency):
import urllib.request, json
def _public_get(path):
    url = f"https://api.binance.com/api/v3/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())
ticker = _public_get("ticker/price?symbol=BTCUSDT")
```

### Affected Endpoints to Rewrite
- `get_price()` — `GET /api/v3/ticker/price`
- `get_prices()` — `GET /api/v3/ticker/price` (full)
- `get_klines()` — `GET /api/v3/klines`
- `get_balance()` — `GET /api/v3/account` (signed)
- `get_account_summary()` — combines spot `GET /api/v3/account` + futures `GET /fapi/v2/account`
- `get_futures_positions()` — `GET /fapi/v2/positionRisk`
- `get_open_orders()` — `GET /api/v3/openOrders` + `GET /fapi/v1/openOrders`
- `cancel_order()` — `DELETE /api/v3/order` + `DELETE /fapi/v1/order`
- `get_symbol_info()` — `GET /api/v3/exchangeInfo?symbol=X`

## Finance MCP: Module Not Installed

### Symptom
Finance MCP (`mcp_servers.finance` in `config.yaml`) tools never appear. Config uses:
```yaml
command: C:/Users/Administrator/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe
args: ["-c", "from finance_mcp.server import main; import asyncio; asyncio.run(main())"]
```

### Root Cause
`finance_mcp` is not installed in the Hermes venv. `pip list | grep finance_mcp` returns nothing.

### Fix
Install the package, or if it's a local module, ensure it's in PYTHONPATH:
```bash
pip install finance-mcp
# or if local:
cd D:/Hermes agent/tools/finance-mcp && pip install -e .
```

## General MCP Dependency Debugging Checklist

1. Check `mcp_servers.<name>.enabled: true` in config.yaml
2. Check the server file exists at the specified path
3. Try launching manually: `python <server.py>` — any import errors will surface
4. Check pip packages: `pip list | grep <module>`
5. If Hermes-required package conflicts with MCP dependency → rewrite MCP to avoid the conflicting import
6. Never downgrade Hermes-required packages to accommodate an MCP server
