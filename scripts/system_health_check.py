#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""棠溪系统体检：cron 健康 / 数据新鲜度 / 守护心跳 / 关键位 / 信号闭环 / 测试。"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(r"D:\Hermes agent")
HOME = Path(os.path.expanduser("~"))
CN = timezone(timedelta(hours=8))
now = datetime.now(CN)
print(f"体检时间：{now.year}年{now.month}月{now.day}日 {now:%H:%M:%S}（北京时间）\n")

# ── 1. cron ──────────────────────────────────────────────────────────
jobs_p = HOME / "AppData" / "Local" / "hermes" / "cron" / "jobs.json"
print("=== 1. cron 任务 ===")
if jobs_p.exists():
    data = json.loads(jobs_p.read_text(encoding="utf-8"))
    jobs = data if isinstance(data, list) else data.get("jobs", [])
    run = [j for j in jobs if j.get("enabled", True) and not j.get("paused")]
    paused = [j for j in jobs if j.get("paused") or not j.get("enabled", True)]
    print(f"  总 {len(jobs)}｜运行 {len(run)}｜暂停 {len(paused)}")
    for j in run:
        print(f"    ▶ {j.get('name','?')[:34]:<34} {str(j.get('schedule',''))[:18]:<18} script={str(j.get('script') or '-')[:30]}")
else:
    print("  (无 jobs.json)")

# ── 2. cron 失败 ─────────────────────────────────────────────────────
db = HOME / "AppData" / "Local" / "hermes" / "cron" / "executions.db"
print("\n=== 2. 近 6 小时失败 ===")
if db.exists():
    c = sqlite3.connect(db)
    cur = c.cursor()
    since = (now - timedelta(hours=6)).astimezone(timezone.utc).isoformat()
    cur.execute(
        "SELECT job_id, status, started_at, error FROM executions "
        "WHERE started_at > ? AND status NOT IN ('completed','running','claimed') "
        "ORDER BY started_at DESC LIMIT 20", (since,))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"    ✗ {r[0]} {r[1]} {str(r[2])[:19]} {str(r[3])[:60]}")
    else:
        print("    ✓ 无失败")
    cur.execute("SELECT job_id, COUNT(*) FROM executions WHERE started_at > ? GROUP BY job_id", (since,))
    print("    近6小时执行次数:", dict(cur.fetchall()))
else:
    print("  (无 executions.db)")

# ── 3. 守护心跳与关键位 ──────────────────────────────────────────────
print("\n=== 3. 守护 / 关键位 ===")
for f, label in (
    (".keylevel_guard_heartbeat.json", "守护心跳"),
    (".keylevel_guard_health.json", "守护健康"),
    ("keylevels_config.json", "批准关键位"),
    ("keylevels_structure_review.json", "结构复核"),
    ("tv_chart_owner.json", "图表归属"),
):
    p = REPO / "data" / f
    if not p.exists():
        print(f"    ✗ {label:<10} 缺失 ({f})")
        continue
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"    ✗ {label:<10} 解析失败 {e}")
        continue
    mt = datetime.fromtimestamp(p.stat().st_mtime, CN)
    age = (now - mt).total_seconds() / 60
    extra = ""
    if f == "keylevels_config.json":
        btc = (d.get("symbols") or {}).get("BTCUSDT", {})
        lv = btc.get("levels") or []
        act = [x for x in lv if x.get("active")]
        extra = f" BTC批准={len(lv)} 有效={len(act)} 续期至={str((d.get('approval_renewal') or {}).get('valid_until'))[:19]}"
    elif f == "keylevel_guard_heartbeat.json":
        extra = f" status={d.get('status')} pid={d.get('pid')}"
    elif f == "keylevels_structure_review.json":
        extra = f" passed={d.get('passed')}/{d.get('total')}"
    print(f"    {'✓' if age < 120 else '⚠'} {label:<10} {age:7.1f} 分钟前{extra}")

# ── 4. 数据新鲜度 ────────────────────────────────────────────────────
print("\n=== 4. 关键缓存 ===")
for f in ("tv_dmi_cache.json", "tv_live_BTCUSDT.json", "keylevels_candidates.json"):
    p = REPO / "data" / f
    if not p.exists():
        print(f"    ✗ {f} 缺失")
        continue
    mt = datetime.fromtimestamp(p.stat().st_mtime, CN)
    age = (now - mt).total_seconds() / 60
    size = p.stat().st_size
    print(f"    {'✓' if age < 60 else '⚠'} {f:<28} {age:7.1f} 分钟前  {size:>8}B")

# ── 5. 信号闭环库 ────────────────────────────────────────────────────
print("\n=== 5. 信号闭环（P0 统计）===")
jdb = REPO / "data" / "trading_journal.db"
if jdb.exists():
    try:
        c = sqlite3.connect(jdb)
        cur = c.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabs = [r[0] for r in cur.fetchall()]
        for t in tabs:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"    {t}: {cur.fetchone()[0]} 行")
    except Exception as e:  # noqa: BLE001
        print("    ✗", e)
else:
    print("    ✗ 无 trading_journal.db")

# ── 6. 测试 ──────────────────────────────────────────────────────────
print("\n=== 6. 测试 ===")
r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                   cwd=REPO, capture_output=True, text=True, timeout=600)
print("   ", (r.stdout or r.stderr).strip().split("\n")[-1][:100])
