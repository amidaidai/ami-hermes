---
name: social-data-mcp
description: "Social Media & News Data MCP Skills — Twitter/X data API, crypto news, argumentation markets, social sentiment analysis"
version: 1.0.0
author: Hermes Agent
tags: [social-media, twitter, news, sentiment, mcp, api]
---

# Social Data & News MCP Skills

Access social media data, news feeds, and sentiment analysis through MCP servers and APIs.

## 🥇 Primary Tool: x_search (xAI Grok, built-in)

**x_search** is the primary mechanism for X/Twitter data — it's built into Hermes, requires no MCP server configuration, and is powered by xAI Grok. Use it for crypto sentiment, narrative tracking, KOL monitoring, and event detection.

### Setup
```bash
hermes auth add xai-oauth
# Or set XAI_API_KEY in .env
```
Once authorized, the `x_search` tool is automatically available in all sessions and LLM cron jobs.

### Crypto Sentiment Query Patterns

| Context | Query | Notes |
|---------|-------|-------|
| Overall market | `"crypto market sentiment BTC ETH"` | Broad sentiment, includes F&G discussion |
| BTC direction | `"Bitcoin ETF crypto bearish bullish"` | ETF flow + directional debate |
| SOL / altcoin | `"Solana crypto sentiment"` | Replace with any coin name |
| Specific event | `"TAIKO bridge exploit sentiment"` | Event-driven reaction |
| Major news/panic | `"BTC crash liquidation"` | Panic/capitulation detection |

### Tips
- Set `from_date` / `to_date` to limit recency (default searches last ~7 days)
- Use `enable_image_understanding=true` for meme/chart analysis
- Always cite results with inline references to X posts
- x_search returns LLM-summarized answers with citations, not raw tweet dumps

### LLM Cron Jobs: Critical Instruction

**When an LLM cron job needs X data, its prompt must explicitly mention `x_search` by name.** Without an explicit instruction, the LLM may not realize the tool is available and will fall back to web_search or skip X entirely. Always include a line like:

> You MUST use the `x_search` tool (xAI Grok-powered) to search X/Twitter for real discussion. This is the primary data source.

**Pitfall: literal `\n` in cron prompts.** The `cronjob(action='update', prompt="...")` API treats `\n` as literal characters, not newlines. Write prompt text with actual line breaks (e.g. Python triple-quoted strings). If the LLM responds with only a skeleton placeholder like "报告已生成并自动投递" instead of the full analysis, check for escaped newlines in the prompt.

**自包含原则.** Cron 运行在隔离会话中，prompt 必须完整自包含：任务描述 + 输出格式模板 + 可用工具列表 + 搜索关键词 + 降级路径。

### Degradation Path
If `x_search` returns no results or errors:
1. Fall back to `web_search site:twitter.com "query"` 
2. Label the source as "web search (X degraded)" in the output

## Secondary Tools (MCP-based)

### OpenTwitter MCP
- Twitter/X data access:
  - User profiles and metadata
  - Tweet search by keywords
  - User tweet history
  - Follower events and trends
  - Deleted tweet detection
  - KOL (Key Opinion Leader) followers
- **Not needed if x_search is working** — only configure for specialized Twitter API access
- Install: `~/.hermes/config.yaml` MCP server config required
- Requires: Twitter API credentials (separate from xAI OAuth)

### OpenNews MCP
- Crypto news search with AI ratings
- Trading signals from news analysis
- WebSocket live feeds for real-time updates
- Filter by keyword, coin, or source
- Install: `npx @heurist-network/skills add opennews-mcp`

### Heurist Mesh Social
- Twitter/X sentiment analysis (alternative to x_search)
- Install: `npx @heurist-network/skills add heurist-mesh`

### Argue.fun
- Argumentation markets
- AI agents debate, bet, and win
- Multi-LLM jury for outcome resolution
- Web: argue.fun

### Unusual Whales API
- Unusual options flow data
- Dark pool prints
- Market tide indicator
- Stock Greek exposure
- Install: `npx @heurist-network/skills add unusual-whales-api`

## Output Format: Table-Heavy Sentiment Card

X 情绪 LLM 分析（cron c6ad11110a80）的输出格式：

### 核心原则：重表格，轻文字

禁止段落式分析输出。全部信息用表格承载。

### 格式结构

首行：↓/↑/○/× + 一句话总览 + 中文时间（2026年6月30日17：17）

然后直接跟 **一张多源验证表**：

```
| 来源 | 观察 | 交易含义 |
|------|------|----------|
| x_search BTC | 恐惧蔓延，KOL分歧 | 空头主导，极值警戒 |
| x_search ETF | 八连流出$1.7B | 增量缺失 |
| Fear & Greed | 15 极端恐惧 | 历史低位 |
| x_search SOL | 谨慎偏多 | 弱于预期 |
```

可选第二张 **操作建议表**（品种 | 方向/策略 | 关键位 | 风控）。

末尾一行成交价参考：BTC $xx / ETH $xx / SOL $xx

禁止：段落展开解释、前置说明、分析框架描述、编号①②③、装饰分隔线。

### 语言和格式约束

- 时间用中文格式与全角冒号：2026年6月30日17：17
- 第一行用 ↑↓○× 开头，不用额外格式修饰
- 控制在 700 字以内
- 来源列第一行必须是 x_search 结果

### Pitfall：LLM 倾向在表格后再加一段"总结"或"解读"——禁止。表格本身就是总结，段落只会增加阅读负荷。

## Workflow

1. **For X/Twitter data**: use `x_search` (Grok, built-in, no config) — this is the default
2. For crypto news + signals: use OpenNews MCP
3. For alternative X sentiment: use Heurist Mesh Social
4. For options market data: use Unusual Whales
5. For argumentation markets: use Argue.fun
6. **Fallback**: web_search site:twitter.com when x_search fails
