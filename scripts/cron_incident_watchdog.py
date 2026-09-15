#!/usr/bin/env python
"""cron 失败聚合看门狗（no-agent cron 用）。

## 为什么需要它
Hermes 会把 cron 的非零退出记进 `~/AppData/Local/hermes/cron/executions.db` 的 `cron_incidents`，
但**没有任何东西去读它**：2026-09-15 实测积压 3,806 条 `state='detected'`（从未 ack/closed），
其中一个作业 3,745 条。查 cron「健不健康」时只看到 `[active]` 与派发成功，
于是「脚本连错上千次」被读成「0 error」——这与叙事闸门当初的静默失败是同一类。

## 输出契约
- 窗口内（默认 24h）有失败 → 打印摘要（作业名/次数/最近一次时间/错误首行）+ 写 `data/cron_incidents_report.json`，exit 1
- 窗口内无失败 → 写同一份报告（healthy=true），静默 exit 0
- DB 不存在/不可读 → 打印 ⚠ + 写心跳 `db_ok:false` + exit 2（不允许“读不到”长得像“干净”）

用法：
  python scripts/cron_incident_watchdog.py                # cron 默认：近 24h
  python scripts/cron_incident_watchdog.py --hours 72 --backlog   # 连历史积压一起看
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRON_DIR = Path.home() / "AppData/Local/hermes/cron"
DB = CRON_DIR / "executions.db"
JOBS = CRON_DIR / "jobs.json"
REPORT = ROOT / "data/cron_incidents_report.json"
HEARTBEAT = ROOT / "data/cron_incident_watchdog_heartbeat.json"


def _job_names() -> dict:
    try:
        raw = json.loads(JOBS.read_text(encoding="utf-8"))
    except Exception:
        return {}
    items = raw.get("jobs") if isinstance(raw, dict) else raw
    out = {}
    for j in (items or []):
        if isinstance(j, dict) and j.get("id"):
            out[j["id"]] = j.get("name") or j["id"]
    return out


def _write_report(payload: dict) -> None:
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def _write_heartbeat(**extra) -> None:
    HEARTBEAT.write_text(json.dumps(
        {"updated_epoch": time.time(), "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **extra},
        ensure_ascii=False, indent=1), encoding="utf-8")


def _parse(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        return None
    # DB 里是带时区的 ISO（+08:00），但历史行/测试可能是裸时间 → 统一成 aware，避免比较报错
    return dt if dt.tzinfo else dt.astimezone()


def collect(hours: float, include_backlog: bool) -> dict:
    """只统计**未关闭**的 incident：closed = 已解决/已确认，open = 仍在身上。

    早期版本按时间窗统计全部 incident，于是「修好之后」还会继续报一整天（告警疲劳）。
    语义修正：未关闭且落在窗口内 = 当前告警；未关闭但窗口外 = 历史积压（提示）。
    """
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    rows = con.execute(
        "select job_id, state, first_seen_at, last_seen_at, error, output_file "
        "from cron_incidents where state != 'closed'").fetchall()
    names = _job_names()
    cut = datetime.now().astimezone() - timedelta(hours=hours)
    recent, backlog = {}, {}
    for jid, state, first, last, err, out in rows:
        last_dt = _parse(last) or _parse(first)
        first_dt = _parse(first) or last_dt
        bucket = recent if (last_dt and last_dt >= cut) else backlog
        b = bucket.get(jid)
        line = (err or "").strip().splitlines()[0][:160] if err else ""
        if b is None:
            bucket[jid] = {"job_id": jid, "job": names.get(jid, jid), "count": 1,
                           "first_seen": first, "last_seen": last, "state": state,
                           "error": line, "_last_dt": last_dt, "_first_dt": first_dt}
            continue
        b["count"] += 1
        # 时间范围要取并集，错误文本取**最近那次**的（首行命中不等于最近一次）
        if last_dt and (b["_last_dt"] is None or last_dt > b["_last_dt"]):
            b["_last_dt"], b["last_seen"], b["error"], b["state"] = last_dt, last, line, state
        if first_dt and (b["_first_dt"] is None or first_dt < b["_first_dt"]):
            b["_first_dt"], b["first_seen"] = first_dt, first
    for d in (recent, backlog):
        for v in d.values():
            v.pop("_last_dt", None)
            v.pop("_first_dt", None)
    total = len(rows)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        # 显式时间戳键必须兼容 data_freshness_watchdog 的 TIMESTAMP_KEYS
        # （updated_epoch/updated_at/timestamp/ts/time/updated），否则它判「时间戳缺失」
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_epoch": time.time(),
        "window_hours": hours,
        "total_unclosed": total,
        "recent_jobs": sorted(recent.values(), key=lambda x: -x["count"]),
        "recent_total": sum(v["count"] for v in recent.values()),
        "backlog_jobs": sorted(backlog.values(), key=lambda x: -x["count"]) if include_backlog else [],
        "backlog_total": sum(v["count"] for v in backlog.values()),
        "healthy": not recent,
    }
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--backlog", action="store_true", help="把窗口外的历史积压也列出来")
    ap.add_argument("--dry", action="store_true", help="不写报告/心跳")
    a = ap.parse_args()

    if not DB.exists():
        print(f"⚠️ cron 失败看门狗无法运行：executions.db 不存在（{DB}）")
        print("   这不是‘没有失败’，是看门狗自己没跑起来。")
        if not a.dry:
            _write_heartbeat(db_ok=False, error="executions.db missing")
        return 2
    try:
        payload = collect(a.hours, a.backlog)
    except sqlite3.Error as e:
        print(f"⚠️ cron 失败看门狗无法运行：executions.db 不可读（{e}）")
        if not a.dry:
            _write_heartbeat(db_ok=False, error=str(e))
        return 2

    if not a.dry:
        _write_report(payload)
        _write_heartbeat(db_ok=True, window_hours=a.hours,
                         recent_jobs=len(payload["recent_jobs"]),
                         recent_total=payload["recent_total"],
                         total_unclosed=payload["total_unclosed"])

    if payload["healthy"]:
        return 0                      # 静默：cron 零 token 约定

    print(f"⚠️ cron 失败告警：近 {a.hours:g}h 有 {payload['recent_total']} 次失败，"
          f"涉及 {len(payload['recent_jobs'])} 个作业（未关闭 incident 总计 {payload['total_unclosed']} 条）")
    for j in payload["recent_jobs"]:
        print(f"\n- {j['job']}  [{j['job_id']}]  {j['count']} 次")
        print(f"    最近：{j['last_seen']}")
        if j["error"]:
            print(f"    错误：{j['error']}")
    if a.backlog and payload["backlog_jobs"]:
        print(f"\n历史积压（窗口外，仅提示）：{payload['backlog_total']} 条 / {len(payload['backlog_jobs'])} 个作业")
        for j in payload["backlog_jobs"][:5]:
            print(f"  · {j['job']}  {j['count']} 次  （{j['first_seen'][:16]} → {j['last_seen'][:16]}）")
    print(f"\n报告：{REPORT.as_posix()}")
    # 注意：**发现失败也必须 exit 0**。Hermes 会把任何非零退出记成新的 cron_incidents，
    # 若用 exit 1 表示"有失败"，看门狗自己每轮都会产生一条 incident（自我噪声循环）。
    # 告警的可见性靠 stdout（deliver=local 会落 output 文件），不靠退出码。
    # exit 2 只保留给"看门狗自己没跑起来"（DB 不可读）——那种失败**应该**成为 incident。
    return 0


if __name__ == "__main__":
    sys.exit(main())
