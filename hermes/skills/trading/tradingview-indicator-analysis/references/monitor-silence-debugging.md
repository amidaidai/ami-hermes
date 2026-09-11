# 监控静默排查与修复

当棠溪问“怎么没有发过来/是不是没监控”时，优先按下面顺序主动排查，不要先解释。

## 快速判断

1. 看 `data/monitor_heartbeat.json`：`status=running` 且时间新，说明行情守望在线。
2. 看 `data/monitor.log` 最近 20 行：区分“没触发”和“触发但降噪不推送”。
3. 看 `data/monitor_state.json`：检查 `BTCUSDT:data_fail_count`、`XAUUSD:data_fail_count`、`noise_history`、`last_alerts`。
4. 看 `data/trade_events.jsonl` 最近事件：如果有 `push_sent=false` 或 `push_reason`，说明监控在工作但被规则静默。
5. 看 cron：`信号巡检` 必须 active、`every 1m`、`no-agent`、last run ok。

## 本轮沉淀的关键坑

- 10s 查价不等于 10s 推送；但不能完全静默到让用户误以为没监控。`信号巡检.py` 应周期性输出“监控正常”心跳卡。
- 严格推送阈值不能过高。高优先级、强触发、数据非 C 的 warning，位信 75 左右就应允许推送；否则 75-77 的可用提醒会被静默。
- XAUUSD 金十Quote单源是当前允许的正常降级状态。单源最高 C 级，但“单源 C 级 + 有有效价格”不等于行情不可用，不应触发连续 C 级熔断。
- XAU 的数据熔断应针对：无价格、快照过旧、异常跳价、非允许来源连续失败；不要把“金十Quote单源有效价”当失败。
- 如果用户怀疑 Telegram 没收到，允许发送一张简短“信号巡检 · 监控正常”验证卡，确认链路。

## 推荐修复方向

- `行情守望.py`：`MIN_WARNING_LEVEL_SCORE` 保持 75 左右，不要恢复到过严的 78+。
- `行情守望.py`：`anomaly_check()` 对 XAUUSD 增加 `single_quote_ok` 判断，金十Quote有效价不累加 data_fail_count。
- `信号巡检.py`：无异常时每约 30 分钟输出一次正常状态卡，内容说明“10s查价不等于10s推送；低位信/弱确认会记录不推送”。
- `信号巡检.py`：历史 system anomalies 只取最近窗口，例如 15 分钟，避免旧异常一直污染健康提醒。

## 回答口径

用卡片式直接说明：

- 监控是否在线。
- 为什么没推送：没触发、降噪、熔断、Telegram链路哪一种。
- 已修复什么。
- 当前心跳、主动品种、cron、推送链路验证结果。
