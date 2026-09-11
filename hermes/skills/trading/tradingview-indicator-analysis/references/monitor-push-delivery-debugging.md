# 监控警报推送送达诊断（v7.5+）

用于用户问「为什么监控警报没推送/推送有问题/事件里写 push_sent 但 Telegram 没收到」时。

## 先分四类，不要先猜

1. **没触发**：价格未进入 near/breach 条件。
2. **触发但策略拦截**：事件禁做、降噪、价格异常熔断。
3. **已入队但未送达**：push 队列接受了消息，但 Telegram/Bot API/CLI 发送失败。
4. **送达但话题错误**：target 路由错误或 message_thread_id 不对。

## 必查顺序

1. 查 heartbeat：确认 `行情守望.py` 当前进程活着，且版本是预期版本。
2. 查 `data/monitor.log` 最近 100-200 行：
   - `事件禁做 ...` = 主动静默，不是发送失败。
   - `降噪不推送 ...` = 阈值/位信/数据等级未达到，不是发送失败。
   - `数据异常熔断 ...` = 价格源跳变/快照异常，主动不推。
   - `推送成功 telegram:...` = Telegram 真实返回成功。
   - `推送失败/推送超时/推送异常 telegram:...` = 发送链路问题。
3. 查 `data/monitor_events.json` 最近事件：看 `type/tier/push_reason/trigger_kind`，但不要只信旧版 `push_sent`。
4. 最小化验证 Telegram 直连：用 `telegram_direct.send_telegram_direct('telegram:-1003733144325:846', '诊断')` 发到报告话题，确认 Bot API 和 token 是否正常。

## 关键教训：push_sent 语义

旧版 `行情守望.py` 的 `push_sent=True` 只代表「消息已入队」或「hermes_cli 子进程执行过」，不等于 Telegram 真实送达。尤其旧兜底逻辑没有检查 `subprocess.run().returncode`，即使 CLI 发送失败也可能被记作成功。

v7.5+ 应保证：

- `_send_one()` 返回 True 只代表真实发送成功。
- Telegram 直连失败要写明 `推送失败 {target}: telegram_direct {reason}`。
- CLI 兜底必须检查 `returncode`，失败写 stderr/stdout 摘要。
- `push()` 异步入队仍可快速返回，但日志必须能区分「入队」和「送达」。

## 推送路由锁定

- BTC 警报：`telegram:-1003733144325:386`
- XAU 警报：`telegram:-1003733144325:385`
- 其他警报：`telegram:-1003733144325:416`
- 任务报告/巡检/复盘：`telegram:-1003733144325:846`

用户提供 `https://t.me/c/{chat}/{topic}` 时，以数字 chat/topic 为准，不要依赖 target list 是否枚举该话题。

## 修复后验证

1. Python 编译通过。
2. 重启守望：杀 `data/monitor.lock` PID，删 lock/heartbeat，用 Hermes venv python 启动。
3. 心跳 age < 30s。
4. `monitor.log` 出现新版启动行。
5. 触发下一条真实警报时，日志能看到 `推送成功/失败` 的真实结果。
