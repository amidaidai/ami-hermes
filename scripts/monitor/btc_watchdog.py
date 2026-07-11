#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC daemon watchdog — 5m cron, restarts if heartbeat stale >120s.

铁律（2026-07-11 审计复发后加固）：
1. 启动前用 psutil 杀掉所有 btc_daemon.py 实例，不只依赖 PID 文件。
2. 清锁 + 写 PID 文件，确保下次能追踪。
3. 不用 shell start /B；用 Popen 直接启动 python 子进程。
4. 启动后验证进程真的存在，否则推 TG 告警。
"""
import json, os, subprocess, sys, time
from pathlib import Path
from datetime import datetime

DAEMON = Path("D:/Hermes agent/scripts/btc_daemon.py").resolve()
HEARTBEAT = Path("D:/Hermes agent/data/.btc_daemon_heartbeat.json")
PID_FILE = Path("D:/Hermes agent/data/.btc_daemon.pid")
LOCK_FILE = Path("D:/Hermes agent/data/.btc_daemon.lock")
WATCHDOG_LOG = Path("D:/Hermes agent/data/watchdog.log")
WATCHDOG_STATE = Path("D:/Hermes agent/data/watchdog_state.json")
WATCHDOG_GUARD = Path("D:/Hermes agent/data/watchdog_guard.json")
WORKDIR = "D:/Hermes agent"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _now_cn() -> str:
    return datetime.now().strftime("%Y年%m月%d日%H：%M")


def _append_log(entry: str) -> None:
    try:
        with WATCHDOG_LOG.open("a", encoding="utf-8") as f:
            f.write(f"[{_now_cn()}] {entry}\n")
    except Exception:
        pass


def _write_state(status: str, detail: dict | None = None) -> None:
    try:
        payload = {
            "schema": "btc_watchdog_state_v2",
            "updated": _now_iso(),
            "status": status,
            "daemon_pid": (PID_FILE.read_text(encoding="utf-8").strip() if PID_FILE.exists() else None),
            "detail": detail or {},
        }
        WATCHDOG_STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _now_ts() -> float:
    return time.time()


def _heartbeat_age() -> float | None:
    try:
        with open(HEARTBEAT) as f:
            hb = json.load(f)
        ts = hb.get("ts")
        if not ts:
            return None
        dt = datetime.fromisoformat(ts)
        return _now_ts() - dt.timestamp()
    except Exception:
        return None


def _list_daemon_instances() -> list[int]:
    import psutil
    pids = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        cmd = " ".join(p.info["cmdline"] or [])
        if str(DAEMON) in cmd or "btc_daemon.py" in cmd:
            pids.append(p.info["pid"])
    return pids


def _kill_instances(pids: list[int]) -> None:
    import psutil
    for pid in pids:
        try:
            psutil.Process(pid).terminate()
            try:
                psutil.Process(pid).wait(timeout=5)
            except Exception:
                psutil.Process(pid).kill()
        except Exception:
            pass


def _clean_locks() -> None:
    for f in (PID_FILE, LOCK_FILE):
        try:
            if f.exists():
                f.unlink()
        except Exception:
            pass


def _start_daemon() -> int | None:
    import psutil
    # 用当前解释器启动守护进程，避免多 python 版本混乱
    exe = sys.executable
    proc = subprocess.Popen(
        [exe, str(DAEMON)],
        cwd=WORKDIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    # 等待并验证
    time.sleep(2)
    try:
        psutil.Process(proc.pid)
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        return proc.pid
    except Exception:
        return None


def _send_report(reason: str, old_count: int, new_pid: int | None) -> None:
    now_cn = datetime.now().strftime("%Y年%m月%d日%H：%M")
    report = f"""⚠ BTC守护重启 · {now_cn} · {reason}

| 项目 | 数据 | 状态 |
|:----|:----|:----|
| 守护 | btc_daemon.py | {'已重启 PID=' + str(new_pid) if new_pid else '启动失败'} |
| 心跳 | 超过`120s` | 失联 |
| 目标 | TG386信号源 | 恢复中 |

| 模块 | 数据 | 状态 |
|:----|:----|:----|
| 旧实例数 | `{old_count}` | 已清理 |
| 新进程 | python.exe | {'已拉起' if new_pid else '失败'} |
| 日志 | stdout静默 | 防刷屏 |

| 方向 | 触发 | 动作 |
|:---:|:----|:----|
| ○观察 | 2分钟后有心跳 | 无需操作 |
| ×修复 | 继续失联 | 查daemon日志 |"""
    print(report)
    try:
        sys.path.insert(0, "D:/Hermes agent/scripts")
        from telegram_reliable import push_tg_rich
        push_tg_rich("telegram:-1003733144325:846", report)
    except Exception as _te:
        print(f"⚠ BTC守护告警RichMarkdown推送失败: {_te}", file=sys.stderr)


def main() -> int:
    age = _heartbeat_age()
    instances = _list_daemon_instances()
    detail = {
        "heartbeat_age_seconds": age,
        "daemon_instances_before": len(instances),
        "daemon_pids_before": instances,
    }
    _append_log(f"tick age={age if age is not None else 'None'} instances={len(instances)} pids={instances}")

    # 心跳新鲜 → 静默退出，不打扰；但仍更新状态文件
    if age is not None and age < 120:
        _write_state("healthy", {**detail, "action": "noop"})
        _append_log("heartbeat fresh; no action")
        return 0

    reason = f"心跳失联 age={age:.0f}s" if age is not None else "心跳文件不存在"
    old_pids = instances
    if old_pids:
        _kill_instances(old_pids)
        time.sleep(1)
        # double-check
        remaining = _list_daemon_instances()
        if remaining:
            _kill_instances(remaining)
    _clean_locks()
    new_pid = _start_daemon()
    detail["daemon_instances_after"] = len(_list_daemon_instances())
    detail["new_pid"] = new_pid
    detail["reason"] = reason
    _write_state("restarted" if new_pid else "restart_failed", detail)
    _append_log(f"restart reason={reason} old_count={len(old_pids)} new_pid={new_pid}")
    _send_report(reason, len(old_pids), new_pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
