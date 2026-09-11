# Windows NTP Sync for Binance API

## Problem
Binance account endpoints (`get_account_summary`, `get_futures_positions`) return `HTTP 400: Timestamp outside recvWindow` when system clock drifts >1000ms from Binance servers.

## Key Pitfall: git-bash encoding
`w32tm` output is GBK-encoded on Chinese Windows. Running from git-bash/MSYS produces garbled output. Always use PowerShell or cmd.

## Fix Recipe

```powershell
# Step 1: Resync (PowerShell)
powershell.exe -NoProfile -Command "w32tm /resync"

# Step 2: Verify (PowerShell)
powershell.exe -NoProfile -Command "w32tm /query /status"
# Look for: 上次成功同步时间: <recent>
```

## Verification After Fix

```python
# If this returns actual data (not HTTP 400), it's fixed:
mcp_binance_get_account_summary()
```

## Why Some Endpoints Still Work

Simple price endpoints (`get_price`, `get_prices`) have looser timestamp tolerance than account/order endpoints. Don't assume the API is healthy just because price queries succeed — always test with `get_account_summary()`.
