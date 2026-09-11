# 批准关键位过期恢复实测（2026-09-02）

## 症状分层

- `keylevel_guard.py` 进程和 `.keylevel_guard_heartbeat.json` 都新鲜，但 `.keylevel_guard_health.json` 为 `degraded`、`active_approved_levels=0`。
- `btc_keylevel_guard_watchdog.py` 以 exit 2 报错。这不是守护崩溃，而是业务配置安全闸门生效。
- 旧 `monitor_heartbeat.json`、`.btc_daemon_heartbeat.json` 过期不应直接判 P0；先确认旧脚本是否已经退役、是否由 `keylevel_guard` 替代。

## 已验证恢复流程

1. 运行 `python scripts/keylevels_collect.py`。它串行切换 D/4h/1h/15m/5m，每周期等待指标重算并校验图表品种/周期，成功后写 `data/keylevels_candidates.json`。
2. 核对候选根字段：`symbol=BINANCE:BTCUSDT.P`、`tf=15`、`source=tradingview_mcp`、时间戳新鲜、候选非空。
3. 人工选择平衡的结构集合（价值区、会话位、HTF上下磁吸），写入 `data/keylevels_config.json`，每条带相同候选来源和明确有效期。候选池状态保持 `candidate_pool_only`，不自动批准。
4. 执行 `python scripts/btc_keylevel_guard_watchdog.py`，实测从 exit 2 恢复为 exit 0；健康文件变为 `status=ok`、`active_approved_levels=8`。
5. 用 `hermes cron run <watchdog-id>` 触发精确任务，再用 `hermes cron list --all` 读回，确认看门狗与到价读取任务均 `last_status=ok`。
6. 运行 `python scripts/audit_preflight.py`，确认 `批准关键位: OK active=8 configured=8`；随后关键位契约测试和全量回归通过。

## 关键判定

- **进程健康 ≠ 业务健康**：必须同时看心跳和有效批准位。
- **安全停机 ≠ 代码故障**：有效位为0时退出2是预期行为。
- **候选 ≠ 批准**：自动把新候选池整体写进批准源属于越权。
- **恢复 ≠ 改成永不过期**：默认仍保留有效期，过期后安全降级。若用户明确给出持久授权，可在 `keylevels_config.json` 设置 `auto_approval_policy.enabled=true`、`scope=existing_levels_only`，由 `btc_keylevel_guard_watchdog.py` 到期前自动续期；该策略绝不能把候选池升格为批准位，也不授予交易执行权。
- **自动续期必须可审计**：保留 `ttl_hours`、`renew_before_minutes`、`authorized_at/by`，每次更新 `approval_renewal`；策略 scope 非 `existing_levels_only` 时必须 fail-closed。
- **授权有效 ≠ 结构仍有效**：持久续期必须再受 `max_structure_age_hours` 与 `structure_reviewed_at` 约束。单次续期的 `valid_until` 不得超过结构审查截止时间；超过最大结构寿命后，守护、健康检查和自动续期都要 fail-closed，等待人工重审，不能用无限续期掩盖旧价漂移。
- **五周期续航与批准续期是两条链**：关键位 watchdog 只管批准有效期；BTC TV 五周期与 SourceSnapshot 需由独立 no-agent 任务按严格 TTL 提前刷新。任务必须 `deliver=local`、共享 TV 锁、错峰执行、以新发布验证成功并恢复进入前的图表身份。
- **成功调用 ≠ 成功恢复**：外部Cron状态必须读回精确任务，不能只看命令返回；共享图表恢复还需在任务完成后实际读取 symbol/timeframe/studies。

## 共享 TV 与性能修复的已验证模式（2026-09-04）

- BTC 五周期续航使用独立 no-agent 入口，按 20 分钟节奏检查、以 22 分钟作为提前刷新门槛，从而在 30 分钟严格契约前续航；SourceSnapshot 单独按 45 分钟门槛检查。新鲜时零采集、零输出。
- BTC/XAU 后台采集必须在同一 TV lease 内完成“主周期行动格刷新＋配对验证”，最后才恢复进入状态。恢复后等待 20 秒并读回身份；真实做过 XAU→BTC→XAU 与 BTC→XAU→BTC 双向验收。
- 截图若分析前置已经验证 symbol/timeframe/studies，可直接复用当前图表并截图；若不匹配才切图、等待 20 秒、复核后截图。不要固定再切一次，否则既增加延迟又可能截到旧行动格。
- Quick 性能先用 cProfile 区分本地 CPU 与外部等待。若耗时集中在独立 REST 请求，可对 K线周期和衍生品只读端点做小规模有界并发；TradingView 切图、FinalVerdict 和 gate 仍必须串行。实测该模式保持全字段覆盖并显著降低 Binance 墙钟时间。
- 结构寿命必须是消费侧共同契约：watchdog 负责续期时截断 `valid_until`，guard 的活动计数和事件循环也要检查同一 `structure_reviewed_at + max_structure_age_hours` 截止时间。只在写入侧限制会让已运行的旧 guard 继续消费过期结构；代码升级后应重启守护并回读新 PID/心跳。
