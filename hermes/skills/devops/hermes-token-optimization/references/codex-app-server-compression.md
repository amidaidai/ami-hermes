# Codex App Server 压缩路由排查

## 适用症状

- 反复出现 `Session context ... exceeds the model context window ... with compression disabled`
- 配置实际显示 `compression.enabled: true`
- 模型为 `openai-codex`，且上下文先增长到模型上限附近才报警

## 根因判别

1. 查看 `config.yaml` 的 `compression` 段，确认 `enabled`。
2. 查看 `compression.codex_app_server_auto`：`native` 会让 Hermes 跳过自身 preflight；只有原生 Responses compaction 真正接管时才安全。
3. 查看 `compression.codex_responses_native` 是否显式开启，以及 `agent.log` 中是否存在原生 compaction 的实际调用/成功迹象。
4. 若日志显示请求持续超过模型 context window，而没有成功 compaction，判定为“路由跳过 + 接管缺失”，不是全局 enabled 失效。

## 已验证修复

使用 Hermes 官方配置命令，避免直接改写受保护的配置文件：

```bash
hermes config set compression.codex_app_server_auto hermes
hermes config set compression.codex_responses_native false
hermes config check
```

保持 `compression.enabled: true`，然后重启 CLI/Desktop。配置在进程启动时读取，当前进程不会动态获得新路由。

## 复核标准

- `hermes config check` 成功
- 新进程实际加载 `codex_app_server_auto=hermes`
- 长会话在约 `compression.threshold` 处触发 Hermes compaction，而不是先超过 provider context limit
- 不能只凭配置写入成功宣称修复；应以新会话日志或实际压缩行为验收

## 注意

`/compact` 是当前会话的应急动作；它不替代重启。若会话已无法处理新消息，直接重启并新建会话。不要把一次性超限数字或具体 session ID 写进技能。