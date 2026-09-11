# 多资产双指标增强审计（2026-09-02）

## 结论

SVP主指标和AggVol副指标均不需要推倒重写。先补契约字段，再改Pine；不要为了增加“智能感”堆叠重复信号。

## SVP主指标

保留：价值区、POC/VAH/VAL、nPOC、VWAP、周月VWAP、DO、EMA、FVG、OB、BOS/CHoCH、CVD、SMT、ADR、行动格和MCP Data Window。

优先增强机器可读字段：`MCP Bar Closed`、`MCP Trigger State`、`MCP Wait Reason Code`、`MCP Conflict Code`、`MCP Structure Confirmed`、`MCP Signal Age`、`MCP Execution Valid`、`MCP Data Quality`。

BOS/CHoCH不能自动等价为完整HH/HL/LH/LL序列确认；事件、方向、确认和年龄应分开输出。

## AggVol副指标

保留：五所成交量、四所OI、聚合CVD、现货/永续、Coverage、Exchange Dominance、OI Breadth/Agreement、Stale Venue、State/Risk/Contract/Freshness Pack。

优先增强：`HALDRO Bar Closed`、`HALDRO Estimated CVD Flag`、`HALDRO OI Valid Flag`、`HALDRO Coverage Quality Code`、`HALDRO Direction Code`、`HALDRO Data Quality Code`。

CVD估算不是交易所原生逐笔；OI升降是事实，新增多/新空/回补应由Python结合价格解释。方向、质量、风险不能共用一个颜色或一个Composite文字。

## 多市场硬边界

AggVol仅加密有效。黄金、外汇、股票、期货和期权卡片不得混入AggVol、BTC情绪、Binance Funding/Taker或加密OI语义。期权必须先分析底层标的，再分析IV、Greeks、OI/PCR和有效MaxPain。

## 实施顺序

1. Python先定义兼容字段和质量门控。
2. Pine做版本化字段增强，不改原方向算法。
3. TradingView云端编译并保存真实回执。
4. 挂载测试图后等待重算，逐周期读行动格/Data Window。
5. 校验D/4h/1h/15m/5m的symbol、resolution、时间戳和闭柱状态。
6. 通过双指标、跨市场、渲染和回归验收后再替换生产版本。

未取得云端编译回执、未完成五周期现场读回时，不得称为“指标已上线”或“已编译通过”。
