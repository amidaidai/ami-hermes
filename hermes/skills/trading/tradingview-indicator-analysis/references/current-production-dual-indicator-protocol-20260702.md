# 当前生产双指标协议（2026年7月2日）

> ⚠ **本文已作废（2026-09-11）**：这是当时（2026-07-02）的实况记录，**不是当前字段映射权威**。
> 文中 `svp_indicator.txt` / `haldro_indicator.txt`、v5/v6、3163/469 行、10 行行动格、
> `MCP CVD Value` / `OI Total` / `Estimated CVD Value` 等全部已失效。
> **现行权威**：`D:/Hermes agent/docs/tv-indicator-field-map.md`（v3.0）+
> 契约 `D:/Hermes agent/scripts/tv_indicator_contract.py`。
> 定版指标：主 `SVP_主指标_空格修正_20260911.pine`（3557 行·68a34fc3）/ 副 `AggVol_副指标_最终版_20260911.pine`（966 行·c4c563ef）。


## 触发场景

当用户上传或指认“这两个是我的指标”“更新分析驾驶舱流程”“不要再用旧指标污染数据”时，必须把本文件视为当前 TV 分析流程的权威补充。

## 生产指标

| 指标 | 文件 | Pine | 行数 | 权威用途 |
|---|---|---:|---:|---|
| 主指标 | `D:/Hermes agent/svp_indicator.txt` | v5 | 3163 | 结构、位置、ICT/FVG、VWAP/EMA/CVD、DMI状态、进场/止损/目标、磁吸 |
| 副指标 | `D:/Hermes agent/haldro_indicator.txt` | v6 | 469 | 聚合现货/永续成交量、OI价仓、会话CVD、量能、覆盖率、单所主导、爆仓、订单流降级 |

主指标标题当前是 `SVP+ICT+VWAP+CVD`，但源码仍包含 EMA9/21/34/55、FVG/HTF FVG、周/月VWAP、DO、Funding、ADR 等模块。不要因标题少写 EMA 就误判 EMA 不存在。

## 已废弃的旧假设

- 旧假设：“主指标没有显式 FVG 代码” → 作废。当前主指标已内置 FVG、CE 50%、位移过滤、HTF FVG确认。
- 旧假设：“主指标 Data Window 编码导出已移除” → 作废。当前已恢复 MCP Data Window 导出。
- 旧假设：“副指标有独立占比行 shareTxtA” → 作废。当前合约占比并入“量能”行，并新增“覆盖”行。
- 旧假设：“副指标行数约418/425” → 作废。当前生产副指标469行。
- 旧名称 `SVP+ICT+VWAP+EMA+CVD` 仅可作为历史/兼容搜索名；正式描述用当前源码标题并注明“含EMA/FVG/MCP DW”。

## 主指标读取协议

优先级：行动格文字 > MCP Data Window兜底 > 外部源校验。

必须读取：

| 来源 | 字段 |
|---|---|
| 行动格 v2 | 结论、方向、进场、止损、目标、确认、风险、磁吸↑、磁吸↓ |
| MCP Data Window | `MCP Side Code`、`MCP Grade Code`、`MCP Setup Score`、`MCP Entry Price`、`MCP Stop Price`、`MCP Target Price`、`MCP CVD Value`、`MCP Quality Code` |
| 右轴/价格 | `POC Price`、`VAH Price`、`VAL Price`、`nPOC Price`、`W VWAP Price`、`M VWAP Price`、`DO Price` |
| FVG | `pine_boxes`、行动格 `FVG✓` / `FVG✓HTF` / `扫★HTF`，必要时 OHLCV 三K补算 |

`MCP Quality Code` 拆码：HTF冲突=1、CVD质量问题=2、低流动性=4、ADR耗尽/禁追=8、HTF FVG=16、MSS=32。不要只写“质量码48”，要解释含义。

## 副指标读取协议

必须读取：

| 来源 | 字段 |
|---|---|
| 行动格 | 信号、结论、风险、高周、持仓、流向、覆盖、量能、爆仓、操作 |
| Data Window | `OI Total`、`CVD Value`、`Volume Ratio`、`Coverage Exchanges`、`Coverage Spot`、`Coverage Perp`、`Coverage Feed Mode`、`Exchange Dominance %`、`Confirm Score`、`Composite` |

副指标是订单流质量层，不是方向主驾驶。覆盖率低、单所主导、OI背离、HTF冲突属于降权/禁追信号，不单独生成方向。

## 分析输出影响

正式分析必须在驾驶舱表中体现：

- 多周期定位表：主指标状态 + 副指标确认分/Composite + 价 vs VWAP。
- 关键位矩阵：VAH/VAL/POC/nPOC/WVWAP/MVWAP/DO + FVG/HTF FVG/磁吸。
- 多源交叉验证：主行动格、MCP Data Window、副指标OI/CVD/覆盖率、Binance OI/Taker/Funding/多空比、Depth、情绪/事件。
- 矛盾点：主指标风险行、MCP Quality Code拆码、副指标风险行、外部源冲突。
- AB方案：A/B/C/X状态严格决定是否可写执行价；B/C需写“确认后入场”，X只写解除条件。

## 运行态利用率审计补充（2026年7月3日）

字段协议存在不等于正式分析真的用上。用户要求检查“流程/驾驶舱/策略/skill有没有用上两个指标”时，必须按 `tangxi-system-audit/references/dual-indicator-runtime-usage-audit-2026-07-03.md` 做运行态审计：

- `tv_live.json` / `tv_dmi_cache.json` 过期或品种不匹配时，TV步骤标 ⚠️ 并写原因，不能在管线完成度中假标 ✅。
- `tv_data_bridge.py` 的 snake_case `indicators` 缓存需要转回 TV 原始字段名后再进入 `_parse_tv_study_values()`；否则 MCP Data Window、FVG CE、HALDRO Composite/CVD质量会静默丢失。
- `decision_table` 需要拆成主指标行动格与副指标行动格两张表；不能把“信号/持仓/流向/量能/操作”混进主指标解析。
- B等待/C等待/X禁做或 R:R<1:2 时，驾驶舱方案表只能写“等待触发”，止损/目标为 `—`，不能把当前价渲染成可执行入场。

## 验证建议

修改渲染或解析后至少跑：

```bash
python -m pytest tests/test_render_tv_card.py tests/test_tv_action_panel_decode.py -q
```

期望：当前回归集应全部通过。