# 2026-06-29 驾驶舱策略/模板/任务稳定性审计教训

## 触发场景
用户要求“全面检查分析策略、分析模板、分析驾驶舱、分析流程、能力、任务为什么总出问题，并全网/社区/TradingView/Reddit/X 对照”。此类任务不是单纯代码审计，必须同时覆盖：运行态、模板源头、router流程、cron/daemon、复盘治理、Git锁定、社区最佳实践。

## 本轮实测发现的关键模式

### 1. cron 绿灯不等于系统健康
审计必须先查 daemon 心跳，再查 cron。实案：20 个 cron 多数 `last_run=ok`，但 `data/monitor_heartbeat.json` 已 7.8h 未更新，实时监控实际失明。报告中要明确区分：
- cron 采集层：脚本是否跑过
- daemon 实时层：行情守望 / BTC daemon 是否新鲜
- cache 数据层：source_snapshot / protections / strategy files 是否新鲜
- agent 分析层：auto_card 是否实测可跑
- 推送层：Telegram/话题/乱码/降级是否真实送达

### 2. Git 锁定是 P0 级生产治理
若 `git status --short` 出现大量 `M` 和 `??`，即使功能看似存在，也不能宣称“已锁定”。实案：100+ modified、20+ untracked，许多新能力（data_freshness_watchdog、qlib_factors、stablecoin_collector、x_sentiment_collector 等）未跟踪。结论应写为“能力存在但未锁定，迁移/reset/update 后可能丢失”。

### 3. 模板源头与用户偏好必须同源
审计必须读取 `references/master-template-v68.md`，并与用户当前偏好比对。实案：模板为 v8.0 叙事风格且写“禁止表格”，但用户当前偏好是表格驱动（多周期定位表、关键位矩阵、多源交叉验证表、预案表）。这是 P1：输出风格反复漂移的源头冲突。修法不是只改某次回复，而是更新权威模板。

### 4. Router 声称覆盖必须实测每类资产
不要只看文档声称“6类资产全覆盖”。用 `pipeline_router.route_pipeline(symbol, mode)` 实测代表品种：BTCUSDT、XAUUSD、EURUSD、AAPL、ES1!/CL1!、期权示例。实案：ES1! quick 正常，但 full 返回 `[]`，说明期货 full route 未闭合。

### 5. auto_card 能跑不代表数据可信
必须跑 BTC + XAU smoke test，并检查 stdout 中的降级/缓存/品种提示。实案：
- BTC：`CMC cannot import cmc_quote`、TV DMI 缓存过期 480min、风控 `0.00U上限`、高低价异常
- XAU：TV DMI 缓存品种不匹配 `BINANCE:BTCUSDT.P`、K线简化占位、风控 `0.00U上限`
这些不是崩溃，但会让卡片执行建议不可信，应列 P1。

### 6. 复盘闭环是策略能力的一部分
审计不仅数 plans/events，还要算 reviews/plans。实案：342 plans / 12 reviews，复盘率 3.5%。按 Trader’s Second Brain 等社区共识，交易质量 A/B/C 评分应在成交/平仓后尽快落盘；否则模型无法根据执行质量升降权。

### 7. 社区对标要落成“差距表”，不是泛泛引用
本轮有效来源与提炼：
- Freqtrade Protections：StoplossGuard、MaxDrawdown、CooldownPeriod、LowProfitPairs；保护层必须可回测且状态新鲜。
- Trader’s Second Brain：A/B/C 交易质量评分，A亏优于C赚，两个C级当天停止。
- Reddit r/algotrading：Walk-forward、OOS、forward test、避免 regime/参数同源过拟合。
- TradingView/Pine：footprint/volume delta 能力增强；TV现场值应成为主源，缓存只降级。
- Bookmap/CVD：CVD背离、冰山吸收、stop-run 必须和结构位结合。

## 推荐审计输出结构
使用表格而非长段叙事：
1. 截图首行（若涉及 BTC/XAU/TV）
2. 一句话总判定
3. 当前真实运行状态表
4. 为什么任务总出问题（根因表）
5. 社区对标表
6. 能力同步矩阵（声称/实测/结论）
7. P0/P1/P2 修复顺序
8. 下一步建议执行包

## 验证命令清单（摘要）
- `git status --short && git log -1 --pretty='%h %ci %s'`
- 数据新鲜度：读取 monitor_heartbeat、btc_daemon_heartbeat、source_snapshot、tv_dmi_cache、protections_state、strategy_governance、strategy_model_stats
- `hermes cron list` + jobs.json 交叉
- `python -m pytest tests/ -q --tb=short`
- `python hermes/scripts/auto_card.py BTCUSDT` 与 `XAUUSD`
- `pipeline_router.route_pipeline()` 覆盖 6 类资产
- TV MCP：health_check、chart_get_state、capture_screenshot(full)
