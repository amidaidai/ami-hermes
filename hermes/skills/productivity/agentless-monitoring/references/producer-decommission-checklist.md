# 退役 / 暂停一个数据生产者（检查清单）

停一个生产者 ≠ `cron pause` 一下就完。要**同时把下游从「必须新鲜」重新定义**，
否则两种坏结局二选一：立刻天天假告警，或悄悄拿陈旧值算出看起来正常的错误结论。

适用于：停一个采集/同步 cron、归档一个守护、把某个品种从常驻改为按需。

## 清单（按顺序做，每步可验证）

1. **暂停**：`hermes cron pause <job_id>`；恢复是 `hermes cron resume <job_id>`。
   先扫一遍 `hermes cron list --all` 确认要停的是**哪些**作业（一个能力可能挂多条）。
2. **验证真的不再触发**（两件事都要做）：
   - `hermes cron list --all` 显示 `[paused]`（或 `jobs.json` 里 `enabled:false` / `state:paused`）
     —— **`hermes cron list` 默认不列 disabled 作业**，不带 `--all` 会让人以为作业被删了。
   - 等**原触发时刻过去之后**查 `executions` 表，确认没有新记录：
     ```bash
     python -c "import sqlite3;p=r'C:/Users/Administrator/AppData/Local/hermes/cron/executions.db';c=sqlite3.connect('file:'+p+'?mode=ro',uri=True);print(c.execute(\"select status,started_at from executions where job_id='<id>' order by rowid desc limit 3\").fetchall())"
     ```
     列表里的 `Next run` 在暂停后可能仍显示一个时间点——**以 executions 表为准**。
3. **把它的新鲜度检查从 `WATCH_FILES` 移到 `PAUSED_SOURCES`，并写明「暂停原因 + 恢复命令」**：
   - 留在 `WATCH_FILES` → 文件停更，立刻天天假告警；
   - 直接删掉 → 失去「为什么没在报」的可追溯性，下一个人会以为漏了监控。
   - 惯例是把「为什么没报」写在 `PAUSED_SOURCES` 的值里（连同 resume 命令）。
4. **审计下游对陈旧引用文件的依赖**：凡是拿「另一个生产者的产物」当**基准/校准值**的地方，
   都要加**时效闸**（超龄即视为不可用）。否则会用陈旧价算出看起来完全正常的错误结论。
   例：相关性矩阵拿 OANDA 现货价当代理腿的校准基准 → 停掉同步后必须改成「超龄即不校准、
   但仍明标是代理源」，而不是继续用一个几十分钟前的价。
5. **同步文档与测试**：知识库/回归里「该文件必须被监控」的断言要改成
   「暂停必须有据可查（指明哪条 cron + 如何恢复）」——否则回归变红，
   或更糟：留下与事实相反的指引，让下一个会话去修一个不存在的故障。
6. **确认按需路径仍可用**：如果停止的是常驻同步，检查调用方在数据不新鲜时是否能**现场拉一次**
   （并在文档里写清这条路径与它的代价，例如多花 1–2 分钟）。
   实测验证方式：手动跑一次那条被停的脚本，确认 exit 0 且产物时间戳更新。
7. **复扫**：`python scripts/data_freshness_watchdog.py report` → `healthy=True`、
   `active_count` 减少、`paused_sources` 里能看到该条。
8. 顺手：把「已退役、禁止再当 P0 报」的清单一并更新（心跳文件归档 + README + 检查清单同步）。

## 反面教训（都会真实发生）

- 只 pause 不改 `WATCH_FILES` → 下一轮新鲜度报告就开始报它的文件过期，看起来像新故障。
- 心跳文件停在几周前、`status` 仍写 `running`、进程早不存在 → 审计时差点报成「全系统瞎」。
- 把「停一个生产者」当成纯运维动作、忘了改回归 → 测试红了才发现有断言写死了旧策略。
