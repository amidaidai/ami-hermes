#!/usr/bin/env python3
"""BTC daemon watchdog — 1m cron, restarts if heartbeat stale >120s"""
import json, os, subprocess, time
from pathlib import Path
from datetime import datetime

DAEMON = "D:/Hermes agent/scripts/btc_daemon.py"
HEARTBEAT = "D:/Hermes agent/data/.btc_daemon_heartbeat.json"
PID_FILE = "D:/Hermes agent/data/.btc_daemon.pid"
WORKDIR = "D:/Hermes agent"


def log(m):
    # 正常心跳不输出；异常重启只输出下方3表，避免Telegram收到调试散行。
    return None


# Check heartbeat
hb = None
try:
    with open(HEARTBEAT) as f:
        hb = json.load(f)
except Exception:
    pass

now = time.time()
alive = False

if hb and "ts" in hb:
    try:
        dt = datetime.fromisoformat(hb["ts"])
        age = now - dt.timestamp()
        if age < 120:
            alive = True
    except Exception as e:
        log(f"hb parse: {e}")

if alive:
    # All good: stdout 必须为空；状态详情留给本地 heartbeat/log，不推送。
    exit(0)

# Daemon dead — restart
log("Heartbeat stale, restarting daemon...")

# Kill old PID if file exists
old = "无"
try:
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            old = f.read().strip()
        if old.isdigit():
            subprocess.run(["taskkill", "/F", "/PID", old],
                           capture_output=True, timeout=5)
            log(f"Killed old PID {old}")
except Exception as e:
    log(f"kill old: {e}")

# Start new daemon — use start /B (background, same console)
cmd = f'start /B python "{DAEMON}"'
log(f"Running: {cmd}")
subprocess.Popen(
    cmd, shell=True, cwd=WORKDIR,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

now_cn = datetime.now().strftime('%Y年%m月%d日%H：%M')
report = f"""⚠ BTC守护重启 · {now_cn}

| 项目 | 数据 | 状态 |
|:----|:----|:----|
| 守护 | btc_daemon.py | 已重启 |
| 心跳 | 超过`120s` | 失联 |
| 目标 | TG386信号源 | 恢复中 |

| 模块 | 数据 | 状态 |
|:----|:----|:----|
| 旧PID | `{old if 'old' in globals() else '无'}` | 已清理 |
| 新进程 | start/B python | 已拉起 |
| 日志 | stdout静默 | 防刷屏 |

| 方向 | 触发 | 动作 |
|:---:|:----|:----|
| ○观察 | 2分钟后有心跳 | 无需操作 |
| ×修复 | 继续失联 | 查daemon日志 |"""
print(report)
# v9.7: 统一走 RichMarkdown 真表格通道推 TG
try:
    import sys
    sys.path.insert(0, "D:/Hermes agent/scripts")
    from telegram_reliable import push_tg_rich
    push_tg_rich("telegram:-1003733144325:846", report)
except Exception as _te:
    print(f"⚠ BTC守护告警RichMarkdown推送失败: {_te}", file=sys.stderr)
