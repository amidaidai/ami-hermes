# Cron 通知路由与 X 情绪 LLM 升级模式

本参考记录棠溪交易系统中定时任务的通知分层原则，适用于 Hermes cron / no_agent / agent cron 的维护和降噪。

## 社区最佳实践映射

从 Grafana / Prometheus Alertmanager / PagerDuty / Datadog / Kentik 的共同原则抽象：

| 原则 | 棠溪任务映射 |
|---|---|
| 告警必须可行动 | Telegram 只发交易机会、关键异常、用户明确想看的每日维护摘要 |
| FYI alerts are trash | “市场平静”“等待信号”“daemon alive”这类状态必须静默 |
| 分组/去重/路由 | 采集类 local 落盘；异常类 Telegram；情绪/雷达走高价值卡片 |
| 增大评估窗口 | 慢变量降频：Dune/稳定币 4h，Deribit 30m，QLib 1h |
| 非紧急走低打扰通道 | 普通采集、因子、复盘、执行桥默认 local |

## 推荐 Telegram 分层

| 层级 | 类型 | Telegram 策略 |
|---|---|---|
| P0 交易警报 | Orion 雷达、X 情绪 LLM、关键位触发 | 发 Telegram |
| P0 运行异常 | BTC daemon 重启、数据新鲜度过期 | 仅异常发 Telegram；健康静默 |
| P1 每日维护 | SkillMCP更新、系统审计、系统备份、BTC关键位同步 | 用户允许发 Telegram |
| P2 数据采集 | Dune、Deribit、COT、清算、稳定币、QLib | local，供分析卡读取 |
| P2 状态心跳 | daemon alive、等待信号、市场平静 | 必须静默 |

## X 情绪：不要只推简单采集表

用户明确反馈：`X情绪刷新太简单了，要llm分析一下`。

推荐架构：

1. no_agent 数据刷新：本地采集，不推 Telegram。
   - 输出：Fear&Greed、CoinGecko Trending/Global、Binance BTC/ETH/SOL/HYPE 24h、Orion候选。
   - 双落盘：`data/x_sentiment_context.json` 和 Hermes data。
2. agent cron LLM 分析：按小时推 Telegram。
   - 脚本 stdout 注入 prompt。
   - LLM 生成短线情绪卡：首行方向 + 多源情绪验证表 + 热门叙事表 + 执行建议表。
3. 如 `x_search` 在 cron 环境不可用或被替换成 `web_search`，卡片必须诚实标注“X直连不可用，本轮用网页/新闻+CoinGecko/F&G/Orion替代”，不能声称 X 实时检索成功。

## 脚本降噪模式

### 健康心跳静默

```python
if alive:
    # stdout 为空：cron 不推送
    return 0
print("BTC daemon restarted ...")
```

### 等待/普通状态静默

```python
if result["status"] in {"no_signal", "quiet"}:
    return 0
print(actionable_event)
```

### 时间戳不参与去重

情绪去重的 hash 不要包含当前时间，否则每次只是 `ts` 变化也会推送。

```python
dedup_key = json.dumps({
    "fear_greed": fg_val,
    "mood": mood,
    "fomo_score": fomo,
    "trending": top,
}, ensure_ascii=False, sort_keys=True)
```

## 验证清单

- `hermes cron list --all`：确认 Telegram 任务只包含 P0/P1。
- `python -m py_compile <changed scripts>`：所有脚本语法通过。
- 健康 watchdog 手动运行输出应为 0 字节。
- 执行桥无信号手动运行输出应为 0 字节。
- 新增 agent cron 后必须 `hermes cron run <job_id> --accept-hooks` 实测一次，并读取 cron output 确认最终卡片格式。