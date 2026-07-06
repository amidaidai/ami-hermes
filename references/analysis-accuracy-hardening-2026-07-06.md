# 棠溪分析准确度硬化记录 · 2026年7月6日

## 本次修复目标

把“能力存在”推进到“分析流程真实使用能力”，重点处理四类失真来源：

| 问题 | 风险 | 修复 |
|---|---|---|
| source_snapshot 年龄未进入 GO/NO-GO | 数据新鲜度闸门只看默认 24h，不能真实反映刷新情况 | `auto_card.py` 新增 `_refresh_and_mark_snapshot()`，每次出卡先刷新并写入 `_snapshot_age_h` |
| XAU 无活跃监控位时快照不刷新 | 行情守望 heartbeat 正常，但 `source_snapshot_XAUUSD.json` 可过期数天 | `行情守望.py` 新增 `maybe_refresh_source_snapshot()`，即使无 active levels 也按 5 分钟节流刷新 |
| 只把 BTC/ETH 当加密 | SOL/山寨/股票期货产品会误走 stock 分支，跳过 Binance 衍生品与 CG Pro | `auto_card.py` 改用 `_asset_class()` 统一路由，所有 USDT 合约走 crypto |
| 实际 R:R 不写回 meta | 复盘 predicted_grade 与 GO/NO-GO 读不到真实 `rr_a/rr_b` | `render_card_locked()` 计算 ATR 止损目标后写回 `meta.rr_a/rr_b/rr1/rr2` |
| GO/NO-GO 取 A/B 最大 R:R | 主线 `rr1<2` 但反向 `rr2>=2` 时错误显示 GO | `go_nogo_gate.py` 改为主线 `rr_a/rr1` 硬闸，主线不足直接 `NO-GO·rr_ratio` |
| BTC情绪串入非加密卡 | XAU/外汇/股票被 BTC Fear&Greed、CG 社区、BTC Polymarket 误导 | `auto_card.py` 对非加密跳过 CoinGecko社区面板、BTC/crypto Polymarket、BTC x_sent 缓存，改用本品种热点/宏观替代 |
| Windows管道/cron stdout 句柄异常 | `render_v8.py` import 时 `sys.stdout.reconfigure()` 可抛 OSError，导致出卡中断 | 增加 `_safe_reconfigure()` 捕获 `OSError/ValueError` |

## 新的准确度执行规则

1. 每次正式出卡前先刷新 `source_snapshot_{symbol}.json`，刷新失败也必须把失败原因写入 `engine_data._snapshot_refresh_error`。
2. GO/NO-GO 的 `data_freshness` 只读真实 `_snapshot_age_h`，不得再依赖默认值判断。
3. `data_freshness_watchdog.py` 必须同时监控 BTC 与 XAU 快照，以及 Deribit / Dune / QLib / Orion / X 情绪 / TV live 等关键源。
4. 行情守望必须在没有 active levels 时继续刷新 source snapshot；监控位过期不能让行情快照停摆。
5. `render_v8.py` 的 TV 行必须优先展示 `_tv_main` 归一化后的 grade/treatment/position；不能因为表格键名是中文就显示“待现场读取”。
6. 非加密资产明确 HALDRO 不适用；加密资产如果 HALDRO 与 SVP 主驾驶强冲突，`go_nogo_gate.py` 的 `dual_indicator` 闸门红灯。
7. R:R 闸门以主线 `rr_a/rr1` 为准，不取 A/B 最大值；主线不足 1:2 时 GO/NO-GO 必须红灯。
8. 非加密资产不得读取 BTC/crypto 的 CoinGecko 社区、Polymarket、BTC x_sent 缓存；只允许使用本品种热点、宏观、金十/COT/对应市场数据。
9. 终端/cron/管道场景下，输出编码重配置必须 fail-open，不能因为 stdout/stderr 句柄异常中断分析。

## 验证命令

```bash
cd "D:/Hermes agent"
python -m py_compile scripts/auto_card.py scripts/render_v8.py scripts/行情守望.py scripts/data_freshness_watchdog.py scripts/watchdog.py scripts/pipeline_router.py scripts/go_nogo_gate.py
python -m pytest tests/test_format_alignment.py tests/test_dual_indicator_gate.py tests/test_pipeline_router.py -q
python -m pytest -q
python scripts/p0_refresh_all.py
python scripts/data_freshness_watchdog.py
python scripts/auto_card.py BTCUSDT
python scripts/auto_card.py XAUUSD
```

## 运行态检查

| 检查 | 期望 |
|---|---|
| `data/source_snapshot_BTCUSDT.json` | age < 30 分钟 |
| `data/source_snapshot_XAUUSD.json` | age < 30 分钟 |
| `data/monitor_heartbeat.json` | status=running 且 age < 2 分钟 |
| `data/tv_dmi_cache.json` | 对 BTC 新鲜；XAU 不得吃 BTC 缓存 |
| `auto_card BTCUSDT` | 管线显示 10 步，full card 含双指标裁决、GO/NO-GO、管线完成度；若 `rr1<2.0` 则必须 `NO-GO·rr_ratio` |
| `auto_card XAUUSD` | 拒绝 BTC TV 缓存与 BTC/crypto 情绪缓存，显示 XAU 专属降级原因 |
