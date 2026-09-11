# 警报去重 & 代理回退可复用模式 (2026-06-29)

## 去重模块

`scripts/alert_dedup.py` — 供所有 no_agent cron 脚本导入。

### 用法

```python
from alert_dedup import dedup_wrapper

output = generate_report()
dedup_wrapper("job_name", output, force_seconds=3600)
# 内容未变 → 静默(cron标记"silent empty")· 变化 → 打印· 超过强制间隔 → 打印
```

### 去重状态文件

`~/AppData/Local/hermes/data/dedup/{job_name}.json`
存储 `{last_hash, last_sent}`，MD5 去重。

### 已注入脚本

| 脚本 | 去重策略 |
|------|------|
| x_sentiment_collector.py | 标准去重·1800s强制 |
| liquidation_collector.py | 爆仓信号不抑制·平常去重 |
| stablecoin_collector.py | 显著变化(>100M)不抑制·平常去重 |
| data_freshness_watchdog.py | 标准去重·3600s强制 |

## 代理回退模式

cron 环境与直接终端环境的代理配置可能不同，导致 SSL 握手超时。
所有面向 no_agent cron 的 HTTP 请求必须使用双策略回退：

```python
def _fetch(url, timeout=10):
    for proxy_handler in [None, {}]:  # proxy → direct
        try:
            if proxy_handler:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxy_handler))
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(url, headers={"User-Agent": "H/1"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:
            continue
    return None
```

已应用于：`orion_screener_radar.py`, `liquidation_collector.py`, `stablecoin_collector.py`, `fallback_chain.py`。
