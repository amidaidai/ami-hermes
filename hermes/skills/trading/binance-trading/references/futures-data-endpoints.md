# Binance Futures Data Endpoints (需API签名)

2026-06-17 会话发现：Binance 公开 `fapi/v1/` 端点对多空比和 Taker 数据返回 404，**但 `/futures/data/` 路径可用（需 BINANCE_API_KEY + 签名）**。

## 签名请求模板

```python
import hmac, hashlib, time, json, urllib.request

def signed_get(path, params_extra=""):
    ts = int(time.time() * 1000)
    p = f"{params_extra}{'&' if params_extra else ''}timestamp={ts}"
    sig = hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()
    url = f"https://fapi.binance.com{path}?{p}&signature={sig}"
    req = urllib.request.Request(url, headers={"X-MBX-APIKEY": KEY})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())
```

## 可用端点

| 端点 | 返回 | 质量 | 用途 |
|------|------|------|------|
| `/futures/data/topLongShortAccountRatio` | longAccount, shortAccount, longShortRatio | A级 | 大户多空 |
| `/futures/data/globalLongShortAccountRatio` | 同上 | A级 | 全局多空 |
| `/futures/data/takerlongshortRatio` | buyVol, sellVol, buySellRatio | B级 | Taker买卖·替代CVD |
| `/futures/data/openInterestHist` | sumOpenInterest, sumOpenInterestValue | A级 | OI历史 |
| `/fapi/v1/fundingRate` | fundingRate, fundingTime | A级 | 费率(公开) |
| `/fapi/v1/premiumIndex` | markPrice, indexPrice | A级 | 溢价(公开) |

## 404端点(勿用)

```
/fapi/v1/topLongShortAccountRatio → 404
/fapi/v1/takerlongshortRatio → 404
```

## 解释

- 大户多空>60%偏多 = 拥挤可能杀多; <40%偏空 = 拥挤可能逼空
- Taker buySellRatio>1.1 = 主动买; <0.9 = 主动卖。替代K线估算CVD(C→B级)
- 费率翻转(正↔负)是重要方向信号
