# Cron 全面审计工作流

当用户抱怨"任务太多/脚本警报/清理不干净"时，按以下步骤全面审计 cron 状态。

## 步骤 1: 列出所有活跃 cron

```bash
hermes cron list
```

重点记录：
- 每个 cron 的 `job_id`、`name`、`schedule`、`script`、`workdir`、`last_run` 状态
- 注意 `deliver` 目标（local vs telegram vs origin）
- 注意 `schedule` 频率（尤其是 `* * * * *` 每分钟执行的）

## 步骤 2: 验证脚本真实存在

```bash
# cron workdir 下的脚本
ls -la "D:/path/to/workdir/scripts/"
# Hermes 默认脚本目录（后备路径）
ls ~/.hermes/scripts/
```

比对 cron 列表中的 `script` 字段与磁盘上的文件：
- ✅ 存在且路径正确 → 正常
- ⚠️ 存在但只在 `~/.hermes/scripts/`（cron 从 workdir 找不到，但 Hermes 有后备）
- ❌ 完全不存在 → 静默失败（仍显示 `ok`）

## 步骤 3: 检查脚本依赖

如果脚本引用了 MCP server 路径（如 `server.js`、`tradingview-mcp`）：
```bash
ls -la D:/path/to/tools/tradingview-mcp/
```

不存在的依赖目录 = 该脚本必然失败。

## 步骤 4: 验证数据文件是否真的在更新

```bash
# 检查 data/ 目录下所有关键文件的修改时间
ls -la --time-style=full ~/AppData/Local/hermes/data/
```

关键判断：
- 文件 mtime 是几分钟前 → 可能有 cron 在写入
- 文件 mtime 是几小时前 → 数据采集 cron 可能失效
- 文件 mtime 与 cron schedule 匹配（如每分钟采集的每 60s 更新）→ 正常

## 步骤 5: 检查 jobs.json 存档

```bash
cat ~/AppData/Local/hermes/cron/jobs.json
```

此文件可能包含已暂停/已删除但未清理的旧记录。检查：
- `state: "paused"` vs `state: "active"` — 暂停的不执行
- `updated_at` — 确认最近的修改时间
- 残留的旧 job 不会影响执行，但占磁盘空间

## 步骤 6: 检查日志中的实际执行

```bash
# 检查各脚本的 log 文件
ls ~/AppData/Local/hermes/logs/*.log
tail -40 ~/AppData/Local/hermes/logs/freerouter.log  # 或其他特定脚本日志
```

关注：
- 日志中的 START 时间与 cron 的 `last_run_at` 是否吻合
- 单次执行耗时（START → DONE 的时间差）
- 脚本是否报错或中途退出

## 步骤 7: 手动运行验证

```bash
# 在终端中直接运行可疑脚本
python ~/.hermes/scripts/<name>.py
```

观察实际输出和错误 — cron 的 `last_status: ok` 完全不可靠。

## 步骤 8: 清理 — 删除全部并选择性重建

当用户说"全部删掉重新开始"时，分四层清理：

### 8a. 删除活跃 cron

```bash
# 获取所有 cron ID 并逐个删除
hermes cron list | grep -oE "^  [a-f0-9]{12}" | xargs -I{} hermes cron delete {}
```

注意：每个 `hermes cron delete` 调用之间 cron 调度器可能触发新执行。一次性获取所有 ID 再批量删除。

### 8b. 清理 cron 输出目录

```bash
rm -rf ~/AppData/Local/hermes/cron/output/*
```

`cron/output/` 下按 job_id 分目录存储了所有历史运行输出，累积可能数百个文件，全部可安全删除。

### 8c. 清空 jobs.json 存档

```bash
echo '{"jobs":[],"updated_at":"<当前ISO时间>"}' > ~/AppData/Local/hermes/cron/jobs.json
```

`cron/jobs.json` 可能含有已暂停/已删除但未随 `hermes cron delete` 清理的旧记录。直接覆盖为空数组确保无残留。

### 8d. 清理废弃数据文件

```bash
# 备份有用的历史数据
cp ~/AppData/Local/hermes/data/btc_history.jsonl /path/to/outputs/

# 删除废弃文件（保留 btc_history.jsonl）
rm -v ~/AppData/Local/hermes/data/btc_analysis_output.txt
rm -v ~/AppData/Local/hermes/data/btc_tv_data.json
rm -v ~/AppData/Local/hermes/data/BTCUSDT.P_*.json
rm -v ~/AppData/Local/hermes/data/detector_state.json
rm -v ~/AppData/Local/hermes/data/fetch_*.py
rm -v ~/AppData/Local/hermes/data/macro_snapshot.json
rm -rv ~/AppData/Local/hermes/data/screenshots/
# ... 其他废弃数据文件
```

同时清理 `D:/Hermes agent/` 等根目录下的孤立脚本（如 `_fetch_svp.py`、`scripts/btc_push_cron.py`）。

### 8e. 选择性重建

只重建用户确认保留的 cron。使用 `cronjob` 工具：

```python
cronjob(
    action='create',
    name='描述性名称',
    schedule='0 6 * * *',     # 5-field cron 表达式
    script='script_name.py',
    no_agent=True,              # 零 token 脚本模式
    workdir='C:/Users/<user>/.hermes/scripts',
    deliver='local',            # 如果脚本自身有 send_telegram()
)
```

## 步骤 9: 发送运行报告到 Telegram

清理完成后，用 `hermes send` 将报告发送到指定话题：

```bash
hermes send -t "telegram:CHAT_ID:THREAD_ID" "报告正文"
```

- `CHAT_ID` = Telegram 群组/频道的 ID（如 `-1003733144325`）
- `THREAD_ID` = 话题的 thread ID（如 `846`）
- 话题 ID 从消息链接获取：`https://t.me/c/<CHAT_ID>/<THREAD_ID>`
- 报告正文支持纯文本或多行字符串，不需要 markdown 格式化
- 适合：任务运行报告、清理完成通知、周期性状态摘要

`hermes send` 使用 Hermes 已配置的 Telegram bot 凭据发送，不经过 LLM agent 循环。

## Pitfalls

- ⚠️ `last_run: ok` = 调度器已启动，不等于脚本成功
- ⚠️ `hermes cron delete` 不终止已在执行的脚本进程
- ⚠️ cron 有两层存储: `hermes cron list` (活跃) + `cron/jobs.json` (存档)
- ⚠️ 脚本可能从 workdir 找不到但被 Hermes 从 `~/.hermes/scripts/` 后备加载
- ⚠️ 数据文件 mtime 持续更新不代表数据内容新鲜（可能只是重写一份旧快照）
- ⚠️ 删除数据文件前备份有用的历史数据（如 `btc_history.jsonl`）
- ⚠️ 清理 crons 后检查 `hermes cron list` 确认为空
- ⚠️ 清除 jobs.json 后重新检查 `hermes cron list` — 空的和暂停的从不同路径查询
- ⚠️ `hermes send` 的超时（15-30s）不等于发送失败 — 返回 `sent` 即确认送达
