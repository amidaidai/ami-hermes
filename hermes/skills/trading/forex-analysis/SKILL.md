---
name: forex-analysis
description: "外汇交易分析 — EURUSD、GBPJPY、USDJPY 等主要外汇对的技术分析、基本面日历、央行政策、相关性扫描。基于 TradingView MCP 实时数据 + 金十财经日历"
version: 1.0.1
author: 安禾
tags: [forex, FX, EURUSD, GBPJPY, USDJPY, trading, forex-analysis, TV-MCP, cockpit-v9.5]
---

# 外汇分析 — Forex Analysis

主流外汇对（EURUSD, GBPJPY, USDJPY, GBPUSD, USDCHF, AUDUSD, NZDUSD, USDCAD）的多周期技术分析。

## 核心数据源

| 数据 | 来源 | 命令 |
|------|------|------|
| K线/指标 | TV MCP | `chart_set_symbol("FX:EURUSD")` → `data_get_ohlcv(count=100)` |
| 基本面 | 金十 MCP | `list_calendar()` 财经日历 |
| 央行利率 | 搜索 | `web_search("ECB rate decision June 2026")` |
| 相关性 | yfinance | `stock-correlation` skill |

## 快速分析流程

### ① TV 五层周期 + 截图

外汇统一五层全周期：D→4h→1h→15m→5m。主执行周期=15m（截图在15m）。

```bash
# 切换到外汇对
TV: chart_set_symbol("FX:EURUSD")

# 五层全周期（必须依次，不可跳过）：
# D日线 → 读 OHLCV summary（宏观结构背景），等15-30s
TV: chart_set_timeframe("D")
TV: data_get_ohlcv(summary=True)
# 4h → 读结构+关键位，等8-12s
TV: chart_set_timeframe("240")
TV: data_get_ohlcv + data_get_pine_labels + data_get_pine_lines
# 1h → 同上，等8s
TV: chart_set_timeframe("60")
# 15m → 主执行+截图，等15-30s
TV: chart_set_timeframe("15")
TV: ui_fullscreen → capture_screenshot(region="full")
# 5m → 微观确认，等15-30s
TV: chart_set_timeframe("5")
TV: data_get_ohlcv

# 最后切回15m主周期
TV: chart_set_timeframe("15")
```

### ② 关键位扫描（五层继承）
```python
# 通过 TV MCP 读取各周期关键位
# D日线 → OHLCV summary（周高/周低、前日高/低）
# 4h → pine_labels + pine_lines（SVP关键位：VAH/VAL/POC/DO）
# 1h → 同上（结构确认，EMA排列）
# 15m → 主执行周期（行动格+截图）
# 5m → 微观确认
# 提取: 周高/周低、前高/前低、EMA50/200、Pivot 点
```

### ③ 日历事件检查
```bash
# 金十 MCP 财经日历
TV 或 Jin10: list_calendar()
# 检查本周是否有: NFP, CPI, 央行利率决议, GDP
```

## 外汇关键分析维度

### 技术面
- **趋势**：EMA50 vs EMA200 排列、ADX(14) 强度
- **关键位**：周高/周低、前日高/低、整数关口、Pivot点
- **动量**：RSI(14) 超买/超卖、MACD 交叉
- **波动率**：ATR(14) 日波动范围

### 基本面
- **利率差**：两国央行利率差异（Carry Trade 基础）
- **经济数据**：NFP/CPI/GDP/零售销售/PMI
- **央行态度**：鹰派/鸽派/中性（ECB/Fed/BOJ/BOE）

### 外汇专属特性
- 外汇是 **24h 市场**（悉尼→东京→伦敦→纽约）
- **流动性时段**：伦敦开盘(UTC 8:00)、纽约开盘(UTC 13:00)、东京开盘(UTC 0:00)
- **相关性**：EURUSD↔USDCHF（负相关）、GBPUSD↔EURUSD（正相关）
- **非农/CPI 前后波动率暴增** 5-10 倍正常水平

## TV 常用代码

| 外汇对 | TV 代码 | 特性 |
|--------|---------|------|
| 欧元/美元 | `FX:EURUSD` | 流动性最大，点差最低 |
| 英镑/日元 | `FX:GBPJPY` | 波动最大，隔夜利息高 |
| 美元/日元 | `FX:USDJPY` | 利率敏感，与美债收益正相关 |
| 英镑/美元 | `FX:GBPUSD` | Cable，伦敦盘活跃 |
| 澳元/美元 | `FX:AUDUSD` | 商品货币，与中国相关 |
| 美元/加元 | `FX:USDCAD` | 石油货币 |
| 美元/瑞郎 | `FX:USDCHF` | 避险货币 |
| 纽元/美元 | `FX:NZDUSD` | 商品货币，农业相关 |

## 集成到棠溪格式

```markdown
◷ Tue · EURUSD · 15m · DXY 104.5
③ 现价 1.0845 · 高 1.0872 · 低 1.0820
关键位 R2 1.0900 · R1 1.0865 · S1 1.0820 · S2 1.0785
趋势 EMA50<EMA200 · ADX 18 → 震荡
日历 NFP Friday · Fed-speak 今天
→ Plan A: ↑做多 突破 1.0865 → 1.0900 SL 1.0820
→ Plan B: ↓做空 跌破 1.0820 → 1.0785 SL 1.0865
风控 1% · 数据前减仓
```

## 陷阱
- 外汇点差在非活跃时段（亚洲凌晨）会扩大 2-3 倍
- 非农/CPI 前 30 分钟波动率骤降（假收敛），数据后瞬间爆发
- TV MCP 切换外汇对时记得先停用 Pine 指标（不同品种参数不同）
