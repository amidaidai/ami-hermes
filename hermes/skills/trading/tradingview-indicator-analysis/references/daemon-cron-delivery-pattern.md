# 守护+Cron 双轨推送模式（2026-06-22 修复）

## 问题
`terminal(background=true)` 启动的守护进程输出不可见（stdout不推Telegram）。
仅cron的stdout能自动送达。单靠守护=检测到了但用户收不到。

## 架构

```
守护 (10s轮询)    → 检测触发 → 写入 btc_pending.txt
cron no_agent (1m) → 读 btc_pending.txt → stdout推Telegram话题
```

## 组件

| 组件 | 文件 | 作用 |
|------|------|------|
| 守护 | `scripts/btc_vwap_daemon.py` | 10s轮询，写pending + 状态文件 |
| 推送 | `scripts/btc_push_cron.py` | no_agent cron，读pending→清空→stdout |
| 状态 | `~/AppData/Local/hermes/data/btc_state.json` | 持久化当前状态（重启续接） |
| 日志 | `~/AppData/Local/hermes/data/btc_alerts.jsonl` | 调试用 |
| pending | `~/AppData/Local/hermes/data/btc_pending.txt` | 队列文件（大小约0.1KB） |

## 启动顺序

1. 启动守护：`terminal(background=true)` 不加 `notify_on_complete`
2. 创建cron：`cronjob(action='create', no_agent=True, script='btc_push_cron.py', schedule='1m', deliver='origin')`
3. 验证：守护写pending → 1分钟内cron读取并推Topic

## 注意事项

- 守护的 `background=true` 模式不加 `notify_on_complete`（避免退出时回推噪音）
- 杀守护用 `terminal("taskkill /PID <pid> /F")` 不用 `process(action='kill')`
- pending文件用 `---` 分隔多条消息，cron一次性推送
- 5分钟冷却窗口：同一事件同5分钟块只写一次pending
- 状态文件重启续接：`btc_state.json` 存VWAP + last_blocks，不丢跨重启事件

## 参考实现

- `scripts/btc_vwap_daemon.py` — 守护主体，含动态VWAP、10s轮询、状态持久化
- `scripts/btc_push_cron.py` — 推送桥梁，约20行
