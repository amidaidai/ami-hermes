# Cron 推送可靠性排查记录

## 故障现象

用户设置了 BTC 价格看门狗，多次触发（可从状态文件确认），但用户从未收到推送消息。

## 根因

**`deliver="origin"` 在话题（thread）中创建的 cron job 无法可靠送达用户。**

无论 no_agent 还是 agent mode，系统均显示 `last_status: ok` 和 `last_delivery_error: null`，但消息从未出现在用户可见的聊天界面。这是**静默丢消息**。

## 排查过程

1. no_agent 脚本用 `deliver="origin"` → 状态文件显示触发，无 delivery error，用户没收到
2. agent-mode cron 用 `deliver="origin"` → 同样无 error，用户没收到
3. agent-mode cron 改用 `deliver="telegram:CHAT_ID:THREAD_ID"` → **用户立即收到**
4. no_agent 脚本改用 `deliver="telegram:CHAT_ID:THREAD_ID"` → 同样成功

## 验证方法

### 验证触发（确认脚本确实跑到了 print 语句）

```bash
# 看状态文件是否有对应 time stamp
cat ~/AppData/Local/hermes/data/.btc_watchdog_state.json
```

### 验证脚本输出（确认 print 内容正确）

```bash
cd ~/.hermes/scripts && python <script>.py
# 有输出 = 触发条件满足，应该推送
# 无输出 = 未触发
```

### 验证推送是否送达

```bash
cronjob action=list | grep <job_name>
# 看 last_delivery_error 字段
# 注意：null + ok ≠ 送达！
```

## 最终方案

**所有需要用户收到的 cron 推送，永远使用显式 delivery 目标：**

```python
deliver="telegram:-1003733144325:386"
```

通过 `cronjob(action='list')` 查看已有的、已知正常推送的 job，复制其 deliver 格式。

## 相关脚本修订历史

| 版本 | 时间 | 变更 |
|:--|:--|:--|
| v1 | 07:31 | no_agent, deliver=origin, 仅监控L1/L2 |
| v2 | 08:22 | +VWAP zone, 状态文件路径用__file__ |
| v3 | 08:55 | 状态文件改为~/AppData/Local/hermes/data/ |
| v4 | 09:04 | 全区间覆盖, MID兜底 |
| v5 | 09:00 (agent) | agent-mode cron, deliver=origin → 用户没收到 |
| v6 | 09:14 | agent-mode cron, deliver=telegram:... → 用户收到！ |
| v7 | 09:33 | no_agent, deliver=telegram:... (最终方案) |
