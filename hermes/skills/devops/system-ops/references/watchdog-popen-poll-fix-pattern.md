# watchdog.py Popen.poll() AttributeError 修复模式

> 场景：Windows git-bash/MSYS 环境下 `subprocess.Popen` 返回的对象在某些情况下缺少 `.poll()` 方法，导致 `AttributeError: 'P' object has no attribute 'poll'`。

## 现象

```python
proc = subprocess.Popen([sys.executable, str(MONITOR_SCRIPT)], ...)
# 部分 Windows 环境下 proc 是不完整的对象（类名显示为 'P'）
try:
    if proc.poll() is not None:  # AttributeError
        ...
except AttributeError:
    # 降级逻辑
```

日志示例：
```
[2026-06-21 21:34:58] 启动失败: 'P' object has no attribute 'poll'
[2026-06-21 21:35:07] 启动失败: 'P' object has no attribute 'poll'
```

## 根因

Python 标准库 `subprocess.Popen` 在某些 Windows 环境（特别是通过 git-bash/MSYS 启动、或使用 `creationflags=subprocess.CREATE_NO_WINDOW`）返回的内部 `_Popen` 对象可能未完全初始化 `.poll()` 方法。这是 CPython 在 Windows 上的已知边缘情况。

## 统一修复模式

**不要**用 `try/except AttributeError` 分支。直接用 PID 判断进程存活，完全绕过 `poll()`：

```python
def pid_alive(pid: int) -> bool:
    """跨平台判断进程是否存活。Windows 用 tasklist，Unix 用 kill(0)。"""
    if not pid:
        return False
    try:
        if os.name == "nt":
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
            ).stdout
            return str(pid) in out and "No tasks" not in out
        os.kill(pid, 0)  # signal 0 不发信号，只检查权限/存在性
        return True
    except Exception:
        return False


def start_monitor(emergency: bool = False) -> bool:
    # ... 前置逻辑 ...

    proc = subprocess.Popen(
        [sys.executable, str(MONITOR_SCRIPT)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    
    # 等待进程真正就绪：轮询心跳文件，而不是睡固定秒数
    grace_seconds = float(os.environ.get("WATCHDOG_START_GRACE_SECONDS", "30"))
    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        time.sleep(1)
        hb = read_heartbeat()
        if hb and hb.get("status") == "running":
            hb_age = heartbeat_age(hb)
            if hb_age < 10:  # 心跳新鲜且状态 running
                write_watchdog_state(status="running", monitor_pid=proc.pid)
                return True
    
    # 超时仍未就绪 → 判定启动失败
    if not pid_alive(proc.pid):
        write_watchdog_state(status="failed", last_restart_reason=f"process died pid={proc.pid}")
        return False
    
    # 进程活着但心跳未写出 → 给更多时间或记录警告
    write_watchdog_state(status="running", monitor_pid=proc.pid, last_restart_reason="started_no_heartbeat_yet")
    return True
```

## 关键点总结

| 反模式 | 推荐模式 |
|---|---|
| `proc.poll() is not None` | `not pid_alive(proc.pid)` |
| `time.sleep(3)` 固定等待 | 轮询心跳文件 `status==running && age<10s`，最长 30s |
| `try/except AttributeError` 分支 | 统一用 `pid_alive()`，彻底避开 `poll()` |
| 单一限流桶 | 分桶：`emergency`(真崩溃) vs `normal`(卡死/环境)，独立计数、独立阈值 |

## 适用范围

- 所有在 Windows git-bash/MSYS 下用 `subprocess.Popen` 启动常驻子进程的守护脚本
- Hermes `watchdog.py`、`btc_watchdog.py` 等看门狗类脚本
- 任何需要“启动 → 确认就绪 → 才算成功”的进程托管场景