#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行情守望守护看门狗 — 每5分 cron，心跳 >300s 则拉起 + 告警 TG:846。
参照 scripts/monitor/btc_watchdog.py 模式：
- 检测 data/monitor_heartbeat.json 的 status+time
- 失联则杀旧进程(start/B 启动的 python 行情守望.py) + 重启
- 重启时输出3表(真Markdown)推 TG:846；正常时 stdout 为空不推送
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Windows GBK 环境 stdout UTF-8 修复（审计 Pitfalls 要求）
import io as _io
if hasattr(sys.stdout, "buffer"):
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DAEMON = "D:/Hermes agent/scripts/行情守望.py"
HEARTBEAT = "D:/Hermes agent/data/monitor_heartbeat.json"
LOCK = "D:/Hermes agent/data/monitor.lock"
WORKDIR = "D:/Hermes agent"
STALE_SEC = 300  # 心跳超 5 分钟判失联


def log(m):
    # 正常不输出；异常重启只输出下方3表
    return None


# ---- 读取心跳 ----
hb = None
try:
    with open(HEARTBEAT, encoding="utf-8") as f:
        hb = json.load(f)
except Exception:
    hb = None

now = time.time()
alive = False
reason = "无心跳文件"

if hb:
    status = hb.get("status")
    tstr = hb.get("time") or hb.get("ts")
    if status == "running" and tstr:
        try:
            # 兼容 2026-07-07T17:41:25 与 2026-07-07T17:41:25.711618800+08:00
            tstr2 = tstr.replace("Z", "+08:00")
            if "+" in tstr2:
                dt = datetime.fromisoformat(tstr2)
            else:
                dt = datetime.fromisoformat(tstr2)
            # 若有 tzinfo 转本地戳差
            if dt.tzinfo is not None:
                age = (datetime.now(dt.tzinfo) - dt).total_seconds()
            else:
                age = now - dt.timestamp()
            if age < STALE_SEC:
                alive = True
            else:
                reason = f"心跳过期 {int(age)}s"
        except Exception as e:
            reason = f"心跳解析失败: {e}"
    else:
        reason = f"status={status}"
else:
    reason = "心跳文件缺失"

if alive:
    exit(0)

# ---- 守护失联：重启 ----
log(f"行情守望失联({reason})，重启中...")

# 清理可能残留的 lock
try:
    if os.path.exists(LOCK):
        os.remove(LOCK)
except Exception:
    pass

# 杀掉旧的 python 行情守望.py 进程（兼容 start/B 启动方式）
killed = "无"
try:
    # 用 wmic 精确匹配命令行含 行情守望.py 的 PID（GBK 解码）
    wmic = subprocess.run(
        ["wmic", "process", "where",
         "name='python.exe' and commandline like '%行情守望.py%'",
         "get", "processid"],
        capture_output=True, timeout=10,
    ).stdout.decode("gbk", errors="replace")
    pids = [l.strip() for l in wmic.splitlines() if l.strip().isdigit()]
    for pid in pids:
        subprocess.run(["taskkill", "/F", "/PID", pid],
                       capture_output=True, timeout=5)
        killed = pid
except Exception:
    pass

# 用 start /B 后台拉起（与 btc_watchdog 一致）
cmd = f'start /B python "{DAEMON}" -s BTCUSDT XAUUSD'
subprocess.Popen(
    cmd, shell=True, cwd=WORKDIR,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

now_cn = time.strftime("%Y年%m月%d日%H：%M")
print(f"⚠ 行情守望重启 · {now_cn} · 原因: {reason}")
print("")
print("| 项目 | 数据 | 状态 |")
print("|:----|:----|:----|")
print("| 守护 | 行情守望.py | 已重启 |")
print(f"| 心跳 | {reason} | 失联 |")
print("| 目标 | TG846 多品种监控 | 恢复中 |")
print("")
print("| 模块 | 数据 | 状态 |")
print("|:----|:----|:----|")
print(f"| 旧进程 | `{killed}` | 已清理 |")
print("| 新进程 | start/B python | 已拉起 |")
print("| 日志 | stdout静默 | 防刷屏 |")
print("")
print("| 方向 | 触发 | 动作 |")
print("|:---:|:----|:----|")
print("| ○观察 | 5分钟后心跳running | 无需操作 |")
print("| ×修复 | 继续失联 | 查守护日志 |")
