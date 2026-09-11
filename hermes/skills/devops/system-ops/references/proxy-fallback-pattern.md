# Cron HTTP请求代理回退模式

## 问题

cron环境与直接终端环境的代理配置可能不同，导致no_agent cron脚本中的HTTP请求在cron中SSL握手超时或连接失败。

## 根因

Windows系统的代理设置在cron子进程环境中可能不继承或部分继承。`urllib.request.urlopen()` 默认使用系统代理，若cron无代理配置则无法访问需要代理的API；若有代理但目标API IP被代理拦截则需直连。

## 解决方案：双策略回退

两种回退策略，按复杂度递增：

### 策略A：内联双策略（单文件、零依赖）

```python
import urllib.request, json

def _fetch(url, timeout=10):
    """代理回退HTTP GET — cron与直接环境通用"""
    for proxy_handler in [None, {}]:
        # None = 使用系统代理，{} = 直连
        try:
            if proxy_handler:
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler(proxy_handler))
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(url, headers={"User-Agent": "H/1"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:
            continue
    return None  # 所有策略都失败
```

### 策略B：多源回退链（fallback_chain.py）

当数据可从多个API获取时，使用三级回退链：

```python
from fallback_chain import fallback_fetch, safe_fetch_crypto, safe_fetch_gold

# 自定义回退链
result = fallback_fetch([
    {"name": "primary",   "url": "https://api1.example.com/data", "timeout": 8},
    {"name": "secondary", "url": "https://api2.example.com/data", "timeout": 10},
], cache_key="my_data.json", cache_ttl=300)

# 便捷函数（预置回退链）
result = safe_fetch_crypto("BTCUSDT")  # Binance → CoinGecko → cache
result = safe_fetch_gold()             # Yahoo → gold-api → cache
result = safe_fetch_fx("EURUSD")       # Yahoo → exchangerate → cache
```

## 已应用位置

| 脚本 | 策略 | 日期 |
|------|:--:|------|
| orion_screener_radar.py | A: 内联双策略 | 2026-06-29 |
| liquidation_collector.py | A: 内联双策略 | 2026-06-29 |
| stablecoin_collector.py | A: 内联双策略 | 2026-06-29 |
| x_sentiment_collector.py | A: 内联双策略 | 2026-06-29 |
| qlib_factors.py | A: 内联双策略 | 2026-06-29 |
| fallback_chain.py | B: 多源回退链 | 2026-06-29 |

## 创建新cron脚本时

所有面向no_agent cron的Python脚本的HTTP请求必须使用策略A。不要直接用 `urllib.request.urlopen()`。如果数据可从多个API获取，用策略B预置回退链防止单源被封后静默失败。
