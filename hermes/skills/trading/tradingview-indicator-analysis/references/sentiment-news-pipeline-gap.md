# 市场情绪/新闻自动化管道缺口 · 2026-06-17

## 当前状态：手动模式

| 数据 | 来源 | 触发 | 延迟 |
|------|------|------|------|
| 恐慌贪婪 | `api.alternative.me/fng/` | data_gatherer.py 自动 | 日更 |
| X 情绪 | Grok x_search | 手动 ad-hoc | 按需 |
| 金十 Flash | 金十 MCP | 手动 ad-hoc | 实时 |
| CoinDesk | 无 | 无 | ∞ |
| Polymarket | 浏览器手动 | 手动 | 按需 |
| Adanos 情绪 | finance-sentiment skill | 未触发 | ∞ |

## 目标：data_gatherer.py v2.1 自动管道

新增 `sentiment` 字段（写入 source_snapshot）：

```python
snap["sentiment"] = {
    # 已有
    "fear_greed": {
        "value": 45, "classification": "恐惧", "updated": "2026-06-17"
    },
    # 新增
    "x_sentiment": {
        "direction": "bearish",       # bullish/bearish/neutral
        "strength": "medium",         # high/medium/low
        "sample_size": 5,             # 搜索返回条数
        "query": "BTC sentiment crypto today",
        "updated_ts": 1781700000
    },
    # 新增
    "news_headlines": [
        {"source": "jin10", "title": "...", "time": "...", "impact": "利多"},
        {"source": "coindesk", "title": "...", "time": "...", "impact": "中性"}
    ],
    # 新增
    "polymarket": {
        "fed_rate_hold_pct": 99.8,
        "crypto_related_markets": 3,
        "updated_ts": 1781700000
    }
}
```

## 实现步骤

### 1. x_sentiment 采集
```python
# 在 data_gatherer.py 中通过 Hermes 工具调用
# 方法 A：直接 HTTP → xAI API（需 pre-shared key 或 SuperGrok token）
# 方法 B：在 execute_code 中 from hermes_tools import x_search
# 方法 C：cron 脚本独立调 x_search + 写缓存 → data_gatherer 读缓存
# 推荐方法 C：用独立 cron（no_agent: true）每 15min 跑 sentiment_collector.py
```

### 2. news_headlines 采集
```python
# 金十 Flash：mcp_jin10_list_flash() 每次返回最近快讯
# CoinDesk：web_extract("https://www.coindesk.com") 提取首页标题
# 合并去重，取最新 5 条，分类利多/利空/中性
```

### 3. Polymarket 采集
```python
# 优先级：browser_navigate 实查 > Gamma API > 跳过
# 每 30min 更新一次，只拉 crypto + Fed + macro 标签的市场
```

## 情绪→结构冲突告警规则

在行情守望.py process_block() 中新增：

```python
# 读 sentiment 缓存
sent = read_sentiment_cache()
if sent and sent["x_sentiment"]["direction"] != "neutral":
    struct_dir = get_structure_direction()  # 从 DMI 决策表
    if struct_dir != sent["x_sentiment"]["direction"] and sent["x_sentiment"]["strength"] == "high":
        push("⚠️ 结构-情绪冲突：结构{struct} vs X社区严重{sent}——注意极端反转风险")
```

## 代理注意
- x_search 已在 Hermes 配置（`grok-4.20-non-reasoning`）
- `api.x.ai` 已从 NO_PROXY 移除 → 走代理正常
- 如果 data_gatherer 在 cron（no_agent: true）中运行，x_search 不可用，需独立 sentiment_collector cron（含 agent）
