# 双指标驾驶舱落地模式（2026-07-04）

适用场景：用户要求把 SVP+ICT+VWAP+CVD 主指标与 HALDRO/Volume Aggregated 副指标真正接入分析卡、驾驶舱与下单闸门，而不是只做口头方案或 Pine 静态审计。

## 核心裁决原则

- SVP v10 = 主驾驶：结构、方向、关键位、入场、止损、目标、A/B/C/X。
- HALDRO = 加密副驾驶：Composite、Confirm Score、OI、CVD、Volume Ratio、Coverage、CVD Quality。
- 非加密品种不要硬套 HALDRO。XAU/外汇/股票/期货应显示“HALDRO不适用”，不因副指标缺失降级；改用对应市场数据验证。
- 主副强冲突时不能输出 A 可执行；必须降级或由 GO/NO-GO 红灯拦截。

## 推荐代码落地点

1. `scripts/auto_card.py`
   - 新增或维护 `_dual_indicator_verdict(symbol, meta, engine_data, cvd_dir, cvd_quality)`。
   - 统一输出 `_dual_indicator_verdict`，字段至少包含：
     - `asset_is_crypto`
     - `svp_state`
     - `svp_direction`
     - `svp_position`
     - `svp_flow`
     - `svp_quality`
     - `svp_execution`
     - `haldro_direction`
     - `haldro_position`
     - `haldro_flow`
     - `haldro_quality`
     - `haldro_confirm`
     - `direction_verdict`
     - `structure_verdict`
     - `flow_verdict`
     - `quality_verdict`
     - `state`
     - `conflict`
     - `usable`
   - 注意 TV study values 可能把 HALDRO 字段映射到 `_tv_main.sub_*`，需要反向映射到短字段，避免驾驶舱误显示“副指标待刷新”。
   - 若 `dual_indicator.usable` 且为加密市场，可把 `haldro_flow` 与 `haldro_direction` 注入 `klines[tf].sub_indicator/sub_composite`，让多周期表同步显示副指标状态。

2. `scripts/render_v8.py`
   - 在“多周期定位”之前新增“### 双指标裁决”表。
   - 表头：`| 裁决项 | SVP v10主驾驶 | HALDRO副驾驶 | 结论 |`。
   - 推荐行：方向、位置/结构、动能/订单流、覆盖/质量、执行。
   - 非加密品种表内明确写 HALDRO 不适用，不要让用户误以为副指标缺失是系统故障。

3. `scripts/go_nogo_gate.py`
   - GO/NO-GO 从 7 闸门升级为 8 闸门，新增 `dual_indicator`。
   - 规则：
     - `conflict=True` → red，禁止 A 级执行。
     - `usable=True` 或非加密 → green。
     - 加密但 HALDRO 未读 → yellow，降级确认型计划。
   - `gate_report_card()` 的绿灯总数、`gate_order` 也要同步改为 8 闸门，避免显示不一致。

4. 测试与验证
   - 若测试无法导入 `auto_card` / `go_nogo_gate`，优先在 `pytest.ini` 保留原有配置并追加 `pythonpath = scripts`，不要覆盖 `testpaths/norecursedirs/python_files`。
   - 添加锁定测试：完整卡必须含 `### 双指标裁决`。
   - 添加闸门测试：主副冲突红灯、主副同向绿灯、非加密无 HALDRO 不拦截。
   - 最低验证命令：
     ```bash
     python -m py_compile scripts/render_v8.py scripts/auto_card.py scripts/go_nogo_gate.py
     python -m pytest tests/test_pipeline_router.py tests/test_card_render_locked.py tests/test_dual_indicator_gate.py -q
     timeout 120 python scripts/auto_card.py BTCUSDT
     ```

## TV MCP 闭环验证

修复/改造后不要只跑单元测试，必须实测真实 TradingView：

1. 用 `mcp_tradingview_tv_health_check` 检查 CDP；失败时 `mcp_tradingview_tv_launch(kill_existing=true, port=9222)`，再复查 `api_available=true`。
2. `chart_get_state` 必须确认 `BINANCE:BTCUSDT.P`、`15m`，且 studies 含 `SVP+ICT+VWAP+CVD` 与 `Volume Aggregated Spot & Futures`。
3. 分别读取：
   - `data_get_pine_tables(study_filter="SVP")`
   - `data_get_pine_tables(study_filter="Volume")`
   - `data_get_study_values`
   - `data_get_pine_lines(study_filter="SVP")`
4. `capture_screenshot(region="full")` 后立即复制到 `C:/Users/Administrator/.hermes-web-ui/upload/default/`，再用该路径给用户展示。
5. 跑：
   ```bash
   cd "D:/Hermes agent"
   python scripts/tv_live_dump.py --verbose
   timeout 150 python scripts/auto_card.py BTCUSDT
   ```

验收标准：
- `data/tv_live.json` 与 `data/tv_dmi_cache.json` 时间新鲜。
- indicators 中含 `s_vwap/poc_price/vah_price/val_price/oi_total/cvd_value/coverage_exchanges/confirm_score/composite`。
- `data/auto_card_BTCUSDT_full.md` 含“### 双指标裁决”。
- 管线完成度 `TV五层 ✅`，总管线 `10/10`。
- 当前不能交易时必须诚实输出 NO-GO/观察，不能因新功能存在而强行给 A 单。

## 实跑判定

- 如果 TV 缓存过期，出卡应显示 TV 五层 ⚠️，双指标表可显示“副指标不足”，不能假装主副共振。
- 如果真实 TV/HALDRO 新鲜，完整卡应出现双指标裁决表并填入 Composite/OI/CVD/Confirm/Coverage。
- 典型读法：SVP `等空 反抽 ⚠冲突` + `观望 · 走弱` = 主指标偏弱但不追；HALDRO `Composite -11` + CVD大负 = 副指标偏空；若 `Confirm Score 0` 或“逆高周”，最多 B/C 等确认，不可升级 A。
- A/B/C/X 与 R:R 仍由原有风控和 GO/NO-GO 共同裁决；双指标共振不是绕过 R:R 的理由。
