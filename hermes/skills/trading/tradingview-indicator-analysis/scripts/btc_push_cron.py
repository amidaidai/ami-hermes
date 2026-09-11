#!/usr/bin/env python3
"""告警推送桥梁 — no_agent cron读取daemon写的pending文件，stdout=Telegram推送"""
import os

PENDING = os.path.expanduser("~/AppData/Local/hermes/data/btc_pending.txt")

if not os.path.exists(PENDING):
    exit(0)

with open(PENDING, "r") as f:
    content = f.read().strip()

if content:
    print(content)

# 清空
with open(PENDING, "w") as f:
    f.truncate(0)
