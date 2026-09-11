# Orion Screener 双策略代理修复

## 问题

Orion全市场雷达 cron（ef4cf5f7cd24）持续失败：`Script exited with code 1 stdout: [ERROR] Orion Binance data fetch failed - API returned empty`

直接测试 `python scripts/orion_screener_radar.py` 返回 exit=0 正常，但 cron 环境返回空。

## 根因链

1. 原始 `fetch_orion("")` → Orion API 不传 exchange 参数时返回空 → 改为 `fetch_orion("binance")`
2. 修复后直接测试通过，但 cron 环境仍然失败
3. 发现：cron 子进程可能不继承代理环境变量（`HTTPS_PROXY=http://127.0.0.1:7897`），而 `screener.orionterminal.com` 不在 `NO_PROXY` 列表中
4. 也不排除 cron 环境有代理而直接环境无代理的反向情况

## 最终修复（双策略回退）

```python
def fetch_orion(exchange=""):
    url = f"{API_BASE}/screener"
    if exchange: url += f"?exchange={exchange}"
    
    strategies = [
        # Strategy 1: Use system proxy (may fail in cron without proxy env)
        (None, "proxy"),
        # Strategy 2: Direct connection (may fail if network requires proxy)  
        (urllib.request.ProxyHandler({}), "direct"),
    ]
    
    for proxy_handler, strategy in strategies:
        try:
            if proxy_handler:
                opener = urllib.request.build_opener(proxy_handler)
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with opener.open(req, timeout=15) as r:
                tickers = json.loads(r.read()).get("tickers", [])
                if tickers:
                    return tickers
        except Exception:
            pass
    
    return []
```

## 关键教训

- cron 子进程的网络环境与直接终端可能不同（代理、SSL证书、DNS）
- 对外部 API 调用使用双策略（代理优先→直连回退）覆盖两种环境
- 不要假设 `urllib.request.urlopen()` 在所有环境下的行为一致
- 修复后需验证 `python scripts/orion_screener_radar.py` exit=0 且产出完整分析卡
