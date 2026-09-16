---
name: hermes-mcp-tool-invocation
description: "For MCP tools: name is tool_search's mcp__<server>__<tool>."
version: 1.0.0
author: 安禾
tags: [mcp, tool-call, tool-search, mcp-tradingview, mcp-binance, integration]
---

# Hermes MCP 工具调用规范 (Multi-MCP Tool Invocation)

## 核心铁律 (2026-08-28 实测)

Hermes 里所有 MCP server 暴露的工具**不在模型面工具列表里**，必须通过 `tool_search` 发现 → `tool_call` 调用。工具名的正确形式是 **`mcp__<server>__<tool>`（双下划线）**，且必须与 `tool_search` 返回的 `name` 一字不差。

## 三种写法的对错

| 写法 | 结果 |
|:---|:---|
| ✅ `tool_call(name="mcp__tradingview__chart_set_timeframe", ...)` | 成功 |
| ❌ `tool_call(name="mcp_tradingview_chart_set_timeframe", ...)` | 报 `'...' is not a deferrable tool` |
| ❌ 直接写函数名 `mcp_tradingview_chart_set_timeframe(...)` | 报 `Tool '...' does not exist` |

**单下划线形式 `mcp_<server>_<tool>`（如 `mcp_tradingview_*`、`mcp_binance_*`）在 Hermes 里根本不存在**。曾在技能文档里出现且看似合理，实测直接失败。不要凭记忆写单下划线前缀。

## 标准流程

1. **先 `tool_search`** 拿确切名字：
   ```
   tool_search(query="tradingview chart timeframe study values")
   ```
   返回里每个 match 的 `name` 形如 `mcp__tradingview__chart_set_timeframe`、`mcp__binance__get_price`。

2. **用 `tool_call` 调用**，`name` 填 tool_search 返回的完整双下划线名；`arguments` 为该工具参数。
   ```python
   tool_call(name="mcp__tradingview__data_get_pine_tables",
             arguments={"study_filter": "SVP"})
   ```

3. MCP 工具都在 `tool_search` 的 deferred catalog 里，**不是 deferrable 的**——`tool_call` 直接可用于已在 deferred catalog 的 MCP 工具。

## 批量与并行：一个 `tool_call` 只装一条本地工具

一次分析要读十几项（行动格、study_values、OHLCV、多空比…）。批量写法有硬约束：

**`tool_call(calls=[...])` 里塞多条本地工具会被整批拒绝**：

```
Local tools require one entry per tool_call; mixed and multi-local batches are not supported.
```

整批丢失，包括里面写对的那几条，白花一轮往返。

**正确写法：同一轮发多个 `tool_call` 块，每块 `calls` 只放 1 条。** 运行时会并发执行，效果等同并行批量读：

```python
# ✅ 同轮 4 个 tool_call 块，每块 1 条 —— 并发执行
tool_call(calls=[{"name": "mcp__tradingview__data_get_pine_tables", "arguments": {"study_filter": "SVP+ICT+VWAP+CVD"}}])
tool_call(calls=[{"name": "mcp__tradingview__data_get_pine_tables", "arguments": {"study_filter": "Volume Aggregated"}}])
tool_call(calls=[{"name": "mcp__tradingview__data_get_study_values", "arguments": {}}])
tool_call(calls=[{"name": "mcp__tradingview__data_get_ohlcv", "arguments": {"summary": True}}])

# ❌ 4 条挤进一个 tool_call(calls=[...]) → 全批被拒，一条都没跑
```

**"只有 connector 类工具能在 `calls` 里批"** —— 本地工具（MCP 工具也算本地）一律一条一块。看到上面那句拒绝文案，不要删掉重试，直接拆块。

## 顺序依赖必须拆轮，不能靠同轮内的先后

同一轮里的多个 `tool_call` 是**并发**的，写在一起的先后不代表执行先后。切换状态再读取（`chart_set_timeframe` → 等指标重绘 → 读数据）必须拆成两轮：

```python
# 轮 1：只发切换
tool_call(calls=[{"name": "mcp__tradingview__chart_set_timeframe", "arguments": {"timeframe": "4h"}}])

# 轮 2：先等等，再读（sleep 不能与要等待的调用同轮）
terminal("sleep 8; echo ok")
# —— 同一轮里同时发下面这组
tool_call(calls=[{"name": "mcp__tradingview__data_get_pine_tables", "arguments": {"study_filter": "SVP"}}])
tool_call(calls=[{"name": "mcp__tradingview__data_get_study_values", "arguments": {}}])
```

各周期等够时间：4h 约 8s、1h 约 6s、15m/5m 约 4s。不等就读到的可能是上一周期的旧值，且**不报错**（同样结构、不同数字），是典型的静默错数据。

## 已知 MCP 前缀对照（以 tool_search 实测为准）

| Server | 前缀 | 例子 |
|:---|:---|:---|
| tradingview | `mcp__tradingview__` | chart_set_timeframe, data_get_study_values, data_get_pine_tables, capture_screenshot |
| binance | `mcp__binance__` | get_price, get_klines, get_open_interest_history |
| financekit | `mcp__financekit__` | crypto_price, correlation_matrix |
| jin10 | `mcp__jin10__` | list_calendar, search_flash |

## 陷阱

- **直接写函数名必然失败**：Hermes 不把 MCP 工具挂成可直接 import 的裸函数。
- **单下划线是历史残留**：老文档写 `mcp_tradingview_*`，实测已废。遇到"not a deferrable tool"就是名字错了，不是工具坏了。
- **工具名不是 deferrable 不代表不能 tool_call**：deferred catalog 里的 MCP 工具能直接 `tool_call`，报"not a deferrable tool / does not exist"只有一种解释——名字写错。
- **一个 `calls` 数组只装一条本地工具**：塞多条会被整批拒（见上一节）。这是并发批量的正确姿势，不是工具坏了。
- **同轮 `calls` 无先后保证**：需要「先切状态再读」的，一律拆成两轮，中间插一次 `terminal("sleep N")`。
- **动手前先看 `linked_files`**：`tradingview-indicator-analysis`、`crypto-multisource-analysis` 这类大 skill 的 `references/` 下可能已经有踩过坑的记录。先扫一遍再试错，比盲调快。

## 验证方法

```python
# 工具名是真还是假，一条命令见分晓
tool_call(name="mcp__tradingview__chart_get_state", arguments={})
# 成功 → 名字正确；报 'is not a deferrable tool' → 你用了单下划线，改双下划线
```

## 参考文件
- `references/zone-alert-agent-cron-pattern.md` — 到价警报 cron 混合模式（零token前置脚本 + agent 到价才分析推送）。**2026-08 修正**：①窄带触发漏检→改穿越检测；②触发后要`deliver=local`+prompt"未触发零输出"，否则 cron 自动投递 agent 每轮"未触发"回复刷屏；③"实时"需 daemon+0.5s 轮询，分钟 cron 不满足。
