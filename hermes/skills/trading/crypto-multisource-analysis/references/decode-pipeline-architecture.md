# 棠溪 v4.3 行动格解码管线架构

> 最后一次更新: 2026-06-27 · 对应主指标 svp_v10 (3142行) · 行动格 v2

## 架构分层

```
┌──────────────────────────────────────────────────────┐
│  TradingView 图表 (CDP port 9222)                     │
│  ┌──────────────┐  ┌──────────────────┐               │
│  │ 主指标 SVP    │  │ 副指标 Volume     │               │
│  │ 行动格 v2     │  │ Aggregated        │               │
│  │ table.new()   │  │ table.new()       │               │
│  └──────┬───────┘  └──────┬───────────┘               │
│         │  dwgtablecells   │  dwgtablecells            │
└─────────┼──────────────────┼───────────────────────────┘
          │                  │
    ┌─────▼─────┐      ┌─────▼─────┐
    │ MCP 实时   │      │ cron agent│  ← 共享同一 CDP 连接
    │ (手动分析) │      │ (自动缓存) │     (MCP server 独占)
    └─────┬─────┘      └─────┬─────┘
          │                  │
    data_get_pine_tables    data_get_pine_tables
    (study_filter="SVP")    → tv_dmi_cache.json
                            │
    ┌───────────────────────▼──────────────────────────┐
    │  auto_card.py 消费层                               │
    │  ┌─────────────────────────────────────────────┐  │
    │  │ 优先: engine_data._tv_pine (调用方注入)      │  │
    │  │ 回退: data/tv_dmi_cache.json (cron 缓存)    │  │
    │  │       → _parse_tv_dmi_table()               │  │
    │  │       → _apply_tv_dmi_override()            │  │
    │  │       → _parse_tv_sub_table()  (副指标)      │  │
    │  └─────────────────────────────────────────────┘  │
    └──────────────────────────────────────────────────┘
```

## 行动格 v2 行标（2026-06 生产格式）

**主指标(SVP)**: `结论 | 方向 | 进场 | 止损 | 目标 | 核对 | 磁吸↑ | 磁吸↓`

- 等级嵌在 `结论` 中，如 `A多 回踩`、`X 禁追·过热远离`
- **没有** `等级` 或 `处理` 独立行

**副指标(Volume)**: `信号 | 结论 | 高周 | 持仓 | 流向 | 量能 | 爆仓 | 操作`

- 仅加密有效（`isCryptoA` 门控），黄金/外汇自动罢工

## CDP 采集方式

### 方式 1: MCP server (实时 · 手动分析)
```
mcp_tradingview_data_get_pine_tables(study_filter="SVP")
mcp_tradingview_data_get_pine_tables(study_filter="Volume")
```
- ✅ 主 agent 直连，零延迟
- ⚠️ MCP server 独占 CDP → 不能同时另开连接

### 方式 2: fetch_tv_data.cjs (独立 CDP 桥 · 脚本自动)
```
node fetch_tv_data.cjs "BINANCE:BTCUSDT.P"
→ ~/AppData/Local/hermes/data/BTCUSDT.P_tv_data.json
```
- 探测每个 page target 找 `TradingViewApi._activeChartWidgetWV`
- 读 `dwgtablecells` 集合提取行动格 + 从 `结论` 派生等级
- **CDP 冲突时不可用**（MCP server 占着 chart target）

### 方式 3: cron agent (MCP 工具 · 定时缓存)
```
cron: "主+副指标缓存刷新"
→ ~/AppData/Local/hermes/data/tv_dmi_cache.json
```
- 每 2 分钟 agent 调 MCP 工具写缓存
- 缓存包含 `grade/treatment/table_raw/sub_table_raw`
- auto_card 从缓存读取

## 数据流对比 (v4.2 → v4.3)

| 字段 | v4.2 (旧 Data Window 导出) | v4.3 (行动格 v2) |
|---|---|---|
| 等级 | `plot(display=display.data_window)` → `data_get_study_values` | 从 `结论` 行派生: `A多/A空/X/C等待` |
| 进场/止损/目标 | 无 | `data_get_pine_tables` 直接读行 |
| CVD | `plot(CVD Value)` → study_values | 由 `cvd_aggtrades.py` (Binance 逐笔) 独立提供 |
| POC/VAH/VAL | `plot(POC/VAH/VAL Price)` → study_values | 从 `pine_labels` 回收 |
| S VWAP/EMA | `plot()` → study_values | 保留，仍在 study_values |

## CDP 连接故障恢复

症状: `api_available: false` 或 `_activeChartWidgetWV is undefined`

原因: MCP server 连到了非 chart target (如 tooltip iframe)

修复:
```
mcp_tradingview_tv_launch(kill_existing=true)
→ 等 5-8 秒
mcp_tradingview_tv_health_check
→ 确认 api_available: true
```

## 缓存格式 (tv_dmi_cache.json)

```json
{
  "grade": "X",
  "treatment": "禁追·过热远离",
  "cvd_state": "—",
  "background": "观望",
  "position": "等触发",
  "table_raw": ["结论 | ...", "方向 | ...", ...],
  "sub_table_raw": ["信号 | ...", "结论 | ...", ...],
  "updated": "2026-06-27T23:12:00+08:00"
}
```

- `table_raw` 不含 `等级` 行 → auto_card 消费时合成 `等级 | {grade}` 行
- `sub_table_raw` 可能不存在（副指标罢工时）
- 顶层 `grade` 从 `结论` 行派生
