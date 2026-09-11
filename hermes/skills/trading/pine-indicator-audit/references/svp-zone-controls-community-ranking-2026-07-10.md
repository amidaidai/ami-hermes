# SVP 区域控件、EMA可调与社区质量排名（2026-07-10）

## 用户校正后的最终图面规则

- 区域标签保留必要英文：`FVG↑/↓`、`OB↑/↓`、`BRK↑/↓`、`LV↑/↓`、`HTF`。
- 标签必须在框内右下角，不在框外：x 从 box right 向左内缩，y 从 box bottom 向上抬升，`label.style_label_right` + `text.align_right`。
- 薄框防越界：纵向抬升用 `min(ATR * lift, zoneHeight * 0.25)`；横向用 `max(box.left + 1, box.right - inset)`。
- FVG 与 OB 都必须有两类设置：`最多显示个数`、`向右延伸K数`。禁止 OB 延伸写死 `+5`；创建与维护统一引用 `OB_EXTEND`。
- EMA 只显示云填充，不显示实体线；四周期必须在输入设置中可调，且同步驱动主图 EMA、HTF trend pack、趋势裁决与 MCP Data Window。
- Pine plot 标题是 const string，周期可调后不要继续把 plot 永久命名成 `EMA 9/21/34/55` 而误导用户。可改稳定语义名（快速1/确认2/结构3/慢速4），并同步下游别名。

## 设置面板审计方法

对所有 `input.*` 变量统计全文引用次数。只有声明一次、无消费的 input 是死设置。2026-07-10 生产版发现：

- `BOS_COL`
- `VWAP_COLOR`
- `VWAP_SD_COLOR_1`
- `MACRO_COLOR`

若颜色被有意硬编码以节省 plot count，应删除死 input，而不是重新接入动态 series color 导致绘图槽增加。

## HTF 开关串线检查（P1）

共享 HTF 有效条件不能代替模块自身开关。实案：

```pine
bool fvgHtfValid = ((SHOW_HTF_FVG and SHOW_FVG) or (SHOW_HTF_OB and SHOW_OB)) and htfHigher
```

若后续 `newHtfBull/newHtfBear` 不再检查 `SHOW_HTF_FVG`，只开 HTF OB 也会生成 HTF FVG；若 `newHtfObBear` 漏 `SHOW_HTF_OB`，只开 HTF FVG 仍可能生成空头 HTF OB。

正确审计：

- FVG 创建必须额外门控 `SHOW_HTF_FVG and SHOW_FVG`。
- OB 多空创建都必须额外门控 `SHOW_HTF_OB and SHOW_OB`。
- 本级重叠确认同样用各自模块开关，不只用共享 timeframe-valid 条件。

## “显示”开关不得暗中关闭计算

实案中 `SHOW_BOS_CHOCH` 标题写“显示 BOS/CHoCH”，但它直接门控 `breakBull/breakBear`，关闭后 OB 检测也停止。修法二选一：

1. 拆成 `ENABLE_STRUCTURE_ENGINE`（计算）与 `SHOW_BOS_CHOCH_TEXT`（显示）；或
2. 若必须单开关，将标题改为“启用BOS/CHoCH与OB结构逻辑”，tooltip 明确依赖。

审计任何 `SHOW_*` 时，grep 其下游：如果影响评分、信号、对象创建或 MCP 导出，就不是纯显示开关。

## 社区对照后的最高收益优化：质量排名，不再堆概念

TradingView 社区成熟 OB/FVG 工具普遍采用 UDT 对象 + 动态质量分 + Top N：

### OB 0–100 建议

- 位移实体/ATR：25
- RVOL：20
- 同向 FVG 重叠：15
- HTF 同向重叠：15
- EMA 趋势对齐：10
- 区域高度/ATR：10
- BOS/CHoCH 来源：5
- 动态扣分：触碰次数、缓解深度、年龄衰减、Breaker 状态

图面每方向只显示 Top 2；其余内部跟踪。A级 OB 才能升级方案，C级只作背景。

### FVG 0–100 建议

- 位移强度：25
- Gap/ATR：20
- RVOL：15
- HTF 重叠：15
- EMA 对齐：10
- 窄成交分布/快速穿越代理：15
- 动态扣分：填充比例、重复测试、年龄

“最近优先”只能作为距离因子，不能代替质量排名。

参考：

- TradingView Ranked OB: https://www.tradingview.com/script/Ce4kPpHV-Ranked-Order-Block-Zones-Zeiierman/
- TradingView Ranked FVG: https://www.tradingview.com/script/Z4h7vDqN-Ranked-FVG-Imbalance-Zones-Zeiierman/
- TradingView Volumized OB: https://www.tradingview.com/script/HUcKziz7-Volumized-Order-Block/
- ATAS FVG: https://atas.net/blog/fvg-trading-what-is-fair-value-gap-meaning-strategy/
- Bookmap CVD: https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy

## Footprint 口径与版本策略

TradingView 2026-01 新增 `request.footprint()`：仅 Premium/Ultimate；单脚本最多一个 footprint 请求。可读 buy/sell volume、delta、POC、VAH/VAL、volume-row imbalance。

重要口径：官方说明 footprint 将低周期 volume 按 intrabar price action 分类，不应笼统宣称为交易所逐笔 bid/ask 真 Delta。

版本策略：

- 通用生产版继续 lower-TF 估算 CVD + HALDRO 聚合确认。
- Footprint 只做独立 `SVP Footprint Pro`，用于 FVG/OB 形成质量与回踩确认。
- 不把 Footprint 直接塞入通用版，避免低套餐无法运行和生产主指标继续膨胀。

官方来源：

- https://www.tradingview.com/pine-script-docs/release-notes/
- https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/

## EMA顺序保护

周期输入允许修改时必须检查：

```pine
bool emaOrderOk = EMA_LEN_1 < EMA_LEN_2 and EMA_LEN_2 < EMA_LEN_3 and EMA_LEN_3 < EMA_LEN_4
```

顺序错误时：行动格直白提示 `× EMA周期顺序错误`；禁止升级A级；MCP Quality Code增加参数错误位。不要暗中排序用户输入，避免设置值与实际计算不一致。

## 部署验证补充

新增 Data Window 字段后，云端脚本保存成功不等于图表实例已刷新。若 `data_get_study_values` 仍缺新字段：移除旧主指标 entity，再从已保存的原生产脚本重新“添加到图表”，确认主副指标各只有一个实例。