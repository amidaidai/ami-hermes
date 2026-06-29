# 棠溪分析卡 · 主模板 v9.6（表格驾驶舱 · SVP v10 · 多资产）

定位：这是棠溪交易驾驶舱的权威输出模板。旧 v8.0 叙事卡仅作历史参考；正式手动分析、自动分析卡、告警复盘均以本文件为准。

## 权威铁律

1. 每次正式分析前必须先读取本文件与 `references/tangxi-trading-cockpit.md`。
2. 首行必须是新 TradingView 全屏截图（加密/XAU 必须 full，含价格轴 + CVD/OI/副指标窗格）。
3. 时间一律北京时间中文格式：`2026年6月29日21：30`，不用 UTC，不用 BJT 后缀。
4. 先给结论，不让用户自己猜；首段 3-5 行浓缩。
5. 正文采用 Markdown 表格，不使用长装饰分隔线，不使用编号①②③。
6. 状态只允许：`A可执行` / `B等确认` / `C轻仓试探` / `X禁做观察`。
7. TV SVP v10 是主驾驶：行动格、关键位、VWAP/EMA/CVD/OI、labels/lines/Data Window 优先。
8. Binance / Deribit / Dune / X / 宏观 / COT 是验证层，不覆盖 TV 主结构，只负责增强或降级。
9. R:R < 1:2 不得输出为可执行方案；只能列为观察或重算。
10. 单笔风险≤1%，硬上限 10U；风控状态过期则降级。
11. DMI/行动格等级是参考，不单独决定方向；方向来自五因子投票：VWAP位置、CVD压力、EMA排列、结构偏向、关键位距离。
12. 正文不给 `setup_id/model_id/entry_tag` 等机器字段；这些只落盘到 JSONL 供复盘。
13. 中文优先。允许保留 BTC、USDT、VWAP、EMA、CVD、OI、Funding、Spot、FVG、OB、ATR、R:R、DXY。
14. cron/no_agent stdout 保持 ASCII-only；中文写 UTF-8 文件或 Telegram 直发。

## 完整分析卡模板

```markdown
![TradingView截图](<ABSOLUTE_PATH_OR_MEDIA>)

{SYMBOL} {ASSET_CN} · {STATUS} · {PRIMARY_BIAS} · {TIME_CN}
现价 `{PRICE}` · 主周期 `{MAIN_TF}` · 数据质量 `{DATA_GRADE}` · 截图 `{SCREENSHOT_TIME}`
结论：{ONE_LINE_DECISION}
打法：{FAST_ACTION_SUMMARY}
失效：{INVALIDATION_SUMMARY}

### 多周期定位

| 周期 | SVP/结构 | VWAP/EMA/CVD/OI | 交易含义 |
|---|---|---|---|
| D | {D_STRUCTURE} | {D_INDICATORS} | {D_MEANING} |
| 4h | {H4_STRUCTURE} | {H4_INDICATORS} | {H4_MEANING} |
| 1h | {H1_STRUCTURE} | {H1_INDICATORS} | {H1_MEANING} |
| 15m | {M15_STRUCTURE} | {M15_INDICATORS} | {M15_MEANING} |
| 5m | {M5_STRUCTURE} | {M5_INDICATORS} | {M5_MEANING} |

### 关键位矩阵

| 类型 | 价位 | 来源 | 用法 |
|---|---:|---|---|
| 上方磁吸/阻力 | `{R_MAGNET}` | SVP/VAH/POC/线 | {R_MAGNET_USE} |
| 做空防线 | `{SHORT_DEFENSE}` | VWAP/EMA/结构 | {SHORT_DEFENSE_USE} |
| 中轴/POC | `{POC}` | SVP | {POC_USE} |
| 做多防线 | `{LONG_DEFENSE}` | VAL/前低/EMA | {LONG_DEFENSE_USE} |
| 下方磁吸/支撑 | `{S_MAGNET}` | SVP/流动性 | {S_MAGNET_USE} |

### 多源交叉验证

| 来源 | 当前读数 | 偏向 | 处理 |
|---|---|---|---|
| TV SVP v10 | {TV_SUMMARY} | {TV_BIAS} | 主驾驶 |
| Binance OI/Funding/Taker | {BINANCE_SUMMARY} | {BINANCE_BIAS} | {BINANCE_ACTION} |
| CVD/订单流 | {CVD_SUMMARY} | {CVD_BIAS} | {CVD_ACTION} |
| Deribit/期权 | {OPTIONS_SUMMARY} | {OPTIONS_BIAS} | {OPTIONS_ACTION} |
| Dune/稳定币/链上 | {ONCHAIN_SUMMARY} | {ONCHAIN_BIAS} | {ONCHAIN_ACTION} |
| 宏观/事件 | {MACRO_SUMMARY} | {MACRO_BIAS} | {MACRO_ACTION} |
| X/社区情绪 | {X_SENT_SUMMARY} | {X_SENT_BIAS} | {X_SENT_ACTION} |

### 执行预案

| 方案 | 条件 | 入场 | 止损 | 目标 | R:R | 仓位 |
|---|---|---:|---:|---:|---:|---|
| 主线 {MAIN_DIR} | {MAIN_CONDITION} | `{MAIN_ENTRY}` | `{MAIN_STOP}` | `{MAIN_TARGET}` | `{MAIN_RR}` | {MAIN_SIZE} |
| 反向 {ALT_DIR} | {ALT_CONDITION} | `{ALT_ENTRY}` | `{ALT_STOP}` | `{ALT_TARGET}` | `{ALT_RR}` | {ALT_SIZE} |
| 禁做/等待 | {NO_TRADE_CONDITION} | - | - | - | - | {NO_TRADE_REASON} |

### 风控闸门

| 闸门 | 状态 | 处理 |
|---|---|---|
| 数据新鲜度 | {FRESHNESS_STATUS} | {FRESHNESS_ACTION} |
| 事件窗口 | {EVENT_STATUS} | {EVENT_ACTION} |
| R:R | {RR_STATUS} | {RR_ACTION} |
| 单笔风险 | {POSITION_STATUS} | {POSITION_ACTION} |
| 连亏/冷却 | {COOLDOWN_STATUS} | {COOLDOWN_ACTION} |
| 相关性/组合暴露 | {CORR_STATUS} | {CORR_ACTION} |

总结：{FINAL_SUMMARY}
```

## 快速更新模板

```markdown
![TradingView截图](<ABSOLUTE_PATH_OR_MEDIA>)

{SYMBOL} · {STATUS} · {PRIMARY_BIAS} · {TIME_CN}
结论：{ONE_LINE_DECISION}

| 项 | 最新读数 | 变化 | 操作 |
|---|---|---|---|
| 价格/关键位 | `{PRICE}` / `{NEAREST_LEVEL}` | {PRICE_CHANGE} | {PRICE_ACTION} |
| TV SVP v10 | {TV_SUMMARY} | {TV_CHANGE} | {TV_ACTION} |
| CVD/OI/Funding | {FLOW_SUMMARY} | {FLOW_CHANGE} | {FLOW_ACTION} |
| 预案 | {PLAN_SUMMARY} | {PLAN_CHANGE} | {PLAN_ACTION} |
```

## 告警模板

```markdown
{DIRECTION_SYMBOL} {SYMBOL} {PRICE}，{PLAIN_LANGUAGE_ALERT}

| 项 | 读数 | 动作 |
|---|---|---|
| 触发 | {TRIGGER_LEVEL} | {TRIGGER_ACTION} |
| TV确认 | {TV_CONFIRM} | {TV_ACTION} |
| 订单流 | {FLOW_CONFIRM} | {FLOW_ACTION} |
| 风控 | {RISK_STATUS} | {RISK_ACTION} |
```

方向符号：
- `↑做多`：站回VWAP/VAL、CVD多背离、下扫回收
- `↓做空`：破VAL、CVD空背离、上扫失败
- `○等待`：接近关键位但确认不足
- `×禁做`：数据过期、R:R不足、事件禁做、SVP X结构冲突

## 资产差异

| 资产 | 主执行周期 | 必读数据 | 不适用/降权 |
|---|---|---|---|
| BTC/ETH | 15m + 5m触发 | TV SVP、Binance OI/Funding/Taker、多空比、CVD、Depth、Deribit、Dune、X、宏观 | 无 |
| 山寨 | 15m + 5m | TV、Binance、BTC方向、流动性、Depth | 低流动性不主动给A |
| XAU | 5m执行 + 15m辅助 | TV、金十、DXY、US10Y、GC/MGC代理、伦敦/纽约窗口、COT | 不套加密Funding/Taker |
| 外汇 | 15m执行 | TV、DXY/利差、央行窗口、COT、事件 | 加密OI/CVD降权 |
| 股票 | 1h主线 + 15m触发 | TV、财报/基本面、期权链、指数/VIX、新闻情绪 | 不套加密Funding |
| 期货 | 15m执行 | TV、合约流动性、宏观、COT、事件窗口 | 加密OI只作关联参考 |
| 期权 | 跟底层 | IV、Delta/Gamma、OI、到期、MaxPain | 不直接套现货止损 |
