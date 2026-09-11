---
name: system-ops
description: 系统运维技能 — 进程管理、磁盘/内存监控、日志轮转、定时任务配置、环境变量管理、文件系统操作。适用于本地开发环境和服务器维护场景。
category: devops
---

# System Operations

## 进程管理

```bash
# 查看进程
ps aux | grep python
ps auxf  # 树形结构

# Windows 用 tasklist
tasklist | findstr python

# 杀掉进程
kill -9 PID                     # Linux/Mac
taskkill /F /PID PID            # Windows
pkill -f "hermes"               # 按名称

# 后台运行（Linux/Mac）
nohup python server.py > output.log 2>&1 &
# 或
setsid python server.py &

# 查看端口进程
lsof -i :8000                   # Linux/Mac
netstat -ano | findstr :8000    # Windows
```

### ⚠️ 在 git-bash/MSYS 下 `taskkill /PID` 会失败

`taskkill /F /PID 11468` 在 git-bash 终端里**报错**而非杀进程：bash 把 `/PID` 当成路径参数，返回 `无效选项 - 'C:/Program Files/Git/PID'`（或 `taskkill /?` 用法提示）。这是 shell 解析问题，不是权限问题。

**可靠替代（PowerShell `Stop-Process`）**——在任意 shell 都可用：
```powershell
powershell -NoProfile -Command "Stop-Process -Id 11468,14240,22236 -Force -ErrorAction SilentlyContinue"
```
若需在 Python 子进程（`subprocess`）里批量 kill，优先走 `Get-CimInstance` 取 PID 列表再 `Stop-Process`（参见下方「查找残留进程」），避免在 bash 里调 `taskkill`。

> 注：Windows 原生 CMD 里 `taskkill /F /PID 11468` 是正常的；只有在 Hermes 终端的 git-bash 下才会中招。要确认到底用 bash 还是 cmd，看 `echo $SHELL` / 进程名（`bash` vs `cmd.exe`）。

## 磁盘监控

```bash
# 磁盘使用
df -h
du -sh /path/to/dir
du -sh * | sort -rh | head -10  # 最大的10个目录

# Windows
wmic logicaldisk get size,freespace,caption

# inode 使用
df -i

# 大文件查找
find / -type f -size +100M -exec ls -lh {} \; 2>/dev/null
```

## 内存/CPU

```bash
# 内存
free -h                         # Linux
cat /proc/meminfo               # 详细信息

# CPU
top -b -n 1 | head -20          # 一屏
htop                            # 交互（如已安装）
mpstat 1 5                      # 各 CPU 使用率

# 按资源排序进程
ps aux --sort=-%mem | head -10  # 按内存
ps aux --sort=-%cpu | head -10  # 按CPU
```

## 日志管理

### 日志轮转（logrotate）
```bash
# /etc/logrotate.d/myapp
/var/log/myapp/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

### Windows 日志轮转锁冲突（PermissionError rotate）

**症状**: Hermes gateway 或其他常驻进程持有 `agent.log` 文件锁，导致日志轮转时 `os.rename(source, dest)` 报 `PermissionError: [WinError 32] 另一个程序正在使用此文件，进程无法访问。`

**应急截断**: `cat /dev/null > /path/to/agent.log` — 在 MSYS/Git-Bash 中可截断被其他进程持有的日志文件（截断不要求独占锁，重命名要求）。轮转失败但日志 < 10MB 可不处理；超过 50MB 必须截断，避免磁盘占满。

**根治**: 重启 gateway (`hermes gateway restart` 或 `taskkill //F //PID <gateway_pid>` 后重新拉起)，但这会中断所有 cron 任务。低风险时段（凌晨）执行。或者在 Python 日志配置中使用 `copytruncate` 风格的 handler 而非默认的 rename 轮转。

### Python 日志配置
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
```

### 日志分析
```bash
# 统计错误频率
grep -c "ERROR" app.log
grep "ERROR" app.log | cut -d' ' -f3 | sort | uniq -c | sort -nr

# 跟踪实时日志
tail -f app.log
tail -f app.log | grep --line-buffered "ERROR\|WARN"

# 查看特定时间段
awk '/2026-01-01 09:00/,/2026-01-01 10:00/' app.log
```

## 定时任务

### Cron Job 健康审计

当用户说"查任务/查监控/监控有问题"时，执行全量 cron job 健康检查。逐项判 health: error/timeout/silent/disabled/deliver 缺失。详细检查清单和修复方法见 `references/cron-health-check-checklist.md`。

#### “一直失败”必须区分历史记录与当前状态

Hermes cron output 会长期保留旧的 `script failed` 文件；任务页面出现红色历史条目，不等于任务当前仍失败：

1. 先以 `jobs.json` / `hermes cron list --all` 的 `last_status` 和 `last_run_at` 判当前状态。
2. 再扫描 output 历史，分别列出历史失败时间与最近成功时间，禁止把旧失败概括成持续故障。
3. 对曾失败任务逐个 `hermes cron run <id>`，看到 `Ran now: succeeded` 后再次核对 `last_status=ok`。
4. output正文里的 `❌陷阱`、`❌暴跌增仓`等业务信号不是任务错误；只有 `Status: script failed`、`Script exited`、timeout、Traceback算执行失败。
5. 不为消除红色而删除历史证据；向用户说明UI保留历史运行记录。

#### 新鲜度阈值必须匹配采集频率

看门狗阈值短于cron间隔会制造周期性假告警。规则：

- `freshness_threshold >= cron_interval × 1.2`，常取1.25倍覆盖网络与调度抖动。
- 每2小时采集建议2.5小时；每3小时采集建议3.5小时。
- 时间新但内容坏仍告警，时间与内容质量分开判断。
- “发现业务异常”不等于脚本崩溃：健康检查应输出告警但exit 0；仅脚本自身不可执行时exit非0。
- 修改后现场运行看门狗；健康状态应exit 0且零stdout，再跑回归测试。

关键检查点：
- `cronjob(action='list')` 拿全量 → 逐项判 state/status/deliver
- 检查输出文件密度和质量
- 对照驾驶舱数据源清单确认无缺失 cron
- no_agent 超时 120s → 脚本优化；LLM 高频 → 转 no_agent

### Linux cron
```bash
# 编辑 crontab
crontab -e

# 常用格式
*/5 * * * * /path/to/script.sh              # 每5分钟
0 9 * * 1-5 /path/to/job.py                  # 工作日9:00
0 0 * * 0 /path/to/weekly_report.sh          # 每周日0:00
@reboot /path/to/startup.sh                  # 开机启动
```

### Windows 任务计划（schtasks）
```bash
# 创建每日9点任务
schtasks /create /tn "MyTask" /tr "python script.py" /sc daily /st 09:00
```

### Python schedule（轻量）
```python
import schedule
import time

def job():
    print("Running...")

schedule.every(5).minutes.do(job)
schedule.every().day.at("09:00").do(job)
schedule.every().monday.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
```

### Hermes cron 全面清理工作流

当需要彻底清除所有 cron 任务时（例如脚本丢失、任务堆积、重新配置），`hermes cron delete` 只删除了调度记录，但还有三个地方可能残留：

1. **活跃 cron list** — `hermes cron delete <id>` 逐个删除
2. **cron 存储文件** — `~/AppData/Local/hermes/cron/jobs.json` 中的暂停任务（paused jobs 不显示在 `hermes cron list` 但仍在存储中）
3. **cron 输出记录** — `~/AppData/Local/hermes/cron/output/` 下的历史输出文件

**完整清理步骤：**

```bash
# 1. 删除所有活跃 cron
hermes cron list | grep -oE "^  [a-f0-9]{12}" | awk '{print $1}' | while read id; do
  hermes cron delete "$id"
done

# 2. 清空 cron 存储（包括暂停任务）
echo '{"jobs":[],"updated_at":"2026-06-23T17:10:00+08:00"}' > ~/AppData/Local/hermes/cron/jobs.json

# 3. 清理输出记录
rm -rf ~/AppData/Local/hermes/cron/output/*

# 4. 验证
hermes cron list  # → "No scheduled jobs."
```

**注意**：`hermes cron list` 只显示活跃任务，不显示已暂停的。暂停任务仍会消耗存储和文件，必须从 `jobs.json` 中清除。

### Hermes cron「幽灵消息」陷阱

**现象**：删除 cron 后，仍在 Telegram 收到该 cron 脚本发出的消息。

**根因**：`hermes cron delete` 只从调度器中移除任务，**不能中断已经在执行中的进程**。如果脚本正在运行（尤其是耗时 3-5 分钟的 OpenRouter API 遍历+健康检查），删除操作无法 kill 它。

**时间线示例**：
```
17:04:33  → 脚本被调度触发（START）
17:05-06  → 用户执行 hermes cron delete
17:09:10  → 脚本完成，send_telegram() 发出消息
```

**解决方案**：
1. 先 kill 进程再删除 cron：`ps aux | grep script_name.py | grep -v grep`
2. 或等脚本自然结束再操作
3. 修改脚本本身的 `send_telegram()` 为有条件推送（如 `change_count > 0` 才发）

### Cron 输出表格格式化标准

当用户说"表格多一点/表格的形式"或"同步到各个渠道"时，所有面向 Telegram/飞书/Discord/本地报告 的 no_agent cron 脚本应使用 Markdown 管道表。详细约束和已应用脚本清单见 `references/cron-output-table-format.md` 与 `references/telegram-mobile-routing.md`。

核心规则：首行结论 + 恰好3张真实Markdown管道窄表 + 每表≤3列；表头+分隔符必须存在；数字对齐（`${:,.0f}` / `{:+.1f}%`）；中文列名优先；方向用 ↑↓→ 箭头；禁止假表格、文字对齐、4列以上宽表、长段落和尾注总结。

棠溪手机端强约束：
- 默认「首行结论 + 恰好3张Markdown管道表」，每表≤3列；避免宽表、假表格、文字对齐、长段落和尾注总结。
- 每张表必须有表头行和分隔行，例如 `| 来源 | 方向 | 证据 |` + `|:----|:---:|:----|`；不能用空格或破折号冒充表格。
- 每行必须放具体数据（价格、百分比、数量、状态、触发条件），不要只写“偏空/需关注/正常”。
- 对 LLM cron：把上述格式铁律直接写进 cron prompt，禁止让模型自由发挥。
- 对 no_agent cron/daemon：改脚本 `print()` 输出本身；成功健康时仍保持零输出，只在异常/决策时输出3表。
- 排查顺序：先 `cronjob list` 找 `deliver=telegram` → 再扫脚本内 `send_telegram`/`api.telegram.org`/`telegram_direct` → 分别修 prompt 和脚本直连输出。

### Cron 告警去重

防止 alert fatigue（刷屏疲劳）：`scripts/alert_dedup.py` 提供 MD5 hash 去重 + 强制间隔机制。详细接口和分级策略见 `references/cron-alert-dedup.md`。

模式：`dedup_wrapper("job_name", output, force_seconds=1800)` 替代裸 `print()`。

### Telegram cron 降噪

当用户反馈“任务报告太频繁”“Telegram 被 cron 刷屏”时，先保留用户明确想看的交易信号（如 X 情绪、Orion 雷达、关键位告警），再把维护/备份/采集/看门狗状态类 cron 改为 `deliver=local`。同时必须搜索脚本内 `send_telegram` / `api.telegram.org` / 目标 thread，避免脚本绕过 cron delivery 直连 Telegram。详细 runbook 见 `references/telegram-cron-noise-triage.md`。

**棠溪交易任务路由矩阵**：用户确认保留 Orion 雷达、X情绪LLM分析、每日技能SkillMCP更新、每日系统审计、每日系统备份、BTC关键位同步；BTC守护只在异常/重启时推；数据新鲜度看门狗属于后台体检，默认 local，不推 Telegram；Dune/Deribit/QLib/清算/稳定币/COT/宏观Poly 等采集默认 local。具体频率、脚本降噪模式、内容 hash 去重、低置信雷达落盘不推见 `references/telegram-cron-routing-matrix.md`。手机端推送必须优先采用“首行结论 + 恰好3张Markdown窄表 + 每表≤3列”，LLM cron prompt 要内嵌该铁律；详见 `references/telegram-mobile-routing.md`。数据新鲜度误报/双落盘路径排查见 `references/tangxi-data-freshness-watchdog.md`。

**Telegram推送审计铁律**：用户问“我的任务有哪些 / 为什么不推电报 / 哪些推到电报”时，不能只看 cron 的 `deliver`。必须同时审 `jobs.json`、解析脚本路径、扫描脚本内 `send_telegram`/`api.telegram.org`/`telegram_direct`，并单独列出常驻 daemon 和手动推送脚本。`deliver=local` 只能说明 cron delivery 不推；脚本直连仍可能推。详细检查清单见 `references/telegram-delivery-audit-checklist.md`。

### Cron 清理工作流

删除 cron 后同步清理输出目录：

```bash
hermes cron remove <job_id>
rm -rf ~/AppData/Local/hermes/cron/output/<job_id>
```

**另一个陷阱**：脚本发送 Telegram 的方式可能与 cron 的 `deliver` 设置不同。脚本内部的 `send_telegram()` 通过 Telegram Bot API 直接发送，不受 cron 的 `deliver: local` 限制。检查脚本是否自带独立的推送逻辑。

**⚠️ 守护进程（daemon）同样会幽灵推送**：不仅 cron 有这个问题。通过 `terminal(background)` 启动的常驻轮询脚本（`while True: sleep(N)`），即使删除 `.py` 文件，已在内存中运行的进程仍会继续轮询和推送。删除守护脚本前必须先 `taskkill` 杀掉所有匹配的进程实例。详见 `realtime-watchdog-daemon` 技能的「🧹 Removing a Daemon」和「🔴 Deleting the script file does NOT stop running processes」pitfall。

### Cron 输出文件路径排查

**场景**：cron 的 `last_status=ok` 但找不到输出文件。

**根因**：脚本内部的 `DATA_DIR` 常量与你的预期路径不一致。很多采集脚本写 `os.path.expanduser("~/AppData/Local/hermes/data")` 而非项目目录 `D:/Hermes agent/data/`。

**排查步骤**：
1. `cronjob(action='list')` 确认脚本路径（`script` 字段）
2. 用 `cat` 或 `read_file` 查看脚本，找 `DATA_DIR`、`os.path.join`、`DATA_ROOT` 等路径常量
3. 在该路径下找输出文件：`ls -la ~/AppData/Local/hermes/data/<script_prefix>* 2>/dev/null`
4. 验证文件内容是否正常——cron 可能是静默成功，只是路径不同

**典型案例**：`stablecoin_collector.py` 写 `DATA_DIR = os.path.expanduser("~/AppData/Local/hermes/data")`，输出 `stablecoin_snapshot.json`。在 `D:/Hermes agent/data/` 下搜不到但数据一直正常。

**警惕**：这种路径分裂不影响功能，但用 `ls data/` 做健康检查时会漏掉。审计时应该检查脚本的 DATA_DIR，而不是假设路径。

### Cron 排期冲突检测与错峰分散

**场景**：Hermes cron 列表中大量 cron 的 schedule 落在相同分钟标记（`:00` / `:30`），多个 no_agent 脚本同时触发，争夺 CPU/网络带宽/API 速率限。

**检测方法**：
1. `cronjob(action='list')` 获取全量列表
2. 提取每个 cron 的 `schedule` 和 `name`
3. 按分钟分组，重点关注 `:00`、`:30` 等热门标记
4. 同时触发 ≥3 个 cron 就需错峰

**错峰原则**：
- 同频 cron 至少间隔 ≥5 分钟
- no_agent 采集脚本优先分散到独立分钟
- LLM cron（带 skills）安排在对应采集脚本之后 5-10 分钟，形成采集→分析管道
- 每2小时/每小时的 cron 可以错开到整点区间内任意分钟

**推荐错峰间距（每30分频次，9-23点版同理）**：
```
:02 → 脚本A（采集优先）
:07 → 脚本B（分析，滞后采集5分钟）
:12 → 脚本C
:17 → 脚本D
:22 → 脚本E
:27 → 脚本F
:32 → 脚本A（第二循环）
:37 → 脚本B
...
```

**每15分频次**：分散到 `3,18,33,48 * * * *` 等偏移分钟，避开 `*/15` 默认的 `:00/:15/:30/:45`。

**每2小时频次**：`5 */2 * * *`、`35 */2 * * *` 等，确保不与每30分的 cron 在 `:30` 撞车。

**重点检查模式**（用户说"怎么有重复的"时优先查这三项）：
| 模式 | 表现 | 解法 |
|------|------|------|
| 多个 `*/30 * * * *` | 全部卡 `:00/:30` | 错峰到 `:02/:32`、`:12/:42` 等 |
| `30 */2 * * *` + `*/30 * * * *` | 每2小时在 `:30` 撞车 | 改到 `:05` 或 `:35` |
| `0 10,22 * * *` 与其他同时段 | 每天固定时间撞车 | 调为 `:05` 或 `:10` |

**验证**：修改后 `cronjob(action='list')` 确认每个 cron 的 `next_run_at` 错开，同分钟无 ≥2 个 cron。

#### 查找残留进程（脚本文件已删，但进程仍在跑）

`taskkill` 需要 PID。当脚本文件已被删除且无法通过文件名 grep 时，用 PowerShell 的 `Get-CimInstance` 查找所有 python 进程并过滤命令行参数中的脚本名：

```powershell
# 查找所有名为 hype_daemon 的 python 进程
Get-CimInstance Win32_Process -Filter "Name='python.exe' AND CommandLine LIKE '%hype_daemon%'"
  | Select-Object ProcessId,CommandLine | Format-Table -AutoSize
```

等价于 `pgrep -f hype_daemon` 的 Windows 原生方法。

**多实例可同时存在**：同一个 nohup/background 脚本可能被重复启动多次，导致多个实例并行执行。所有匹配的进程都需要被 kill。循环 kill：

```bash
# 先用 Get-CimInstance 查出所有 PID
for pid in $(powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe' AND CommandLine LIKE '%hype_daemon%'\" | Select-Object -ExpandProperty ProcessId"); do
  taskkill //F //PID "$pid"
done
```

**验证清理完成**：再次运行 `Get-CimInstance` 查询，输出为空即表示无残留进程。

**🟡 为何 `tasklist | findstr` 在 MSYS bash 中不适用**：`tasklist /V` 输出的命令行通常被截断超过 80 字符，无法可靠匹配长脚本路径。`Get-CimInstance` 返回完整 `CommandLine` 字段（不截断），是 Windows 上查找特定脚本进程的可靠方法。

## Windows no_agent Cron 编码陷阱

### 问题

在 Windows 上，Hermes no_agent cron 脚本的标准输出（stdout）被 Python 以 `cp936`（GBK）编码写入管道，而非 UTF-8。如果脚本 `print()` 输出中文或 emoji，Hermes 网关收到的是 GBK 乱码字节而非原文。Telegram 上呈现为 `馃煛 绔欏洖VAL` 之类的乱码。

### 修复

在 no_agent cron 脚本的最开头（import 之后，任何 print 之前）添加两行：

```python
import io, sys
# 强制 stdout/stderr 以 UTF-8 编码输出，防 Windows GBK 乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
```

**注意**：设置 `PYTHONIOENCODING=utf-8` 环境变量在 Hermes cron 子进程管道中无效，必须用 `TextIOWrapper` 在代码层强制编码。

### 文件写入不受影响

Python 3 的 `open()` 默认以 UTF-8 写入文件，所以 `write_pending(msg)` 写入 `btc_pending.txt` 时不会乱码。问题只出现在 `print()` → stdout 管道 → Hermes gateway → Telegram 这条链路上。

### 定位方法

如果 cron 推送出现乱码，检查：

1. 确认系统 locale：`python -c "import locale; print(locale.getpreferredencoding())"` — Windows 上输出 `cp936` 即易感
2. 看 cron job 的 `last_status` — 即使正常也可能输出乱码
3. 对比原始中文字符/emoji 和 Telegram 上看到的乱码模式：`馃煛`=`🟡`、`绔欏洖`=`站回`、`浠穈`=`价\``

### 推送内容格式

当 no_agent cron 脚本读取 `btc_pending.txt` 并输出时，注意：

- **分隔线过滤**：如果 pending 文件中使用 `---` 作为多条消息的分隔，务必在输出前过滤掉这些行，否则 Telegram 会渲染为纯文本 `---`，破坏排版
- **方向标注**：每条告警首行应标注方向（`↑做多` / `↓做空` / `○等待`），让用户一眼知道操作倾向
- **分割方法**：按告警首行（emoji+关键词）而非空行来切分消息块，因为连续写入 pending 的多条告警之间没有空行分隔

## 环境变量管理

```bash
# 查看
echo $PATH
env | grep HERMES

# Windows (PowerShell)
# $env:HERMES_HOME

# 设置临时
export MY_VAR=value

# 持久化（~/.bashrc 或 ~/.bash_profile）
echo 'export MY_VAR=value' >> ~/.bashrc

# 代理相关环境变量
export HTTP_PROXY="http://127.0.0.1:7897"
export HTTPS_PROXY="http://127.0.0.1:7897"
export ALL_PROXY="http://127.0.0.1:7897"

# 不走代理的域名/地址（逗号分隔，支持通配）
export NO_PROXY="localhost,127.0.0.1,api.example.com"

# 注意：小写版本（http_proxy, https_proxy）同样重要——部分 CLI 工具只读小写
export http_proxy="http://127.0.0.1:7897"
export https_proxy="http://127.0.0.1:7897"

# 查询当前代理状态
env | grep -i proxy

# Hermes 桌面 App 继承系统环境变量，在终端会话中自动注入
# 修改 ~/.bashrc 后新终端生效；修改 Windows 系统环境变量需重启应用

### Hermes CLI 在 PowerShell 中不可用

**症状**: 在 Windows PowerShell 输 `hermes` 报「无法将"hermes"项识别为 cmdlet、函数、脚本文件或可运行程序的名称」。

**根因**: `hermes.exe` 所在目录 `~\.hermes-web-ui\desktop-runtime\hermes\<version>\win-x64\python\Scripts\` 不在 Windows 的 User PATH 中。Hermes Desktop 只在启动 Git Bash 时把该目录加入 PATH（通过 `declare -x PATH=...`），但不修改 Windows 系统环境变量。PowerShell 使用 Windows 原生的 PATH 查找，看不到该目录。

**修复（Windows User PATH 添加）：**
```powershell
# 在 PowerShell 中以管理员或当前用户身份执行
[Environment]::SetEnvironmentVariable(
  'Path',
  [Environment]::GetEnvironmentVariable('Path', 'User') +
    ';C:\Users\<用户名>\.hermes-web-ui\desktop-runtime\hermes\<version>\win-x64\python\Scripts',
  'User'
)
```

**验证：**
```powershell
# 重新打开 PowerShell，输
where.exe hermes
# 应返回两条：
#   ...\Scripts\hermes.cmd
#   ...\Scripts\hermes.exe
```

**替代方案（不用改 PATH）：**
- 直接在 Git Bash 中运行（Hermes Desktop 的终端默认就是 Git Bash）
- 在 PowerShell 中输 `hermes-agent`（`hermes-agent.exe` 已在 `~\.hermes\hermes-agent\venv\Scripts\` 的 PATH 中）
```

## 代理配置

Windows 环境下代理通常由 Clash Verge / v2rayN / NekoRay 等客户端管理。Hermes 桌面 App 继承系统环境变量中的 `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`。

### 检测当前代理

```bash
env | grep -i proxy               # 查看代理环境变量
curl -s --max-time 10 -o /dev/null -w "HTTP_CODE:%{http_code} TIME:%{time_total}s IP:%{remote_ip}\\n" \
  https://httpbin.org/get        # 走代理测试（默认走）
curl -s --max-time 10 --noproxy '*' -o /dev/null -w "HTTP_CODE:%{http_code} TIME:%{time_total}s IP:%{remote_ip}\\n" \
  https://httpbin.org/get        # 直连测试（跳过代理）
# 对比两条命令的 TIME —— 代理 > 直连倍数倍属正常，直连不通 = 被墙
```

### API 端点批量连通性测试

当需要检查多个 API 中转站/LLM 端点的网络连通性和延迟时：

```bash
# 批量测试 /v1/models（GET，仅需任意 key）
for url in \
  "https://api.aijws.com/v1/models" \
  "https://api.yairouter.com/v1/models" \
  "https://timicc.com/v1/models" \
  "https://api-slb.micuapi.ai/v1/models" \
  "https://api.deepseek.com/v1/models"; do
  code=$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "$url" -H "Authorization: Bearer sk-test" 2>/dev/null)
  time=$(curl -s --max-time 10 -o /dev/null -w "%{time_total}s" "$url" -H "Authorization: Bearer sk-test" 2>/dev/null)
  echo "$url → $code ($time)"
done

# 批量测试 /v1/chat/completions（POST）
for url in \
  "https://api.aijws.com/v1/chat/completions" \
  "https://api.yairouter.com/v1/chat/completions"; do
  result=$(curl -s --max-time 20 -o /dev/null -w "%{http_code}" -X POST "$url" \
    -H "Authorization: Bearer sk-test" \
    -H "Content-Type: application/json" \
    -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}' 2>/dev/null)
  echo "$url → $result"
done
```

**返回码含义**: 401 = 网络通但 API key 无效（预期行为）; 200 = 正常; 502 = 服务端源站挂了（Cloudflare 报 origin bad gateway）; 301 = 需要重定向到 www 前缀; 超时/连接失败 = 网络不通或被墙。

**502 诊断**: Cloudflare 的「Error 502: Bad gateway — origin web server returned an invalid or incomplete response」表示 AI 中转站的源站（实际运行模型的服务器）宕机或过载，不是客户端网络问题。换模型名或等一段时间再试。

### Clash Verge 代理客户端

Clash Verge 是 Windows 上常见的代理客户端，配置文件位置：

```bash
# verge.yaml（主配置）
%APPDATA%/io.github.clash-verge-rev.clash-verge-rev/verge.yaml

# 关键字段
enable_system_proxy: true         # 是否开启系统代理
use_default_bypass: true          # 是否使用默认 bypass 列表
system_proxy_bypass: null         # 自定义 bypass 域名（默认 null）
verge_mixed_port: 7897            # 混合代理端口（HTTP/SOCKS5）
enable_external_controller: true  # 是否开启外部控制 API
```

#### Clash Verge 客户端导入、External Controller 与节点质量检测

当用户要“像推文那样在 Clash 客户端显示”某个 Clash 配置生成/检测工具的结果时，目标通常不是只启动 Web UI，而是：开启 Clash Verge External Controller → 让工具能切换/检测节点 → 生成 `_checked.yaml` → 用 `clash://install-config` deep link 导入 Clash Verge 客户端显示带标签的节点名。详细 runbook 见 `references/clash-verge-client-integration.md`。

当用户只是想知道“我的节点怎么样/哪些好用”，不要默认把检测结果导入客户端或污染原订阅；优先按 `references/clash-node-quality-checking.md` 生成独立节点质量报告。只有用户明确要求客户端显示时，才导入 `_checked.yaml`；用户要求删除时，必须同时清理 `profiles.yaml` 与 `profiles/` 下 deep link 导入生成的 remote/merge/script/rules/proxies/groups 关联文件。

关键坑：
- 只改 Web 工具配置不够；Clash Verge 的 `verge.yaml` 里 `enable_external_controller` 要为 `true`，运行时 `clash-verge.yaml` 里要有 `external-controller: 127.0.0.1:9097` 和匹配的 `secret`。
- 修改后必须重启 `clash-verge.exe` 与 `verge-mihomo.exe`，再用 `curl -H 'Authorization: Bearer <secret>' http://127.0.0.1:9097/version` 验证。
- 生成/导出的 YAML 需要由本地 HTTP 服务可访问，然后打开 `clash://install-config?url=<encoded_url>&name=<encoded_name>`；验证 `profiles.yaml` 出现新 `remote` 条目。


**配置域名直连（不走代理）：**

```yaml
# verge.yaml 中修改
system_proxy_bypass: api.aijws.com    # 单个域名
system_proxy_bypass: "*.example.com,api.test.com"  # 多个域名（引号包裹）
```

改完后在 Clash Verge → 设置 → 关闭再开启「系统代理」使之生效。或者检测本机是否有 clash-verge.exe 进程，有则说明需要在 UI 中切换。

**确认生效：**
1. 检验域名直连：`curl --noproxy '*' -s https://api.aijws.com/v1/models ...`
2. 检查 NO_PROXY 环境变量已包含该域名：`env | grep NO_PROXY`

**定位 clash-verge.exe 进程：**
```bash
tasklist | grep -i clash-verge
```

### 临时绕过代理（当前会话有效）

```bash
# 方式 A：添加到 NO_PROXY
export NO_PROXY="$NO_PROXY,api.aijws.com"

# 方式 B：curl 级别绕过
curl --noproxy 'api.aijws.com' https://api.aijws.com/v1/models ...
curl --noproxy '*' https://api.aijws.com/v1/models ...  # 全局跳过

# 方式 C：Python requests 级别
import os
os.environ["NO_PROXY"] = os.environ.get("NO_PROXY", "") + ",api.aijws.com"
```

### 永久绕过

1. **Clash Verge 用户**：配置 `system_proxy_bypass`（见上），下次 Clash 重新应用系统代理时生效
2. **直接设系统环境变量**（通过 Windows 系统属性的「环境变量」→ 编辑 `NO_PROXY`），新终端/新应用生效
3. **写入 shell profile**（bashrc/zshrc）：`echo 'export NO_PROXY="$NO_PROXY,api.aijws.com"' >> ~/.bashrc`

### 注意事项

- Hermes 桌面 App 继承系统环境变量，修改后需 **完全重启 Hermes Studio**（关掉所有 `Hermes Studio.exe` 进程）才能在新会话生效
- Clash Verge 的 `use_default_bypass: true` 表示在系统默认 bypass 列表（localhost、127.0.0.1、::1 等）基础上追加 `system_proxy_bypass` 的内容
- 当前终端 `export NO_PROXY` 只影响当前 shell 及其子进程，不影响其他窗口或 Hermes 后端进程
- 要验证配置是否真正写入：`cat "$APPDATA/io.github.clash-verge-rev.clash-verge-rev/verge.yaml" | grep system_proxy_bypass`

## 文件系统操作

```bash
# 符号链接
ln -s /target/path /link/path

# 查找 + 批量操作
find . -name "*.log" -mtime +30 -delete                         # 删除30天前日志
find . -name "*.py" -exec chmod 644 {} \;                       # 改权限
find . -type d -empty -delete                                   # 删空目录

# 压缩/打包
tar czf archive.tar.gz /path/to/dir
zip -r archive.zip /path/to/dir
```

## Cookie-based CLI 认证配置

部分 CLI 工具（twitter-cli、rdt-cli 等）没有传统的 OAuth flow，而是通过浏览器 session cookie 来认证。用户通常用 Cookie-Editor 扩展导出 Header String 格式的 cookie。

### 通用处理流程

```python
from http.cookies import SimpleCookie
# 或用 ; 手动分割（处理超长 JWT 时更可靠）
cookies = {}
for part in cookie_string.split(';'):
    part = part.strip()
    if '=' in part:
        k, v = part.split('=', 1)
        cookies[k.strip()] = v.strip()
```

**解析方式选择**：
- `SimpleCookie` — 标准方式，适合常规 cookie。但遇到**超长 JWT token**（如 token_v2 等 1300+ 字符）时，如果字符串在传递过程中被截断，SimpleCookie 可能解析失败（只解析到截断点前的 cookie）。
- 手动 `split(';')` — 更健壮，能处理部分截断的 cookie 字符串。即使 JWT 中间被截断，仍能提取正确的 key/value 对、保留正确的 cookie 数量。

### 各工具配置方式

#### twitter-cli

```bash
# 安装
pip install twitter-cli

# 方式 A：通过 agent-reach configure（推荐）
agent-reach configure twitter-cookies "auth_token=xxx; ct0=xxx"

# 方式 B：环境变量（持久化到 bashrc）
export TWITTER_AUTH_TOKEN="your_auth_token"
export TWITTER_CT0="your_ct0"
```

**注意**：Twitter/X 在中国大陆被墙，需设置代理。有些工具仅读取小写 `http_proxy`（不读大写 `HTTP_PROXY`），务必同时设置：

```bash
export http_proxy="http://127.0.0.1:7897"
export https_proxy="http://127.0.0.1:7897"
```

验证：`twitter status` 应返回 `authenticated: true` 并显示用户名。

#### rdt-cli

```bash
# 安装（PyPI 版本落后，从 GitHub 装）
pip install 'git+https://github.com/public-clis/rdt-cli.git'

# 认证方式 A：从浏览器提取（浏览器已登录 reddit.com）
rdt login

# 认证方式 B：Cookie-Editor 导出后手动写入 credential.json
# cookie 存储位置：~/.config/rdt-cli/credential.json
# 格式：{"cookies": {"reddit_session": "...", ...}, "source": "manual:cookie-editor", "saved_at": timestamp}
```

**关键 cookie**：`reddit_session` 是唯一必需的 cookie。`rdt status` 应显示 `authenticated: true`。

**Pitfall**：reddit_session 是 JWT token，值可能 700+ 字符。完成配置后测一次实际读取：`rdt sub python --limit 3`。

#### 通用注意事项

- Cookie 凭据只存在本地
- Cookie 有有效期，需定期刷新
- 推荐为 cookie-based 平台使用专用副账号
- 批量 cookie 优先走 `agent-reach configure --from-browser <browser>` 命令

#### ⚠️ Chrome 127+ App-Bound 加密：自动化 Cookie 提取失效

Chrome 127 起引入了 App-Bound 加密（当前版本 149，持续升级中）。`rookiepy`、`browser-cookie3` 等 cookie 提取工具无法解密新格式的 cookie，报错 `decrypt_encrypted_value failed` 或 `Unable to get key for cookie decryption`。这不是工具问题，是 Chrome 主动收紧了安全边界。

**影响范围**：所有依赖 `rookiepy`/`browser-cookie3` 的自动化流程（Agent-Reach 的 `configure --from-browser`、rdt login、Cookie 自动提取等）。

**两套方案**：

1. **Cookie-Editor 扩展手动导出**（推荐，最靠谱）
   - 安装扩展：https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm
   - 在浏览器中登录目标网站，点 Cookie-Editor → Export（JSON 或 Header String）
   - 手动配置：
     * Agent-Reach: `agent-reach configure <platform>-cookies "<header-string>"`
     * 雪球：通过 Python 脚本写入 `~/.agent-reach/config.yaml` 的 `xueqiu_cookie` 字段
     * rdt-cli：将 cookie 写入 `~/.config/rdt-cli/credential.json` 的 `cookies` 字段

2. **Playwright 开新会话**（无头浏览器）
   - 适合无 Chrome 可用但需登录的场景
   - `playwright.chromium.launch()` → `context.add_cookies()` → 导航到目标站完成登录 → `context.cookies()` 导出
   - 需交互式登录（Snowflake / QR code 等），不能完全静默

## Windows Python Web 工具安装与验证

当用户给 GitHub Python/FastAPI/Playwright 小工具并要求“安装这个”时，不要停在 clone 或 pip install。按 `references/windows-python-webapp-install.md` 执行：克隆到 `D:/Hermes agent/projects/`、创建 `.venv`、安装依赖/Playwright、用 Hermes background process 启动服务、curl + Playwright 打开页面并保存截图。若首页报 `TemplateResponse` / `TypeError: unhashable type: 'dict'`，优先检查 Starlette 新版参数签名，将旧式 `templates.TemplateResponse("index.html", {"request": request})` 改成显式 `request=..., name=..., context=...` 后重启验证。

## Windows 便携式 CLI 安装

当 winget/scoop/choco 在 Git-Bash 中不可用时，下载 portable zip 是最可靠的路径。**MSI 静默安装**（`msiexec /i ... /quiet`）在 Git-Bash 中常静默失败（exit 103, 权限不足），便携式 zip 不需要管理员权限。

通用模式：

```bash
# 1. 下载 portable zip
cd /tmp
curl -L -o tool.zip "https://github.com/org/repo/releases/download/vX.Y.Z/tool_windows_amd64.zip"

# 2. 解压到独立目录
unzip -o tool.zip -d tool_extract

# 3. 安装到 ~/.local/bin
mkdir -p ~/.local/bin
cp tool_extract/bin/tool.exe ~/.local/bin/

# 4. 添加到 bashrc PATH（一次性）
grep -q 'local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# 5. 当前会话生效 + 验证
export PATH="$HOME/.local/bin:$PATH"
tool --version
```

**Pitfalls**:
- `which` 有时找不到刚安装的 exe（PATH 缓存），用绝对路径验证：`~/.local/bin/tool.exe --version`
- 解压出的目录名不固定，先 `ls` 确认再复制
- 当前 shell 需要用 `export PATH=...` 才能立即生效；新终端窗口才自动读 `.bashrc`
- Python pip 安装的 CLI 工具若进了 venv，只在激活该 venv 时可用

详细命令和更多场景（gh CLI、mcporter 配置路径陷阱、yt-dlp 配置、非 PyPI Python 包安装）见 `references/windows-portable-cli-install.md`。

## 第三方 Agent CLI 工具安装与验证

当需要从 GitHub 安装第三方的 AI agent 工具（如 Agent Reach 等）并验证其能力时：

1. 克隆仓库：`git clone https://github.com/org/repo.git && cd repo`
2. 安装：`pip install -e .`（editable 开发安装）
3. 运行内置诊断：`python -m module.cli doctor`
4. **直接验证**：不要只看 doctor 报告，直接运行每个后端工具确认其真实可用状态

### ⚠️ 重要陷阱：Doctor 假阴性

内置诊断可能因为子进程超时过短而误报"未安装"。例如 rdt-cli (Reddit CLI) 首次响应约 12s，而部分 diagnostic tool 的超时可能只有 10s，导致误判。**总是直接用后端工具二次确认：**

```bash
rdt status --json     # Reddit → authenticated: true
twitter status        # Twitter → authenticated: true
gh auth status        # GitHub
```

### 渠道可用性速查

| 层级 | 典型渠道 | 认证要求 |
|------|---------|---------|
| 零配置 | GitHub / YouTube / V2EX / RSS / 网页 | 无 |
| 需配置 | Twitter / Reddit / B站 / 小红书 / 雪球 | Cookie / OAuth |
| 复杂 | 小宇宙 / LinkedIn | API Key / MCP 服务 |

详细信息见 `references/third-party-agent-tool-install-and-verify.md`。

## 任务运行报告生成

每次执行运维类任务（清理/审计/修复/脚本运行）后，应生成结构化任务运行报告并推送到指定渠道。适用于 cron 任务和手动执行。

### 报告结构

详细样式约束和 no_agent 退出码规则见 `references/hermes-cron-report-style-and-no-agent.md`。

```
## 任务运行报告

| 项目 | 内容 |
|---|---|
| 任务 | {任务名称} |
| 时间 | {开始时间} → {结束时间} |
| 状态 | ✅ 成功 / ❌ 失败 |

## 执行流程

1. {步骤1}
2. {步骤2}
3. {步骤3}

## 关键指标

| 指标 | 值 |
|---|---|
| {指标1} | {值} |
| {指标2} | {值} |

## 耗时详情

| 阶段 | 耗时 |
|---|---|
| {阶段1} | {时长} |
| 总计 | {总时长} |

## 下次运行

{cron 描述} / 手动触发
```

### 报告分段规则

1. **头部**: 用普通 Markdown 表格展示任务名、时间范围、状态（✅/❌）
2. **执行流程**: 用普通数字编号（1/2/3），不要用①②③或装饰性分隔线
3. **关键指标**: 实际度量（删除数量、耗时、成功率等），优先用中文表格
4. **耗时详情**: 各阶段耗时分解
5. **下次计划**: 是否有定期执行
6. **语言风格**: 尽量中文；除 API、PID、cron、job、error、OK、路径、命令、专有名词等大众通用英文外，不主动夹英文
7. **禁止样式**: 不使用 `══════════`、`━━━` 等装饰性分隔符

### Hermes no_agent Cron 维护脚本模式

日常维护任务（系统审计、备份、技能/SkillMCP 更新）推荐使用 **no_agent 模式**的 Python 脚本：
- 脚本就是任务本身，stdout 直接交付
- **静默原则**：全正常时零输出（不产生噪音），仅异常时输出报告
- 异常输出会自动触发 Telegram 推送（配合 cron 的 deliver 设置）

#### 脚本结构模板

```python
#!/usr/bin/env python3
"""每日XXX — 时间点 cron，仅异常时输出"""
import sys, subprocess, os, time, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
REPO_ROOT = Path("D:/Hermes agent")
LOG_DIR = REPO_ROOT / "outputs" / "maintenance-logs"

def run(cmd: list[str], timeout=120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"Timeout after {timeout}s"
    except Exception as e:
        return 999, repr(e)

def main() -> int:
    start = datetime.now(TZ)
    lines = [f"══════════ 任务运行报告 ══════════",
             f"任务：每日XXX", f"时间：{start.strftime('%Y-%m-%d %H:%M:%S')}", ""]
    issues = []

    # ── 执行检查 ──
    # check_1() → issues append only when problem
    # check_2() → ...

    if not issues:
        # 完全静默成功
        return 0

    # 仅异常时输出；no_agent 语义是 stdout 非空即推送。
    # 注意：发现异常 ≠ 脚本失败，返回 0；只有脚本崩溃/采集不可执行才应非零，避免 cron 被标记 error。
    print("\n".join(lines))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

#### 部署步骤

1. 脚本放 `~/.hermes/scripts/`（Hermes cron 的解析根目录）
2. 同时复制到项目 `hermes/scripts/repo-maintenance/` 做版本控制
3. 创建 cron job：
   ```bash
   hermes cron create --name "任务名" --script "script_name.py" --no-agent "分钟 小时 * * *"
   ```
4. 退出码 1 时 stdout 被 cron 捕获并 push

#### 审计维度（daily_system_audit.py）
| 维度 | 检测内容 |
|------|----------|
| 技能完整性 | `skill_integrity_guard.py --json` → 行号污染 / frontmatter 损坏 |
| MCP 连通 | `hermes mcp test <name>` 逐个测 8 服务器 |
| Hermes doctor | `hermes doctor` 输出中的 warnings |
| 磁盘空间 | `shutil.disk_usage()` → 可用 < 10% 报警 |
| Git 状态 | `git status` + 落后提交数 |
| 日志异常 | 扫描最近 5 个 .log 中的 error/traceback |

#### 维护维度（daily_skill_mcp_update.py）
| 维度 | 检测内容 |
|------|----------|
| Hub 技能 | `hermes skills check` → 有更新则自动 update |
| Curator | `hermes curator run` → 归档过期技能 |
| MCP 测试 | 逐个 `hermes mcp test` 验证连通性 |
| Hermes 升级 | 子进程调 `daily_hermes_official_update.py` |

#### 现有脚本（~/.hermes/scripts/ + 仓库副本）

| 时间 | 任务 | 脚本 |
|------|------|------|
| 06:00 | 每日系统备份 | `daily_private_repo_backup.py` |
| 06:30 | 每日系统审计 | `daily_system_audit.py` |
| 07:00 | 每日技能/SkillMCP更新 | `daily_skill_mcp_update.py` |

仓库副本：`D:/Hermes agent/hermes/scripts/repo-maintenance/`

### Telegram 话题发送

使用 `hermes send` CLI 发送到指定话题：

```bash
hermes send -t "telegram:-1003733144325:846" "{报告内容}"
```

- `-t` / `--to` 格式 `platform:chat_id:thread_id`
- 发送后验证：返回 `sent` 表示成功

### 常用话题

| 目标 | 格式 |
|------|------|
| 分析话题 386 | `telegram:-1003733144325:386` |
| 报告话题 846 | `telegram:-1003733144325:846` |

## Windows 专用命令

```bash
# 网络
ipconfig /all
netstat -ano

# 服务
net start
net stop ServiceName

# 系统信息
systeminfo | grep "Total Physical Memory"
```

## Windows OS 级全面检查

当用户要求"全面检查系统/体检/系统检查"时，"全面"意味着**所有维度**，不是只看 CPU/RAM/磁盘。第一轮至少覆盖以下 12 个维度，缺任何一个都算不完整：

| 维度 | 采集内容 |
|------|----------|
| ① 硬件 | CPU 型号/核数/负载、GPU/显存/驱动、主板/BIOS、内存条数/频率、硬盘型号/接口 |
| ② 系统 | OS 版本/Build、安装日期、上次启动、运行时长、页面文件 |
| ③ 磁盘 | 各分区总/已用/剩余/使用率、文件系统、健康状态 |
| ④ 安全 | Defender 状态/实时保护/病毒库、防火墙各配置文件、最近安全更新(HotFix)、BitLocker、入站规则数量、暴力破解记录 |
| ⑤ 网络 | 有线/WiFi 状态+速率、DNS、代理设置、活跃连接数、监听端口列表 |
| ⑥ 内存 | 各进程内存 Top 15+、总进程内存、Memory Compression 占用 |
| ⑦ 驱动 | GPU/网卡/音频/蓝牙驱动版本+日期、异常设备(ConfigManagerErrorCode≠0) |
| ⑧ 用户 | 本地账户列表/启用状态/最后登录、管理员组成员 |
| ⑨ 启动项 | 开始菜单+注册表 Run 启动项 |
| ⑩ 计划任务 | 状态为 Ready/Running 的计划任务 |
| ⑪ 事件日志 | System 日志最近错误(Error)、Windows Update 日志、Security 登录事件 |
| ⑫ 共享 | SMB 共享列表 |

**关键 PowerShell 命令**：见 `references/windows-system-audit-commands.md`

**输出格式**：用卡片式表格，分维度汇总。末尾分三级：
- ✅ 正常项
- ⚠️ 需关注（可更新但不紧急）
- ❌ 需立即处理（安全漏洞、保护关闭等）

**反模式**：
- 第一轮只查 CPU/RAM/磁盘就回复 → 用户会说"我说全面检查"
- 用 `wmic` 命令 → 在 MSYS bash 中不可用，必须用 `powershell -Command`
- 不加 `| cat` → PowerShell 输出在 bash 中可能截断

## Windows + Hermes 全面体检工作流

当用户要求"检查 Hermes 系统/体检/审计我的系统"且上下文涉及 Hermes 配置时，按层采集并留下可复查的报告，而不是只口头总结：

1. 建立输出目录，例如 `outputs/system-check/`，把每一类检查结果保存为编号文件。
2. 系统层：采集时间、主机、OS、CPU、内存、磁盘、启动时长、工作区目录体积；Windows 上可用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command 'Get-CimInstance ... | ConvertTo-Json'` 获取结构化硬件/磁盘/进程信息。
3. 进程/端口层：检查高内存进程、关键进程、监听端口和关键本地端口；Windows bash 环境用 `tasklist`、`netstat -ano`、`ps -ef`。
4. 网络层：检查代理环境变量、基础 ping、DNS、关键 API 的直连/代理 `curl` timing；ICMP ping 失败但 HTTPS 正常时，不要误判为 API 不可用。
5. Hermes 层：运行 `hermes --version`、`hermes config check`、`hermes doctor`、`hermes status --all`、`hermes mcp list/test`、`hermes cron list/status`、`hermes gateway status`；敏感配置只报告"present/len"，不要输出 key。
6. 产出最终 `REPORT.md`：总况、关键状态、问题优先级、建议动作、证据文件路径。把"运行态正常"和"历史日志中过去失败"分开描述。
7. Windows Git-Bash 体检的采集坑（编码、Python `shell=True` 调用 cmd.exe、curl timing 引号）见 `references/windows-hermes-audit-pitfalls.md`。
8. 体检脚本如果用 Python `subprocess.run(..., shell=True)`，在 Windows 上默认进入 `cmd.exe`，不是 Hermes 终端里的 Git-Bash；因此不要在这种脚本里直接写 `command -v`、`which`、`&& echo`、`for ...; do ...; done`、`find ... -printf` 等 Bash 习惯命令来做关键判定。对 Hermes CLI 版本/路径、工作区大小、日志扫描、curl timing、npm audit 这类关键项，要么直接通过当前 `terminal` 工具二次复核，要么在 Python 中显式调用 Git-Bash，并把二次复核结果保存为独立证据文件。
   - **重要补充**：在 Windows Python 子进程里写 `subprocess.run(['bash','-lc', ...])` 仍可能解析到 `C:\Windows\System32\bash.exe`（WSL 启动器）而不是 Git-Bash，导致所有证据文件出现 WSL 安装提示/乱码且 rc=1。审计采集器应显式使用 `C:/Program Files/Git/usr/bin/bash.exe`，或先从当前 Hermes terminal 用 `cygpath -w /usr/bin/bash` 确认路径后传入；不要只信 Python 进程内的 PATH。
9. 采集完成后先审 `manifest.json`、`summary.json` 或命令返回码，不要直接写结论：凡是 `returncode != 0`、`timeout`、输出只有 "The system cannot find the path specified." / "unexpected at this time." / "不允许使用空管道元素" / `uv trampoline failed to canonicalize script path` / WSL 安装提示乱码 的证据文件，必须重跑或换实现补证据。尤其是 Hermes CLI：若 Python 审计脚本里 `subprocess.run(...)` 调错 shell 或触发 cmd.exe/uv trampoline 失败，不能把它写成 Hermes 故障；立即用当前 `terminal` 的 Git-Bash 直跑同一批 `hermes doctor/status/config/mcp/cron`，保存为 `*_bash.txt`，并以这批二次证据为准。
10. TradingView 链路要分两层判定：`hermes mcp test tradingview` 只证明 MCP server 可启动，不证明 TradingView Desktop 的 CDP 端口可用。全面体检发现 BTC关键位/TV分析任务异常时，必须再跑 `node tools/tradingview-mcp/src/cli/index.js status` 与 `python scripts/btc_ref_levels_sync.py`（输出落证据文件）。若 status 报 `CDP connection failed` 或脚本报 `TradingView CDP unavailable`，结论写“TV CDP不可用/需以CDP模式重启TradingView”，不要误判为 MCP 配置坏。
11. PowerShell 复杂管道不要全部塞进一行 `-Command`：`foreach(...) { ... } | Sort-Object` 在转义/换行不稳时容易触发空管道解析错误。遇到端口映射、防火墙规则这类复杂采集，优先写临时 `.ps1`：先 `$rows = foreach (...) { [pscustomobject]... }`，最后 `$rows | Sort-Object ... | Format-Table -AutoSize`，再把输出保存到证据目录。
12. 端口结论要区分"系统默认监听噪音"和"业务进程暴露"：RPC/SMB/动态端口需要结合防火墙判断；Hermes Studio/Web UI、Dashboard、远控/安全软件等业务进程若绑定 `0.0.0.0`/`::`，必须同时实测 `curl http://127.0.0.1:<port>/` 与 `curl http://<LAN_IP>:<port>/`。LAN 返回 HTTP 200 才标为局域网暴露；只本机 200/LAN 不通则标为本机监听。
12. 体检报告生成后必须做一次文件存在与长度验证（例如 `test -s REPORT.md && wc -l REPORT.md`），并在最终回复给出可点击的绝对路径 Markdown 链接。
13. Windows Git-Bash 中用 Python 生成报告时，不要把 MSYS 路径（如 `/d/Hermes agent/...`）直接交给 `pathlib.Path` 写文件；Python 会当成 `\\d\\...` 导致 `FileNotFoundError`。先转换成原生路径（`D:/Hermes agent/...`），或从一开始用 `D:/...` 作为输出目录传给 Python。
14. 审计发现 Hermes cron `Script not found` 时，不只看 `hermes cron list`；要读 `C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json`，确认 `script` 与 `workdir` 的组合会解析到哪里。维护脚本若实际在 `D:/Hermes agent/hermes/scripts/repo-maintenance/`，cron 的 `script` 应写成 `hermes/scripts/repo-maintenance/<name>.py`（相对 workdir），修改前备份 `jobs.json`，修改后用 `hermes cron list --all` 验证。
8. 体检后执行修复时，优先处理 MCP env 透传、OpenRouter base URL、npm audit、gateway 重启验证；详细 runbook 见 `references/windows-hermes-repair-runbook.md`。
9. 当用户反馈"任务多/卡顿"或体检发现重复监控、Dashboard 暴露、watchdog 重启风暴时，按运行时降噪流程合并/降频任务、收紧端口、验证当前状态；详细策略见 `references/windows-hermes-cron-and-runtime-optimization.md`。

### Hermes 平台退役/停用工作流

当用户确认某个消息平台"不用了/停用/不要再推送"（例如 Discord）时，按平台退役处理，而不是只在记忆里标注：

1. 先备份 `~/AppData/Local/hermes/config.yaml` 和 `~/AppData/Local/hermes/channel_directory.json`，备份名包含平台名和时间戳。
2. 用 Hermes CLI 修改配置，避免直接编辑安全敏感配置文件：`hermes config set <platform>.<key> <value>`。在 Windows Git-Bash 中如果 `hermes` 入口报 `uv trampoline failed to canonicalize script path`，改用安装 venv 直接调用：`/c/Users/Administrator/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe -m hermes_cli.main config set ...`。
3. 对 Discord 这类平台，停用时至少清空/关闭：`allowed_channels`、`free_response_channels`、`auto_thread`、`history_backfill`、`history_backfill_limit`、`reactions`；把 `require_mention` 和 `thread_require_mention` 设为安全默认 `true`。
4. 清理 `channel_directory.json` 中对应 `platforms.<platform>` 的缓存频道列表为 `[]`，避免后续 `send_message(action='list')` 继续推荐废弃目标。
5. 运行 `hermes status --all` 验证该平台显示 `not configured`，并把变更、备份路径、验证结果写入本次体检/维护报告。
6. 不要删除 Hermes 源码自带 platform plugin；内置插件文件不是启用状态。历史备份和历史日志里的平台字符串也不要改，保留证据链。

## Windows 端口安全审查

当用户要求"审查端口"、"检查哪些端口对外暴露"、"端口安全审计"时，不能只列监听端口。必须交叉验证三层信息才能判断真实风险：

**三层验证法：**
1. **监听层**：哪些端口在监听，绑定地址是什么（`0.0.0.0`/`::` = 外部可达，`127.0.0.1`/`::1` = 仅本地）
2. **防火墙层**：是否有 Allow/Block 规则覆盖该端口，规则适用的配置文件（Public/Private/Domain）
3. **网络配置层**：当前网卡的 NetworkCategory（Public 最严格，Domain 最宽松）

**关键判断逻辑：**
- 绑定 `0.0.0.0`/`::` + 无防火墙 Allow 规则 + Public 网络 = **默认阻断**（安全）
- 绑定 `0.0.0.0`/`::` + 有 Allow 规则（Any端口） = **开放**（高风险）
- Windows 防火墙 **Block 优先于 Allow**，有 Block 规则覆盖的端口即使有 Allow 规则也被阻断
- `wmic` 在 MSYS bash 中不可用，必须用 `powershell -Command`

**常见风险模式：**
- 安全软件（360、火绒等）自动创建 Allow Any 入站规则 → 相当于防火墙打洞
- UPnP 端口 2869 有显式 Allow → 历史漏洞多，非必要应禁用
- SMB 445 / RPC 135 / NetBIOS 139 虽然监听，但默认防火墙通常阻断 → 确认无 Allow 规则即可
- 代理工具（Clash Verge 等）可能有 Allow Any 规则暴露代理端口

**输出格式**：分三张表——外部可达端口（含防火墙状态+风险评级）、仅本地端口（安全，简表）、关键发现+建议操作。参考 `references/windows-port-audit-commands.md`。

详细命令和分析模板见 `references/windows-port-audit-commands.md`。

## 注意事项
- `rm -rf` 危险操作前先用 `ls` 确认路径
- 日志文件定期轮转，避免占满磁盘
- cron 脚本中的 PATH 和环境变量需要显式设置
- 敏感信息（密码/token）不要出现在命令行参数中（会被 ps 看到）
- 系统审计类任务要保存证据文件，并在最终回复中引用报告路径
