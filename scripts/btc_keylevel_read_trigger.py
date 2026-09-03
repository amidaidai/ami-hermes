#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC 关键位触发读取 — 读实时守卫(btc_keylevel_rest_guard.py)写下的触发文件。

守护进程 0.5s 轮询价格，穿越 79,633/78,400 任一位 → 写 data/btc_keylevel_trigger.json。
本脚本每2min 查该文件：有未过期的 TRIGGER → 输出 TRIGGER 供 agent 分析推送；
无 → 静默 WAIT。这样"到价提醒"由实时守护捕捉，cron 只做分析搬运。
"""
import json
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 守护触发文件
TRIGGER_FILE = Path("D:/Hermes agent/data/btc_keylevel_trigger.json")
# 独立状态文件，记录本 agent 已处理过的触发时间戳，防重复
STATE_FILE = Path(os.path.expanduser("~/AppData/Local/hermes/data/btc_klt_agent_state.json"))
# 冷却（agent 分析推送后，同触发位不再重复推）
AGENT_COOLDOWN = 1800


def main():
    try:
        with open(TRIGGER_FILE) as f:
            trig = json.load(f)
    except Exception:
        trig = None

    if not trig or not trig.get("triggered"):
        # 无触发
        _reset_agent_state()
        print("WAIT no-trigger", flush=True)
        sys.exit(0)

    # 有触发，检查是否已处理
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except Exception:
        state = {}

    ts_key = trig.get("ts", "")
    cooldown_until = trig.get("cooldown_until", 0.0)
    zone = trig.get("zone", "")
    direction = trig.get("direction", "")
    price = trig.get("price", 0)

    last_done_ts = state.get("zone", {}).get(zone, "")
    now_ts = time.time()

    # 若触发时间戳已处理过 → 静默
    if last_done_ts == ts_key:
        print(f"WAIT already-handled zone={zone}", flush=True)
        sys.exit(0)

    # 若守护侧仍在冷却（说明刚触发过且未分配给 agent 新任务），仍可触发分析
    print(f"TRIGGER zone={zone} price={price:,.0f} dir={direction} ts={ts_key} cooldown_until={cooldown_until:.0f}", flush=True)


def _reset_agent_state():
    """无触发时，agent 侧状态可重置（下次触发重新提醒）。此处不清 ts_key，保留去重。"""
    pass


if __name__ == "__main__":
    main()
