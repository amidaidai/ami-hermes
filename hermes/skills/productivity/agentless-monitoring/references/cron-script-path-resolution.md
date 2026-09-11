# Cron 脚本路径解析与调试

> 历史记录（2026-08-31）：旧版路径排障记录；当前入口以仓库和 cron 实际配置为准。

## 核心规则

Hermes cron 的 `script` 参数（相对路径）从 `~/.hermes/scripts/` 解析，**不是从 workdir**。

```
script='btc_collector.py'  →  ~/.hermes/scripts/btc_collector.py
```

workdir 仅影响子进程的 CWD 和项目上下文文件（AGENTS.md 等），不影响脚本发现。

## 部署步骤

```bash
# 1. 将脚本复制到 cron 可发现位置
cp "D:/project/scripts/xxx.py" ~/.hermes/scripts/

# 2. 如果脚本有 import 依赖（同目录下其他 .py 文件）
cp "D:/project/scripts/dmi_decision.py" ~/.hermes/scripts/

# 3. 测试能否从目标目录运行
cd ~/.hermes/scripts && python xxx.py
```

## `last_run: ok` 的陷阱（重要）

`hermes cron list` 中显示的 `Last run: ok` **不等于脚本实际执行成功**。

`ok` 仅表示"cron 调度引擎已执行该任务"——引擎成功启动了子进程（Python）或者认为计划已触发。**脚本本身如果不存在于 `~/.hermes/scripts/` 下、Python import 失败、或脚本内部报错，仍可能显示 `ok`**。

**排查铁律**：只要看到 `last_run: ok` 但脚本行为异常（无输出、数据不更新），必须手动验证：
```bash
# 1. 确认脚本真的存在
ls -la ~/.hermes/scripts/<script_name>.py

# 2. 确认所有 import 依赖也在同一目录
grep "^import\|^from" ~/.hermes/scripts/<script_name>.py

# 3. 直接在 ~/.hermes/scripts/ 下手动运行测试
cd ~/.hermes/scripts && python <script_name>.py 2>&1

# 4. 检查脚本输出的状态文件（如果有的话）
cat ~/AppData/Local/hermes/data/<state_file>.json
```

### 典型场景复现（2026-06-23）

系统中 9 个 cron 全部显示 `last_run: ok`，但实际：
- 4 个脚本在磁盘上完全不存在（`清理守护.py`、`每日学习·社区进化.py`、`btc_collector.py`、`macro_poly_refresh.py`）
- 3 个虽然存在但在错误路径（代码在 `~/.hermes/scripts/` 但 cron workdir 指向 `D:/Hermes agent/scripts/`，Hermes 后备解析到 `~/.hermes/scripts/` 反而让它们能运行）
- 5 个缺失脚本对应的高频 cron（每分钟/每2分钟执行）每分钟都在静默失败，零通知

**结论**：`last_run: ok` 是 cron 引擎级别的成功，不是业务级别的成功。必须结合文件存在检查 + 手动运行验证。

## 排查流程

当 cron 报 `Script exited with code 1` 或怀疑静默失败时：

| 错误现象 | 根因 | 修复 |
|:--|:--|:--|
| `can't open file 'C:\\Users\\...\\xxx.py'` | 脚本不在 `~/.hermes/scripts/` | 复制脚本到该目录 |
| `ModuleNotFoundError: No module named 'yyy'` | import 依赖不在 Python path | 复制依赖到同目录 |
| 工作目录中测试正常但 cron 失败 | cron 解析路径与工作目录不同 | 确认脚本在 `~/.hermes/scripts/` |

## 已知坑

- **`~/.hermes/` = `/c/Users/Administrator/.hermes/`** (MSYS) 或 `C:\Users\Administrator\.hermes\` (cmd)
- **多脚本依赖**：`btc_alert_watch_v3.py` 需要 `dmi_decision.py` 在同一目录
- **workdir 错觉**：设置 workdir 不改变脚本路径，只改变 CWD 和 injected project context
