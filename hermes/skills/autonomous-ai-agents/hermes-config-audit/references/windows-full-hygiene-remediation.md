# Hermes Windows 全面精简：安全处置顺序

用于“全面检查并优化、东西太多且杂乱”类任务。重点是先量化，再区分运行开销、提示词开销和磁盘占用，最后只做有回滚点的清理。

## 1. 先分三类，不要混为一谈

- **提示词/Token 膨胀**：启用技能数量、MCP schema、Memory/User Profile、SOUL/AGENTS、对话历史。
- **运行态杂乱**：活动/暂停 Cron、Gateway、插件、MCP 连通性、Curator 状态。
- **磁盘膨胀**：`state.db`、完整更新备份、状态快照、桌面 runtime、venv、node_modules、uploads。

磁盘体积大不一定增加每轮 Token；大量 bundled 插件显示为“not enabled”也不等于实际启用。

## 2. 推荐审计顺序

1. `hermes doctor`、`hermes status --all`、`hermes config check`。
2. 读取配置摘要：主模型、fallback、auxiliary、Tool Search、compression、skills.disabled、security、approvals、sessions、updates。
3. `hermes skills list` 读取**运行时**启用/禁用汇总；原始 `SKILL.md` 文件数只用于磁盘清点。
4. 逐个 `hermes mcp test <name>`，不要只看 enabled。
5. `hermes cron list --all`，区分 active、paused、last error。
6. `hermes sessions stats`，再对不同保留期做 `prune --dry-run`。
7. 分层统计 Hermes Home 和 Web UI 各一级目录体积。
8. 扫描近期日志并区分当前阻断与已恢复历史告警。

## 3. 技能精简

- 先确认 `tools.tool_search.enabled: on`。MCP 工具多时，这比删 MCP 更有效。
- `hermes skills list` 的 enabled/disabled 汇总是运行态权威值。
- `Path.rglob('SKILL.md')` 可能统计到重复包装、分类副本或支持目录，不能直接宣称为“启用技能数”。
- 按能力重叠和低频服务禁用，不删除交易、Hermes 管理、安全、文档、浏览、开发核心技能。
- 修改前备份 `config.yaml`；复杂 YAML 用 Python `yaml.safe_load/safe_dump`，修改后断言类型和值。

## 4. 会话清理

先 dry-run：

```bash
hermes sessions prune --older-than 30 --dry-run
hermes sessions prune --max-messages 0 --dry-run
```

确认后再清理：

```bash
hermes sessions prune --older-than 30 --yes
hermes sessions prune --max-messages 0 --yes
```

随后设置：

```yaml
sessions:
  auto_prune: true
  retention_days: 30
  vacuum_after_prune: true
```

### 重要解释

- 删除少量 session 后，`state.db` 可能几乎不变。
- 原因通常是消息正文仍多、SQLite 空闲页有限，以及同时维护 FTS 与 trigram FTS 两套索引。
- 报告时分开写“逻辑记录减少”和“文件体积减少”，不要承诺 prune 必然显著缩小数据库。
- 若30天内就有大量消息，继续减小数据库只能牺牲近期 session_search；需明确权衡。

## 5. Memory / User Profile

- 删除日期行情、任务完成日志、具体版本结果。
- 把重复偏好合并为5—10条短规则。
- 目标：Memory <50%，User Profile <60%。
- 报告前后字符数与条目数，说明是“合并压缩，不是清空偏好”。

## 6. 备份和磁盘清理

优先识别：

- `backups/tmp*.db`：可能是中断后遗留的临时数据库；先核对时间、有效备份数量和用途。
- 多份数百MB的 `pre-update-*.zip`：按明确保留策略留最新2—5份。
- 单独命名的人工数据库备份、唯一状态快照：默认保留，除非用户明确同意删除。
- 桌面 runtime、CLI venv、Node runtime：是独立运行环境，不因“重复”就手删。

推荐未来策略：

```yaml
updates:
  pre_update_backup: quick
  backup_keep: 2
```

删除前必须先列出目标、时间、大小和保留副本；删除后重新统计实际释放空间。

## 7. 安全与可逆性

- 若 `approvals.mode` 是布尔 `false`，视为高优先级安全问题，建议改为字符串 `smart`。
- 保留本轮 `config.yaml` 回滚点。
- 旧配置备份很多但体积很小时，优先移动到 `backups/config-archive/`，不要为了几十KB制造删除风险。
- Curator 建议 resume + prune-only；默认不启用 LLM consolidation，不自动删除技能。

## 8. 更新判断

`hermes --version` 显示“落后 N commits”不等于正式版本过期：

1. 比较本机版本与官方 releases 最新稳定版。
2. 查看 `origin/main` 的版本字段。
3. 若稳定版相同，而落后的只是未发布 main 提交，默认不要追 main 更新。
4. 有本地未跟踪或修改文件时，先报告并保留，不要为了消除 commit 数盲目更新。

## 9. 重启与验证

Windows 上 `hermes gateway restart` 可能在读取本地化子进程输出时出现解码告警，但命令也可能完成重启。不要凭 traceback 判失败；必须随后验证：

```bash
hermes gateway status
hermes doctor
```

最终验收至少包括：

- 配置字段断言通过。
- Gateway running。
- Doctor 通过。
- 逐个 MCP test 通过。
- Memory/Profile、技能启用数、session 数和磁盘体积有前后对比。
- 输出完整报告和配置回滚路径。
