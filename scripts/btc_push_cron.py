#!/usr/bin/env python3
"""BTC告警推送 — no_agent cron读取pending文件推送到Telegram"""
import os, time

DIR = os.path.expanduser("~/AppData/Local/hermes/data")
PENDING = os.path.join(DIR, "btc_pending.txt")

if not os.path.exists(PENDING):
    exit(0)

size = os.path.getsize(PENDING)
if size == 0:
    exit(0)

# 读全部内容
with open(PENDING, "r") as f:
    content = f.read().strip()

if content:
    print(content)

# 清空（截断）
with open(PENDING, "w") as f:
    f.truncate(0)
