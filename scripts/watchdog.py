#!/usr/bin/env python3
"""Legacy monitor watchdog compatibility layer.

The production authority is monitor/market_watchdog.py.  This module is kept
only for old imports and controlled diagnostics; it never starts by default.
External alerts are also opt-in so importing/testing this compatibility layer
cannot send Telegram messages.
"""
from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(os.environ.get("HERMES_ROOT", "D:/Hermes agent"))
HEARTBEAT_FILE = ROOT / "data" / "monitor_heartbeat.json"
LOCK_FILE = ROOT / "data" / "monitor.lock"
WATCHDOG_LOCK_FILE = ROOT / "data" / "watchdog.lock"
LOG_FILE = ROOT / "data" / "watchdog.log"
GUARD_FILE = ROOT / "data" / "watchdog_guard.json"
WATCHDOG_STATE_FILE = ROOT / "data" / "watchdog_state.json"
SYSTEM_EVENT_FILE = ROOT / "data" / "system_events.jsonl"
MONITOR_SCRIPT = ROOT / "scripts" / "行情守望.py"
CHECK_INTERVAL = 60
STALE_SECONDS = 300
MAX_RESTARTS_PER_HOUR = 20
MAX_RESTARTS_EMERGENCY = 30
TZ = timezone(timedelta(hours=8))


def log(msg: str) -> None:
    line = f"[{datetime.now(TZ):%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def write_watchdog_state(**updates):
    state = {}
    try:
        if WATCHDOG_STATE_FILE.exists():
            value = json.loads(WATCHDOG_STATE_FILE.read_text(encoding="utf-8"))
            state = value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        state = {}
    state.update(updates)
    state["updated"] = datetime.now(TZ).isoformat()
    WATCHDOG_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHDOG_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def append_system_event(row: dict) -> None:
    payload = dict(row)
    payload.setdefault("time", datetime.now(TZ).isoformat())
    SYSTEM_EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SYSTEM_EVENT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def send_watchdog_alert(msg: str) -> bool:
    """Send only when explicitly enabled; tests may replace this function."""
    if os.environ.get("TANGXI_ENABLE_WATCHDOG_ALERTS") != "1":
        return False
    try:
        from telegram_direct import send_telegram_direct
        result = send_telegram_direct("telegram:-1003733144325:416", msg, timeout=10)
        return bool(result[0]) if isinstance(result, tuple) else bool(result)
    except Exception as exc:
        log(f"watchdog告警失败: {type(exc).__name__}: {str(exc)[:100]}")
        return False


def notify_watchdog_block(reason: str, cooldown_remaining: int, restart_count: int):
    state = write_watchdog_state(
        status="blocked",
        last_restart_reason=reason,
        restart_count_1h=restart_count,
        blocked_until=(datetime.now(TZ) + timedelta(seconds=max(0, cooldown_remaining))).isoformat(),
    )
    now_ts = time.time()
    last_alert = float(state.get("last_alert_sent", 0) or 0)
    if now_ts - last_alert < 900:
        return state
    append_system_event({
        "type": "watchdog_restart_blocked",
        "reason": reason,
        "cooldown_remaining": cooldown_remaining,
        "restart_count_1h": restart_count,
    })
    if send_watchdog_alert(f"安禾监控告警：行情守望重启被限速 — {reason}"):
        write_watchdog_state(last_alert_sent=now_ts)
    return state


def read_heartbeat() -> dict | None:
    try:
        value = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def heartbeat_age(hb: dict) -> float:
    try:
        timestamp = datetime.fromisoformat(str(hb["time"]).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
    except (KeyError, TypeError, ValueError, OverflowError):
        return float("inf")


def pid_alive(pid: int) -> bool:
    try:
        if os.name == "nt":
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
            ).stdout
            return str(pid) in out and "No tasks" not in out
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return False


def acquire_watchdog_lock() -> bool:
    WATCHDOG_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"pid": os.getpid(), "started": datetime.now(TZ).isoformat()}, ensure_ascii=False)
    try:
        fd = os.open(str(WATCHDOG_LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            old = json.loads(WATCHDOG_LOCK_FILE.read_text(encoding="utf-8"))
            if pid_alive(int(old.get("pid") or 0)):
                return False
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        try:
            WATCHDOG_LOCK_FILE.unlink()
        except OSError:
            return False
        try:
            fd = os.open(str(WATCHDOG_LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
    return True


def release_watchdog_lock() -> None:
    try:
        value = json.loads(WATCHDOG_LOCK_FILE.read_text(encoding="utf-8"))
        if str(value.get("pid")) == str(os.getpid()):
            WATCHDOG_LOCK_FILE.unlink()
    except (OSError, json.JSONDecodeError, TypeError):
        pass


def _load_guard() -> dict:
    try:
        value = json.loads(GUARD_FILE.read_text(encoding="utf-8")) if GUARD_FILE.exists() else {}
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def start_monitor(emergency: bool = False) -> bool:
    """Start legacy monitor only when directly requested by a caller."""
    guard = _load_guard()
    now_ts = time.time()
    hour_ago = now_ts - 3600
    key = "restart_times_emergency" if emergency else "restart_times"
    budget = MAX_RESTARTS_EMERGENCY if emergency else MAX_RESTARTS_PER_HOUR
    kind = "真崩溃" if emergency else "卡死/环境未就绪"
    recent = [t for t in guard.get(key, []) if isinstance(t, (int, float)) and t > hour_ago]
    if len(recent) >= budget:
        cooldown = int(max(0, min(recent) + 3600 - now_ts))
        reason = f"重启速率限制[{kind}]：{budget}次/小时已达上限 · 冷却{cooldown}s"
        log(reason)
        write_watchdog_state(status="blocked", restart_count_1h=len(recent), last_restart_reason=reason)
        notify_watchdog_block(reason, cooldown, len(recent))
        return False

    hb = read_heartbeat()
    if hb and hb.get("status") == "running":
        try:
            hb_pid = int(hb.get("pid") or 0)
        except (TypeError, ValueError):
            hb_pid = 0
        if hb_pid and heartbeat_age(hb) <= STALE_SECONDS and pid_alive(hb_pid):
            write_watchdog_state(status="running", last_restart_reason="already_running", monitor_pid=hb_pid)
            return True

    recent.append(now_ts)
    guard[key] = recent
    GUARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    GUARD_FILE.write_text(json.dumps(guard, ensure_ascii=False, indent=2), encoding="utf-8")
    write_watchdog_state(status="restarting", restart_count_1h=len(recent), last_restart_reason=f"attempt_start[{kind}]")

    try:
        if LOCK_FILE.exists():
            try:
                lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
                if not pid_alive(int(lock.get("pid") or 0)):
                    LOCK_FILE.unlink()
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                try:
                    LOCK_FILE.unlink()
                except OSError:
                    pass
        env = os.environ.copy()
        env.pop("HANGQING_NO_SEND", None)
        kwargs = {
            "cwd": str(ROOT), "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL, "env": env,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen([sys.executable, str(MONITOR_SCRIPT)], **kwargs)
        time.sleep(float(os.environ.get("WATCHDOG_START_GRACE_SECONDS", "3")))
        try:
            if proc.poll() is not None:
                write_watchdog_state(status="failed", last_restart_reason=f"启动失败: code={proc.returncode}")
                return False
        except AttributeError:
            if os.environ.get("WATCHDOG_SKIP_PID_ALIVE_CHECK") != "1" and not pid_alive(proc.pid):
                write_watchdog_state(status="failed", last_restart_reason=f"启动失败: pid={proc.pid}")
                return False
        if os.environ.get("WATCHDOG_SKIP_PID_ALIVE_CHECK") != "1" and not pid_alive(proc.pid):
            write_watchdog_state(status="failed", last_restart_reason=f"启动失败: pid={proc.pid}")
            return False
        write_watchdog_state(status="running", last_restart_reason="started", monitor_pid=proc.pid)
        return True
    except (OSError, subprocess.SubprocessError, TypeError) as exc:
        write_watchdog_state(status="failed", last_restart_reason=f"start_exception:{type(exc).__name__}")
        return False


def main() -> None:
    # cron_watchdog_is_authority: legacy watchdog never owns production by default.
    if os.environ.get("TANGXI_ENABLE_LEGACY_WATCHDOG") != "1":
        write_watchdog_state(status="retired", last_restart_reason="cron_watchdog_is_authority")
        return
    if not acquire_watchdog_lock():
        return
    atexit.register(release_watchdog_lock)
    # Deliberately bounded: this compatibility module does not run a resident
    # controller.  The current cron watchdog owns the production lifecycle.
    write_watchdog_state(status="retired", last_restart_reason="cron_watchdog_is_authority")


if __name__ == "__main__":
    main()
