# 棠溪多资产分析契约（2026-09-02）

## 资产路由

| 资产 | 主周期 | 主结构源 | 交叉验证 | 禁止混入 |
|---|---|---|---|---|
| 加密 | 15m | TV SVP | AggVol、Binance Futures、CG/CMC、Deribit、宏观、X | X不能改FinalVerdict |
| 黄金 | 5m | TV SVP | 金十、DXY、US10Y、GLD/GDX/TIP、COT、X | AggVol、BTC情绪、Binance Funding/Taker |
| 外汇 | 15m | TV SVP | 金十、DXY、央行、利差、相关货币对、X | 加密OI/CVD语义 |
| 股票 | 1h | TV SVP | FinanceKit、SEC/财报、板块、期权、X | 加密衍生品语义 |
| 期货 | 15m | TV SVP | 期货行情、库存、日历、DXY、相关商品、X | 加密AggVol语义 |
| 期权 | 15m | 底层标的TV | IV/Greeks、OI/PCR、事件日历、期权链、X | 直接把标的卡当期权结论 |

## 档位契约

- `quick`：执行周期、实时价、主指标、适用副源、触发/阻断；正式加密/黄金更新必须新截图。
- `inherit`：刷新执行与触发周期，继承未过期高周期，并输出相对上次的变化；高周期过期、突破或冲突时升级`full`。
- `full`：五周期D→4h→1h→15m→5m、资产专属全源、源级质量、FinalVerdict和完整卡。
- `monitor`：价格事件和event_id，不做方向判断、不生成执行价格、不下单。

## 决策优先级

1. SVP决定结构、关键位、路径和等待语义。
2. AggVol仅在加密确认、降级或否决，不独立授权。
3. 资产专属API验证实时价格、衍生品、宏观、基本面或期权。
4. X模型只补情绪、催化剂和盲点；不可改变引擎置信度或最终裁决。
5. Python FinalVerdict是唯一执行权威。
6. 卡片只渲染FinalVerdict：GO-A才可有Entry/Stop/Target；WAIT/NO-GO只能给条件或禁止原因。

## TV共享图表验收

- 采集前取得跨进程锁。
- 切换后读取chart state，确认symbol和resolution。
- 指标重算等待15-30秒后再读行动格/Data Window。
- 读取后再次确认symbol和resolution。
- 任何不匹配、空行动格、空候选池或非完整核心字段都不得写fresh缓存。
- 缓存记录来源、时间戳、symbol、resolution、identity_valid、action_table_complete、source_quality。

## X模型验收

X模型调用结果必须带：查询词、资产、时间范围、来源时间、模型ID、置信度和降级状态。X不可用不等于整个市场数据不可用，但必须降低情绪源完整度；不得把旧X缓存写成实时成功。

## 指标增强原则

SVP与AggVol不应继续堆叠重复信号。优先增加机器可读字段：闭柱、等待原因、冲突码、结构确认、信号年龄、执行有效性、估算CVD标记、OI有效标记、覆盖质量。Pine新增字段必须先做Python契约和回归，再做版本化源码、TradingView云端编译、挂载现场读回和五周期验收；未取得云端回执不得称为已上线。
