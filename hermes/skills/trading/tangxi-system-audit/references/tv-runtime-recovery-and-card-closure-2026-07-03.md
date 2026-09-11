# TV运行态恢复 + 驾驶舱完整卡闭环（2026-07-03）

适用场景：用户要求“全面按照优化建议恢复”、TV五层过期、`monitor_heartbeat.json` stopped、`auto_card` 没有真正吃到 SVP/HALDRO 双指标，或 full card 缺管线完整性备注。

## 恢复顺序

1. 先采集 BEFORE：git 状态、`monitor_heartbeat.json`、`.btc_daemon_heartbeat.json`、`tv_live.json`、`tv_dmi_cache.json`、`source_snapshot_*`、cron 列表。
2. 恢复守护进程：
   - 行情守望必须用 Hermes background：`rm -f data/monitor.lock && python scripts/行情守望.py -s BTCUSDT XAUUSD`
   - BTC守护若 stale，再清 pid/lock 后后台启动 `python scripts/btc_daemon.py`。
   - 验证心跳 mtime < 5 分钟，`status=running`。
3. 恢复 TV CDP：优先 `mcp_tradingview_tv_health_check`；若 CDP 失败，用 `mcp_tradingview_tv_launch(port=9222, kill_existing=false)`；仍失败且确认 9222 不通/TV 不在跑，再 `kill_existing=true`。
4. 验证 TV 双指标能力：
   - `data_get_study_values` 必须读到 SVP：`MCP Side Code`、`MCP Grade Code`、`MCP Setup Score`、`MCP Target Price`、`MCP CVD Value`、`MCP Bull/Bear FVG CE`、`POC/VAH/VAL`。
   - HALDRO 必须读到：`OI Total`、`CVD Value` 或 `Estimated CVD Value`、`Coverage Exchanges`、`Confirm Score`、`Composite`。
   - `data_get_pine_tables(study_filter="SVP")` 必须读到行动格表。
   - `capture_screenshot(region="full")` 成功并验证文件存在。
5. 刷新桥接缓存：`python scripts/tv_data_bridge.py`，验证 `data/tv_dmi_cache.json` 新鲜且 symbol 为 `BINANCE:BTCUSDT.P`。
6. 刷新 P0 数据：`python scripts/p0_refresh_all.py`，要求 source_snapshot/protections/governance/model_stats/btc_signal 全部新鲜。
7. 修复/验证驾驶舱完整性：full card 文件本身必须追加“管线完成度审计”表，不能只在终端 stdout 打印。
8. 实跑闭环：
   - `PYTHONPATH=./scripts python -m pytest tests/test_render_tv_card.py tests/test_tv_action_panel_decode.py tests/test_pipeline_router.py tests/test_card_render_locked.py -q`
   - `python -m py_compile scripts/auto_card.py scripts/render_v8.py scripts/render_tv_card.py scripts/go_nogo_gate.py scripts/tv_data_bridge.py`
   - `python scripts/auto_card.py BTCUSDT` 应看到 TV五层 ✅ 且完成 10/10。
   - `python scripts/auto_card.py XAUUSD` 对 BTC TV 缓存应保持 ⚠️ 品种不匹配，完成 7/8 是正确门禁，不是失败。
   - `python scripts/btc_ref_levels_sync.py` 必须返回 0，并刷新 `data/btc_ref_levels.json`；若 `fapi.binance.com` 返回 403，脚本应自动 fallback 到 Binance spot / `data-api.binance.vision` 获取 recent high/low，TV SVP 仍是关键位权威源。
   - `hermes cron run <BTC关键位同步job>` 后 `last_status=ok`；不要只看手动脚本成功。
9. 代码有变更时提交推送；生成恢复报告并用 `hermes send -t telegram:-1003733144325:846` 推送。

## 关键代码教训

- `auto_card.py` 的管线完成度审计不能只打印 stdout；必须写入 `auto_card_*_full.md`，否则用户看文件/推送时仍不知道缺了哪一步。
- `GO/NO-GO` 的 `tv_live` 闸门不能只认 `engine_data._tv_pine` 或 `engine_data.tv`；正式链路也可能通过新鲜 `tv_dmi_cache.json` 生成 `_tv_main` / `_tv_override` / `_tv_cache_status.usable`。否则 TV已恢复仍被误判为红灯。
- Binance 步骤完成度不能只查不存在的 `engine_data.cmc`；应接受 `prices.futures`、`cmc_global`、`funding`、`oi` 或卡文本中的 Binance/CMC 证据。
- XAU 的 TV ⚠️ 在当前架构下是正确行为：SVP v10 依赖加密字段，OANDA:XAUUSD 不稳定返回完整 Pine 数据；必须拒绝 BTC TV 缓存污染，继续用 gold-api + 金十代理。

## 报告格式

恢复完成报告用窄 Markdown 表：健康状态、已恢复项、验证命令、异常项、产物路径。首句直接给结论，不写长篇计划。