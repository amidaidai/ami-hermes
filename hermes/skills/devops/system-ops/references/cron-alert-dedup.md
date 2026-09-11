# Cron 告警去重模块

## 模块位置

`scripts/alert_dedup.py` — 可被所有 no_agent cron 脚本导入使用。

## 核心接口

```python
from alert_dedup import should_send, dedup_wrapper

# 判断是否发送：内容hash与上次相同则跳过
if should_send("job_name", content, force_every_seconds=3600):
    print(content)

# 便捷包装：自动处理 print 与否
dedup_wrapper("job_name", content, force_seconds=1800)
```

## 去重逻辑

1. 计算 `md5(content)` → 与上次比较
2. 内容变化 → 立即发送，更新 hash
3. 内容相同但超过 `force_every_seconds` → 强制发送（防止长期静默）
4. 内容相同且在间隔内 → 静默跳过（不 print，cron 标记为 "silent"）

## 状态存储

`~/AppData/Local/hermes/data/dedup/{job_name}.json` → `{"last_hash": "...", "last_sent": timestamp}`

## 分级策略

不同任务应有不同的强制间隔和触发逻辑：

| 任务类型 | 强制间隔 | 特殊规则 |
|----------|:------:|------|
| 情绪/因子 | 1800s(30min) | 内容变化才发 |
| 清算压力 | 1800s | 爆仓信号**始终发送** |
| 稳定币 | 3600s(1h) | 变化 > $100M **始终发送** |
| 数据新鲜度 | 3600s | 有告警时才发（默认静默） |

## 已注入脚本

- x_sentiment_collector.py
- liquidation_collector.py
- stablecoin_collector.py
- data_freshness_watchdog.py

## 新建 cron 时

所有面向 TG 推送的 no_agent 脚本应使用 dedup_wrapper 替代 `print()`，避免市场平静时重复推送刷屏（alert fatigue）。
