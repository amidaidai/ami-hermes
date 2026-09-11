# 双指标能力运行态利用率审计模式（2026-07-03）

用于用户要求“参照这两个指标全面检查分析流程/驾驶舱/策略/skill有没有用上能力”时。

## 审计目标
不要只确认 Pine 源码或字段映射存在；必须确认运行态分析卡实际吃到了 SVP 主指标与 HALDRO 副指标能力。

权威双指标能力：
- SVP 主指标：行动格 v2、MCP Side/Grade/Score/Entry/Stop/Target/CVD/Quality、FVG CE/Quality、VWAP/EMA/POC/VAH/VAL/nPOC/W/M VWAP/DO。
- HALDRO 副指标：OI Total、Estimated CVD Value、CVD Method/Quality、Volume Ratio、Coverage、Exchange Dominance、Confirm Score、Composite、行动格信号/结论/风险/操作。

## 必查 5 层
1. 运行态：cron、daemon heartbeat、TV cache freshness、source_snapshot freshness。
2. 静态桥接：`pipeline_router.py`、`auto_card.py`、`tv_data_bridge.py`、`render_v8.py`、`render_tv_card.py`、`go_nogo_gate.py` 是否消费上述字段。
3. Skill 权威链：旧 V5.1/禁表格段落是否被驾驶舱表格卡覆盖。
4. 实跑：`PYTHONPATH=./scripts python -m pytest ...` + `python scripts/auto_card.py BTCUSDT` + `python scripts/auto_card.py XAUUSD`。
5. 报告：P0/P1/P2，每项必须有证据→影响→修复建议。

## 关键判断规则
- `tv_dmi_cache.json` 或 `tv_live.json` 过期/错品种时，TV 步骤必须标 ⚠️，不可算 ✅。
- `auto_card` 里的管线完成度表必须有“备注”列；缺失项写明“缓存过期/品种不匹配/未采到有效字段”。
- `tv_data_bridge.py` 输出的 `indicators` 是 snake_case 缓存，不等同于 TV MCP 原始 `study_values`。运行态需要反向映射成 `MCP Side Code`、`Composite` 等原始字段名，才能被 `_parse_tv_study_values()` 吃到。
- `decision_table` 同时混有主指标行动格和副指标行动格，需要拆成两张表：`SVP+ICT+VWAP+CVD` 与 `Volume Aggregated`。
- B等待/C等待/X禁做或 R:R<1:2 时，渲染层不得把当前价作为入场；显示“等待触发”，止损/目标为 `—`。
- XAU 若缓存 symbol 是 `BINANCE:BTCUSDT.P`，必须拒绝注入；宁可标待刷新，也不能用 BTC 关键位污染 XAU。

## 回归测试建议
至少覆盖：
- cache indicators → studies：MCP Grade、FVG CE、Estimated CVD、Composite 都能恢复。
- decision_table → 双表：主表进场/止损/目标 + 副表信号/OI/CVD/操作均能解析。
- B等待卡：不含当前价可执行入场，必须出现“等待触发”。
- BTC/XAU auto_card：TV不可用时完成度不是全 ✅，而是带原因的 ⚠️。

## 常见修复点
- `auto_card._parse_tv_study_values()` 需要识别 K/M/B 后缀并转数值。
- `auto_card._build_tv_main_data()` 需要包含 MCP FVG 与 HALDRO CVD质量字段。
- `render_tv_card.extract_from_tv_data()` 需要接受 `Estimated CVD Value`、`CVD Method Code`、`CVD Quality Code`。
- `render_v8.py` 非 A 状态不能渲染当前价/止损/目标为可执行计划。

## 完成标准
完成后必须 git commit/push，并报告：测试命令、BTC/XAU 实跑结果、TV完成度状态、commit id、git clean 状态。