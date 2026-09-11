# Binance API Signed Request Pattern

## Problem

Binance API signed endpoints (e.g. `GET /api/v3/account`) return `{"code":-1022,"msg":"Signature for this request is not valid."}` even when `BINANCE_API_KEY` and `BINANCE_SECRET_KEY` are correctly configured in the Hermes `.env`.

## Root Cause

Binance Secret Keys are **base64-encoded strings**, not raw ASCII. The HMAC-SHA256 signature must be computed on the **decoded bytes**, not the raw string.

64-character base64 secrets → 48 bytes after decoding.

## Fix

```python
import hmac, hashlib, base64
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import json, time

# Load from Hermes env (already set by Hermes at startup)
API_KEY = os.getenv("BINANCE_API_KEY", "").strip()
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "").strip()

# Decode the base64 secret
sec_bytes = base64.b64decode(SECRET_KEY)

# Sync server time to avoid -1021 timestamp error
t0 = json.load(urlopen(Request(
    "https://api.binance.com/api/v3/time",
    headers={"User-Agent": "Anhe/1.0"}
)))["serverTime"]

params = {"timestamp": t0, "recvWindow": 10000}
query = urlencode(params)
signature = hmac.new(sec_bytes, query.encode("utf-8"), hashlib.sha256).hexdigest()

url = f"https://api.binance.com/api/v3/account?{query}&signature={signature}"
req = Request(url, headers={
    "X-MBX-APIKEY": API_KEY,
    "User-Agent": "Anhe/1.0",
    "Accept": "application/json",
})
with urlopen(req, timeout=20) as r:
    data = json.load(r)
```

## Diagnostic Steps (in order)

| Error Code | Meaning | Fix |
|---|---|---|
| `-1022` | Invalid signature | Ensure base64 decode + HMAC-SHA256 |
| `-1021` | Timestamp outside recvWindow | Sync with `/api/v3/time`, use `recvWindow=10000` |
| `-1131` | recvWindow > 60000 | Keep recvWindow ≤ 50000 |
| `400` (no body) | Bad request format | Check headers, URL encoding |

## Still Failing After Fix?

If `-1022` persists after base64 decode + server time sync:
1. Log into Binance → API Management
2. Verify the API Key has `Enable Reading` checked
3. Check IP whitelist includes this machine's public IP
4. Re-copy the Secret Key (ensure 64 chars, no whitespace, no truncation)
