# 生产双指标更新记录 — 2026年7月2日

## 权威文件

| 指标 | 路径 | 版本/规模 | 哈希前缀 | 角色 |
|---|---|---:|---|---|
| 主指标 | `D:/Hermes agent/svp_indicator.txt` | Pine v5 · 3163行 | `703eb981` | 主驾驶：结构、方向、位置、进场、止损、目标、磁吸 |
| 副指标 | `D:/Hermes agent/haldro_indicator.txt` | Pine v6 · 469行 | `b049bac0` | 副驾驶：订单流质量、OI价仓、CVD、覆盖率、Composite、爆仓 |

## 关键纠偏

- 主指标标题是 `SVP+ICT+VWAP+CVD`，不再写作旧 `SVP+ICT+VWAP+EMA+CVD`；但源码仍包含 `EMA 9/21/34/55`，不要误判“无EMA”。
- 主指标已内置 `SHOW_FVG`、`FVG_DRAW_BOXES`、`FVG_REQUIRE_DISP`、`FVG_HTF_ALIGN`、`SHOW_HTF_FVG`、`FVG_SHOW_CE`；禁止再说“主指标没有FVG”。
- 主指标已恢复 MCP Data Window 导出：`MCP Side Code`、`MCP Grade Code`、`MCP Setup Score`、`MCP Entry Price`、`MCP Stop Price`、`MCP Target Price`、`MCP CVD Value`、`MCP Quality Code`。
- 副指标 `Volume Aggregated Spot & Futures` 导出：`OI Total`、`CVD Value`、`Volume Ratio`、`Coverage Exchanges/Spot/Perp`、`Coverage Feed Mode`、`Exchange Dominance %`、`Confirm Score`、`Composite`。
- 不再假设 TV 一定有独立 Open Interest 研究。加密 OI 优先读副指标 + Binance OI；`chart_get_state` 实际存在独立 OI 时才额外读取。
- 副指标“占比”不再作为独立行；合约占比并入“量能”行，新增“覆盖”行用于低覆盖/单所主导降权。

## 读取顺序

1. `chart_get_state` 校验品种、周期、studies，防止跨会话污染。
2. 五层读取：`D → 4h → 1h → 15m → 5m`。
3. 每周期读：主 `pine_tables` + `study_values` + `pine_labels` + `pine_lines` + `pine_boxes` + OHLCV。
4. 加密额外读副指标：`pine_tables(study_filter="Volume Aggregated")` + study_values。
5. 行动格文字优先；MCP Data Window 兜底；外部源只做交叉验证和降级。
6. 输出驾驶舱固定表：流程/完整性、多周期、关键位、多源、矛盾、方案、评分。

## 已同步的代码/测试

- `scripts/auto_card.py`：当前主指标名与 MCP DW 兜底逻辑。
- `scripts/render_tv_card.py`：生产双指标描述。
- `scripts/dmi_decision.py`、`scripts/vwap_ema_cvd_engine.py`：主指标参数来源。
- `scripts/pipeline_router.py`：Deribit期权 `BTC-...-C/P` 先识别为 option。
- 回归：`tests/test_render_tv_card.py`、`tests/test_tv_action_panel_decode.py`、`tests/test_pipeline_router.py`。
