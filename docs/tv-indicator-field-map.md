# 双指标 TV Pine → 分析卡 字段映射 v1.2

> 所属：棠溪交易驾驶舱 / `tradingview-indicator-analysis`
> 更新：2026年7月2日
> 来源：用户上传的两份权威生产指标：`主指标.txt` + `副指标.txt`。
> 铁律：以后正式分析只读这套双指标，不再沿用旧 SVP/HALDRO 假设或旧 Data Window 状态。

## 0. 当前生产指标

| 指标 | 权威文件 | Pine | 行数 | 分工 |
|---|---|---:|---:|---|
| 主指标 | `D:/Hermes agent/svp_indicator.txt` | v5 | 3163 | 结构、位置、ICT/FVG、VWAP/EMA/CVD、DMI状态、进场/止损/目标、磁吸 |
| 副指标 | `D:/Hermes agent/haldro_indicator.txt` | v6 | 469 | 聚合现货/永续成交量、OI价仓、会话CVD、量能、覆盖率、爆仓、订单流降级 |

主指标当前标题是 `SVP+ICT+VWAP+CVD`，但源码仍包含 EMA9/21/34/55、周/月VWAP、DO、FVG、Funding、ADR 等模块；不要因标题少写 EMA 就误判 EMA 不存在。

## 1. 主指标更新点

| 模块 | 当前规则 | 分析影响 |
|---|---|---|
| FVG | 已显式内置 ICT 三K FVG、CE 50%、位移过滤、本级/HTF确认 | 正式分析必须读取/解释 FVG✓、FVG✓HTF、扫★HTF；不再说“指标没有FVG代码” |
| 行动格 v2 | 结论、方向、进场、止损、目标、确认、风险、磁吸↑、磁吸↓；完整模式另有指标/计划 | `pine_tables` 是主真理源；卡片里的进出场优先用行动格原文 |
| Data Window | 已恢复 MCP 导出：`MCP Side Code`、`MCP Grade Code`、`MCP Setup Score`、`MCP Entry Price`、`MCP Stop Price`、`MCP Target Price`、`MCP CVD Value`、`MCP Quality Code` | 可作为 MCP 稳定读取兜底；但行动格文字仍优先于编码字段 |
| 右轴价格 | `POC Price`、`VAH Price`、`VAL Price`、`nPOC Price`、`W VWAP Price`、`M VWAP Price`、`DO Price` | 关键位矩阵必须从这些字段/线条交叉验证 |
| 质量码 | `Quality Code` 按位编码：HTF冲突=1、CVD质量问题=2、低流动性=4、ADR耗尽/禁追=8、HTF FVG=16、MSS=32 | 多源交叉验证表要拆码，不得只写“质量码31” |

### 主指标行动格字段

| 行 | 源码变量 | 用途 |
|---|---|---|
| 结论 | `actionStateText` | A/B/C/X状态与处理 |
| 方向 | `panelDirVal` | 主倾向、评分、过热/走弱、溢价/折价、KillZone、扫位计数 |
| 进场 | `panelEntryVal` | FVG@CE、扫低/扫高、VAL/VAH、吸收/派发、结构触发 |
| 止损 | `panelStopVal` | 结构失效位 + ATR夹层 |
| 目标 | `panelTgtVal` | 同向磁吸 + R:R |
| 确认 | `panelConfirmText` | HTF/CVD/位置/MSS/FVG/扫★HTF |
| 风险 | `panelRiskText` | HTF逆、CVD冲突、EMA逆、位移缺、深溢折、ADR、SMT、OI、薄量 |
| 磁吸↑/↓ | `pnlMagUp` / `pnlMagDn` | 上下方目标、分数、HTF标记、距ATR |

### 主指标 MCP Data Window 字段

| 字段 | 含义 | 读取优先级 |
|---|---|---|
| `MCP Side Code` | 1=多，-1=空，9=X，0=中性/等待 | 表格缺失时兜底 |
| `MCP Grade Code` | 3=A，2=B，1=C，-1=X，0=等待 | 表格缺失时兜底 |
| `MCP Setup Score` | 0-10执行评分 | 评分列/Composite |
| `MCP Entry Price` | A级计划价；B/C可能为空 | 仅 A 或已确认时可执行 |
| `MCP Stop Price` | A级失效/止损价 | 与行动格止损交叉验证 |
| `MCP Target Price` | 同向磁吸目标价 | 关键位矩阵/目标 |
| `MCP CVD Value` | 主指标CVD值 | CVD窗格与订单流验证 |
| `MCP Quality Code` | 质量/冲突位码 | 拆码写入矛盾点 |

## 2. 副指标更新点

| 模块 | 当前规则 | 分析影响 |
|---|---|---|
| 交易所 | 默认5家：BINANCE/BYBIT/OKX/COINBASE/BITGET | 不再按旧20+交易所假设读字段 |
| 配额 | 交易所20 + EUR/RUB 2 + OI聚合4 + OI回退1 = 27/40 | 不能误报超40 |
| OI | 聚合 Binance/Bybit/OKX/Bitget OI + 单源回退 | 加密订单流表必须写 OI四象限 |
| 覆盖率 | `聚合n/5 · 现n 永n · 覆盖% · 低覆盖/单所主导` | 覆盖/单所主导是降权，不是方向 |
| 行动格 | 精简模式默认只显示 信号/结论/风险/操作；完整模式显示高周/持仓/流向/覆盖/量能/爆仓/操作 | 解析器不能强依赖“占比”行；合约占比已并入量能行 `合N%` |
| Data Window | `OI Total`、`CVD Value`、`Volume Ratio`、`Coverage Exchanges/Spot/Perp`、`Coverage Feed Mode`、`Exchange Dominance %`、`Confirm Score`、`Composite` | 副指标可从 study_values 直接补订单流数值 |

### 副指标行动格字段

| 行 | 源码变量 | 含义 | 卡片用途 |
|---|---|---|---|
| 信号 | `signalA + flowShortA + confirmScoreA/5` | 偏多/偏空/无向 + 共振 + 流型 + 确认分 | 订单流方向与质量 |
| 结论 | `actText` | 实涨可信、真实下跌、涨势存疑、回补/去杠杆、踩踏/轧空 | 真假运动判断 |
| 风险 | `riskWarnA` | 低覆盖、单所主导、HTF冲突、OI背离 | 降权/禁追理由 |
| 高周 | `htfTxtA` | 偏多/偏空/震荡 | 与主指标HTF交叉 |
| 持仓 | `oiTxtA` | 新多、新空、空补、多平、OI背离 | 价仓四象限 |
| 流向 | `cvdTxtA` | 买盘占优、卖盘占优、均衡 | CVD确认/背离 |
| 覆盖 | `coverageRowA` | 聚合覆盖与单所主导 | 数据质量 |
| 量能 | `volTxtA` | 放量/缩量/平量 + 合约占比 | 是否能追 |
| 爆仓 | `liqTxtA` | 空头爆仓/多头爆仓/无明显 | 轧空/踩踏风险 |
| 操作 | `comboTxt` | 配合主指标可做/降级/等待 | 最终执行质量 |

### 副指标 Data Window 字段

| 字段 | 含义 |
|---|---|
| `OI Total` | 聚合/回退后的总OI |
| `CVD Value` | 会话CVD累计值 |
| `Volume Ratio` | 当前量 / EMA量 |
| `Coverage Exchanges` | 有效交易所数量 |
| `Coverage Spot` | 有效现货源数量 |
| `Coverage Perp` | 有效永续源数量 |
| `Coverage Feed Mode` | 1=聚合，-1=回退单图，0=其他 |
| `Exchange Dominance %` | 最大交易所成交占比 |
| `Confirm Score` | 0-5确认分 |
| `Composite` | 正=多、负=空，绝对值含共振强度 |

## 3. 分析驾驶舱新读取顺序

```text
① TV健康与品种校验：chart_get_state，价格数量级必须匹配
② 五周期读取：1D → 4h → 1h → 15m → 5m
③ 每周期读取：pine_tables + study_values + pine_labels + pine_lines + pine_boxes + OHLCV摘要
④ 主指标优先：行动格 v2 决定结构/计划；MCP Data Window 补价格/质量码
⑤ 副指标确认：行动格 + OI/CVD/Volume/Coverage Data Window
⑥ 外部验证：Binance OI/Funding/Taker/多空比/Depth、F&G、CoinGecko、Jin10/Web/X
⑦ 截图：full窗口，价格轴 + 主行动格 + 副行动格/OI/CVD窗格
⑧ 输出：多周期定位表、关键位矩阵、多源交叉验证、矛盾点、AB方案、评分、管线完成度
```

## 4. 合成裁决

| 情况 | 裁决 |
|---|---|
| 主A + 副确认分≥3/5 + OI/CVD顺向 + 覆盖正常 | A机会，可盯执行 |
| 主A + 副CVD不配/回补/缩量/低覆盖 | 降B，等二次确认 |
| 主B/C + 副强 + 贴关键位/FVG/磁吸 | B偏A，给确认触发，不给无条件挂单 |
| 主X + 副强 | 不直接反向；拆质量码与风险，写解除X条件 |
| 主指标FVG✓HTF + MSS✓ + 副顺向 | FVG回踩/CE位优先级上调 |
| 副单所主导/低覆盖 | 数据降权，不作为单独方向源 |

## 5. 禁止事项

- 禁止再说“主指标没有显式FVG代码”。当前主指标已内置FVG与HTF FVG确认。
- 禁止再按“主指标Data Window编码已移除”处理。当前已恢复 MCP Data Window 导出。
- 禁止用旧 `SVP+ICT+VWAP+EMA+CVD`/旧HALDRO字段假设覆盖用户本次上传指标。
- 禁止只读 `study_values` 不读行动格；行动格是进场/止损/目标的权威文本。
- 禁止强依赖副指标“占比”行；当前占比并入“量能”行，新增“覆盖”行。
- 禁止把副指标加密 OI/Funding/Spot-Perp 逻辑套到 XAU/外汇/股票。
