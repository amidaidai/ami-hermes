# 行情守望看门狗模式

## 单一控制权铁律

同一个守护进程只能有一个生产重启控制器。棠溪系统以 Hermes cron 的 `scripts/monitor/market_watchdog.py` 为唯一权威；历史常驻 `scripts/watchdog.py` 必须默认退役，仅显式调试变量才允许启动。

双控制器会产生：互删锁文件 → 重复拉起 → 多实例并行 → 心跳互相覆盖 → 一小时重启桶耗尽。看到“卡死/环境未就绪：20次/小时”时，不要先提高上限，先查是否存在双看门狗或重复守护实例。

## Windows可靠进程发现

Windows 11可能没有 `wmic`，不要依赖它查完整命令行。使用 `psutil`：

```python
import psutil
pids = []
for proc in psutil.process_iter(["pid"]):
    try:
        cmdline = " ".join(proc.cmdline())
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue
    if "行情守望.py" in cmdline:
        pids.append(proc.pid)
```

注意：诊断脚本自身的命令行若含目标脚本字面量，也可能被误匹配并自杀。生产匹配应限定 `python.exe` 且检查参数元素/脚本绝对路径；临时探针可动态拼接目标字符串，避免它出现在探针命令行。

## 正确重启顺序

1. 读取心跳并确认超过阈值。
2. 查找所有目标守护实例。
3. 精确终止旧实例并等待退出。
4. **进程退出后**再删除 `monitor.lock`；禁止先删锁。
5. 用参数数组直接 `subprocess.Popen([sys.executable, script, ...])`，不用 `start /B`、`shell=True`或尾随`&`。
6. 等待启动宽限期，验证新PID、心跳时间和`status=running`。
7. 再触发一次cron看门狗，健康时应静默成功且不得新增实例。

## 限速告警诊断

| 现象 | 优先检查 |
|---|---|
| 20次/小时“卡死/环境未就绪” | 双控制器、先删锁后杀进程、进程发现失效 |
| 30次/小时“真崩溃” | 守护启动后立即退出、依赖/配置错误 |
| 心跳新鲜但有多个PID | 多实例同时写心跳，不能以新鲜心跳判健康 |
| guard文件已清但仍收到旧告警 | 查残留内存进程或延迟投递，不要只看当前文件 |

清空限速桶只能在根因修复、重复实例清理后进行；单独删除`watchdog_guard.json`会掩盖重启风暴。

## 验证清单

```text
- 目标守护进程恰好1个
- 旧常驻watchdog默认不运行
- monitor.lock中的PID与唯一进程一致
- monitor_heartbeat.json PID一致、年龄<检查阈值
- 手动运行行情守望看门狗：succeeded且健康时零输出
- 等待至少一个cron周期：未新增PID、未产生限速告警
- 回归测试覆盖：单一权威、psutil发现、kill在unlink之前
```

## Cron配置

`--script monitor/market_watchdog.py --no-agent --workdir "D:/Hermes agent"`。频率表达式要写成`*/3 * * * *`（每3分钟），不是`3 */3 * * *`（每3小时第3分）。

## 多实例审计检测模式（2026-07-11 实测）

看门狗拉起守护时旧进程未被完全杀死，或手动启动与 cron 看门狗同时运行，导致同一守护脚本多个 python.exe 实例并存。审计时用以下脚本检测：

```python
import psutil, time
for p in psutil.process_iter(['name','pid','cmdline','create_time']):
    cl = p.info.get('cmdline') or []
    if p.info.get('name') == 'python.exe' and any('行情守望' in str(c) or 'btc_daemon' in str(c) for c in cl):
        age = time.time() - p.info.get('create_time', 0)
        print(f'PID={p.info["pid"]:6d} age={age:.0f}s')
```

发现同一脚本 >1 实例即 P0。修复步骤：
1. 识别最旧实例（age 最大），逐个 `psutil.Process(pid).terminate()` + 等待退出
2. 保留最新单实例
3. 清锁文件（`monitor.lock` / `.btc_daemon.lock`）
4. 验证看门狗下一周期不再重复拉起

注意：诊断脚本自身的命令行若含目标脚本字面量也会被匹配，需过滤掉 PID 为自身的进程。
