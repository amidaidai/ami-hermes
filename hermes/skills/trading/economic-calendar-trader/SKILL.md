---
name: economic-calendar-trader
description: "财经日历与事件交易 — NFP/CPI/FOMC/央行利率/GDP 等关键数据发布前的行情准备、波动率预期、交易准备清单。对接金十 MCP + Binance MCP + Yahoo Finance"
version: 1.0.0
author: 安禾
tags: [calendar, NFP, FOMC, CPI, economic-data, news-trading, events, macro]
---

# 财经日历 — Economic Calendar Trader

关键经济数据发布前的交易准备——日历检查→预期偏差→波动率预估→预案策略。

## 核心数据源

| 数据 | 来源 | 命令 |
|------|------|------|
| 财经日历 | 金十 MCP | `list_calendar()` — 当前周全部事件 |
| 快讯 | 金十 MCP | `list_flash()` — 实时新闻快讯 |
| BTC 行情 | Binance MCP | `get_price()`, `get_klines()` |
| XAU 行情 | 金十 MCP | `get_quote(code="XAUUSD")` |
| 宏观搜索 | web | `web_search("CPI June 2026 consensus")` |

## 事件检查流程

### ① 拉本周日历
```bash
# 金十 MCP — 本周全部事件
金十: list_calendar()
# 输出: 日期/时间/国家/事件/前值/预期/重要性
```

### ② 识别关键事件

| 事件 | 时间 | 影响品种 | 波动率 |
|------|------|---------|--------|
| **FOMC利率决议** | 每月 | BTC/XAU/USD/Yield | ⭐⭐⭐⭐⭐ |
| **非农(NFP)** | 每月第一个周五 | BTC/XAU/FX | ⭐⭐⭐⭐⭐ |
| **CPI** | 每月中 | BTC/XAU/FX | ⭐⭐⭐⭐ |
| **PCE** | 月底 | BTC/XAU | ⭐⭐⭐ |
| **GDP** | 季末 | FX/USD | ⭐⭐⭐ |
| **央行利率** | 按日程 | 对应货币对 | ⭐⭐⭐⭐ |
| **PMI/零售** | 月中 | FX | ⭐⭐ |

### ③ 预期偏差分析
```python
# 预期 vs 前值 gap
# 金十日历含前值和预期值
calendar = list_calendar()
for event in calendar:
    if event.importance == "high":
        gap = abs(event.forecast - event.previous) / abs(event.previous)
        if gap > 0.1:  # 偏差>10%
            print(f"⚠ {event.name}: 预期{event.forecast} vs 前值{event.previous}")
```

### ④ 波动率预期
```python
# NFP/FOMC 前 30 分钟波动率通常会骤降（假收敛）
# 数据后 3-5 分钟出现最大波动
# BTC 重大事件通常 10-30% 波动
# XAU 通常 1-3%
# FX 通常 50-150 pips
```

## 交易准备清单

### 数据公布前（-24h）
- [ ] 检查日历，标记高重要性事件
- [ ] 了解市场预期（搜索共识预测）
- [ ] 预估波动方向（偏鹰/偏鸽预判）
- [ ] 确认当前持仓是否需减仓
- [ ] 设置预警（Binance MCP price alert）

### 数据公布前（-1h）
- [ ] 减仓/平仓（非必要不过夜）
- [ ] 确认止损已设置且合理
- [ ] 准备好 Plan A/B

### 数据公布时
- [ ] 等待 3-5 分钟让波动稳定（假突破常见）
- [ ] 观察：最初5min方向 + 回收还是延续
- [ ] 确认做单：方向 + 量能 + 结构位 + 风控

## 各品种事件敏感度

| 品种 | 最敏感事件 | 典型波动 |
|------|-----------|---------|
| BTC | FOMC > CPI > NFP | 3-10%（核心事件）|
| XAU | NFP > FOMC > CPI | 1-3%（CPI超预期0.5%+ ~ 20-40美元）|
| EURUSD | ECB > NFP > CPI | 50-150 pips |
| USDJPY | FOMC > NFP > 日本央行 | 50-120 pips |
| S&P 500 | FOMC > CPI > NFP | 1-3% |

## 注入分析卡

```
④ 宏观：
本周焦点 — 周五 NFP（预期240K vs 前值175K → 偏差+27% ⚠）
FOMC 下周三 · 市场定价降息25bp概率68%
数据前波动率可能收缩 → 警惕数据后爆发
→ 建议：数据前减仓至半仓
```

## 陷阱
- **预期偏差才是驱动的核心**，不是数据绝对值
- NFP 初值经常被大幅修正（后两个月修），不要追 NFP 趋势
- FOMC 的声明措辞比利率决议本身更重要
- 中国PMI对BTC的影响被低估（全球需求指标）
- 金十日历为北京时间，需换算到 UTC
