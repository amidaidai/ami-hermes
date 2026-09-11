# Binance HMAC 签名端点速查 v1.0

◷ 2026-06-21

## 端点路径（正确 vs 错误）

| 功能 | ❌ 错误路径 | ✅ 正确路径 | 需要签名 |
|------|-----------|-----------|---------|
| K线 | fapi/v1/klines | fapi/v1/klines | 否（public） |
| Taker买卖比 | fapi/v1/takerlongshortRatio | **futures/data/takerlongshortRatio** | **是（HMAC）** |
| 多空比 | fapi/v1/globalLongShortAccountRatio | **futures/data/globalLongShortAccountRatio** | **是（HMAC）** |
| OI | fapi/v1/openInterest | fapi/v1/openInterest | **是（HMAC）** |
| Funding | fapi/v1/fundingRate | fapi/v1/fundingRate | 否（public可用） |

## HMAC 签名实现

```python
def _binance_sign(params: dict, secret: str) -> str:
    import hmac, hashlib, urllib.parse
    query = urllib.parse.urlencode(params)
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
```

用法：
```python
ts = int(time.time() * 1000)
params = {"symbol": sym, "period": "5m", "limit": 1, "timestamp": ts}
params["signature"] = _binance_sign(params, secret)
headers = {"X-MBX-APIKEY": api_key}
requests.get(f"{base}/futures/data/takerlongshortRatio", params=params, headers=headers)
```

## 回退链

1. 有 API Key → HMAC 签名端点（A级数据）
2. 无 API Key → public 端点（B级数据）
3. 两者都失败 → 标注 N/A

Key 存储：`hermes/secrets/binance.json` → `{"api_key": "...", "secret_key": "..."}`
