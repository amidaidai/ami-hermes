# Telegram Cron 降噪排查

适用：用户反馈“任务报告太频繁”“Telegram 被 cron 刷屏”，但仍希望保留少数关键交易推送（如 X 情绪、Orion 雷达、关键位告警）。

## 标准流程

1. 列全量任务：`hermes cron list --all`，并备份 `~/AppData/Local/hermes/cron/jobs.json`。
2. 按 `deliver` 分组：找出所有 `telegram:<chat>:<thread>` 的任务，区分“用户想看”的信号和“维护/采集/任务运行报告”噪音。
3. 查最近输出：检查 `~/AppData/Local/hermes/cron/output/<job_id>/`，确认哪些任务每次都有非空 stdout。Hermes cron 会给 stdout 加 `# Cron Job: ...` 头，用户会感知成“任务报告”。
4. 保留高价值推送：例如 X 情绪、Orion 全市场雷达、雷达分析、关键位真实告警。
5. 降噪低价值推送：对维护、备份、数据采集、看门狗状态类任务执行 `hermes cron edit <job_id> --deliver local`，保留运行和日志，不再发 Telegram。
6. 查绕过 cron delivery 的脚本：搜索 `send_telegram`、`send_telegram_reliable`、`api.telegram.org`、目标 thread，例如 `telegram:-1003733144325:846`。脚本内直连 Telegram 不受 cron `deliver=local` 控制，必须同步改成只写日志/异常落盘/按需发送。
7. 验证：再次运行 `hermes cron list --all`，确保 Telegram delivery 只剩用户明确想看的任务；运行 `python -m py_compile` 检查被改 Python 脚本。

## 判断表

| 类型 | 默认处理 |
|---|---|
| X 情绪/市场情绪 | 保留 Telegram |
| Orion/全市场雷达/高置信雷达分析 | 保留 Telegram |
| 关键位真实告警/交易执行信号 | 保留 Telegram，必要时可靠优先 |
| 每日系统审计/备份/技能更新/模型同步 | 改 local，日志留存 |
| Dune/COT/Deribit/稳定币/清算/QLib 等采集刷新 | 默认改 local，供分析管线读取 |
| watchdog “alive/status” 输出 | 必须 local 或静默，不应推 Telegram |

## Pitfalls

- `deliver=local` 只影响 Hermes cron 的交付；脚本内部 Bot API 直发仍会继续刷屏。
- no_agent 脚本只要 stdout 非空，就会被 cron 记录并可能投递；成功无异常的采集脚本应尽量静默或只本地。
- 修改 cron 前先备份 `jobs.json`，便于恢复用户原配置。
- 不要删除用户喜欢的交易信号任务；先按偏好保留，再降噪维护类任务。