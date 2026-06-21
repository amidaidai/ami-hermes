#!/usr/bin/env python3
"""
棠溪 · 监控看门狗 v1.0
30秒检查 monitor_heartbeat.json，心跳停滞>90秒则自动重启行情守望.py
"""

import atexit
import json, subprocess, sys, time, os
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path("D:/Hermes agent")
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
MAX_RESTARTS_PER_HOUR = 3   # 放宽以避免风暴
MAX_RESTARTS_EMERGENCY = 6  # 放宽真崩溃预算
TZ = timezone(timedelta(hours=8))



def log(msg: str):
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_watchdog_state(**updates):
    state = {}
    if WATCHDOG_STATE_FILE.exists():
        try:
            state = json.loads(WATCHDOG_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    state.update(updates)
    state["updated"] = datetime.now(TZ).isoformat()
    WATCHDOG_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHDOG_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def append_system_event(row: dict):
    row = dict(row)
    row.setdefault("time", datetime.now(TZ).isoformat())
    SYSTEM_EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SYSTEM_EVENT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def send_watchdog_alert(msg: str) -> bool:
    try:
        from telegram_direct import send_telegram_direct
        ok, _reason = send_telegram_direct("telegram:-1003733144325:416", msg, timeout=10)
        if ok:
            return True
    except Exception as e:
        log(f"watchdog直发告警失败: {type(e).__name__}: {str(e)[:100]}")
    try:
        subprocess.run(["hermes", "send", "telegram:-1003733144325:416", msg], cwd=str(ROOT), capture_output=True, text=True, timeout=20)
        return True
    except Exception as e:
        log(f"watchdog兜底告警失败: {type(e).__name__}: {str(e)[:100]}")
        return False


def notify_watchdog_block(reason: str, cooldown_remaining: int, restart_count: int):
    state = write_watchdog_state(
        status="restart_blocked",
        last_restart_reason=reason,
        restart_count_1h=restart_count,
        blocked_until=(datetime.now(TZ) + timedelta(seconds=max(0, cooldown_remaining))).isoformat(),
    )
    now_ts = time.time()
    last_alert = float(state.get("last_alert_sent", 0) or 0)
    if now_ts - last_alert < 900:
        return
    append_system_event({"type": "watchdog_restart_blocked", "reason": reason, "cooldown_remaining": cooldown_remaining, "restart_count_1h": restart_count})
    send_watchdog_alert(f"安禾监控告警：行情守望重启被限速 — {reason}")
    write_watchdog_state(last_alert_sent=now_ts)


def read_heartbeat() -> dict | None:
    if not HEARTBEAT_FILE.exists():
        return None
    try:
        return json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def heartbeat_age(hb: dict) -> float:
    try:
        t = datetime.fromisoformat(hb["time"]).astimezone(TZ)
        return (datetime.now(TZ) - t).total_seconds()
    except Exception:
        return 9999.0


def pid_alive(pid: int) -> bool:
    try:
        if os.name == "nt":
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5
            ).stdout
            return str(pid) in out and "No tasks" not in out
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def acquire_watchdog_lock() -> bool:
    WATCHDOG_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"pid": os.getpid(), "started": datetime.now(TZ).isoformat()}, ensure_ascii=False)
    try:
        fd = os.open(str(WATCHDOG_LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        return True
    except FileExistsError:
        try:
            lock = json.loads(WATCHDOG_LOCK_FILE.read_text(encoding="utf-8"))
            old_pid = int(lock.get("pid") or 0)
        except Exception:
            old_pid = 0
        if old_pid and pid_alive(old_pid):
            print(f"已有看门狗运行: PID {old_pid}", flush=True)
            return False
        try:
            WATCHDOG_LOCK_FILE.unlink()
        except FileNotFoundError:
            pass
        try:
            fd = os.open(str(WATCHDOG_LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            return True
        except FileExistsError:
            return False


def release_watchdog_lock():
    try:
        lock = json.loads(WATCHDOG_LOCK_FILE.read_text(encoding="utf-8"))
        if str(lock.get("pid")) == str(os.getpid()):
            WATCHDOG_LOCK_FILE.unlink()
    except Exception:
        pass


def start_monitor(emergency: bool = False) -> bool:
    """启动行情守望（含速率限制）

    v1.2: 区分「真崩溃」与「环境未就绪/卡死强杀」。
    - emergency=True（进程确已死亡）：给更宽松的预算 MAX_RESTARTS_EMERGENCY，
      因为真崩溃是必须救活的，不该被普通限速一刀切拉黑。
    - emergency=False（卡死强杀/心跳文件缺失）：用保守预算 MAX_RESTARTS_PER_HOUR，
      避免「环境未就绪→拉起→又卡死→再拉起」的死循环空转。
    两类各自独立计数，互不挤占。
    """
    guard = {}
    if GUARD_FILE.exists():
        try:
            guard = json.loads(GUARD_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    now_ts = time.time()
    hour_ago = now_ts - 3600

    # 两类重启分桶计数，互不挤占
    key = "restart_times_emergency" if emergency else "restart_times"
    budget = MAX_RESTARTS_EMERGENCY if emergency else MAX_RESTARTS_PER_HOUR
    kind = "真崩溃" if emergency else "卡死/环境未就绪"

    guard_restarts = [t for t in guard.get(key, []) if t > hour_ago]
    if len(guard_restarts) >= budget:
        cooldown_remaining = int(max(0, min(guard_restarts) + 3600 - now_ts))
        reason = f"重启速率限制[{kind}]：{budget}次/小时已达上限 · 冷却{cooldown_remaining}s"
        log(reason)
        notify_watchdog_block(reason, cooldown_remaining, len(guard_restarts))
        return False

    guard_restarts.append(now_ts)
    guard[key] = guard_restarts
    write_watchdog_state(status="restarting", restart_count_1h=len(guard_restarts),
                         last_restart_reason=f"attempt_start[{kind}]")
    GUARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    GUARD_FILE.write_text(json.dumps(guard, indent=2), encoding="utf-8")
    
    # 清理旧锁
    if LOCK_FILE.exists():
        try:
            lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            old_pid = int(lock.get("pid", 0))
            if old_pid and not pid_alive(old_pid):
                LOCK_FILE.unlink()
                log(f"清理旧锁 PID={old_pid}")
        except Exception:
            try:
                LOCK_FILE.unlink()
            except FileNotFoundError:
                pass
    
    try:
        subprocess.Popen(
            [sys.executable, str(MONITOR_SCRIPT)],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        log("行情守望.py 已启动")
        write_watchdog_state(status="running", last_restart_reason="started")
        return True
    except Exception as e:
        log(f"启动失败: {e}")
        return False


def main():
    if not acquire_watchdog_lock():
        return
    atexit.register(release_watchdog_lock)
    log("看门狗启动 · 检查间隔45s · 超时180s")
    restart_count = 0
    
    while True:
        time.sleep(CHECK_INTERVAL)
        
        hb = read_heartbeat()
        
        if hb is None:
            log("心跳文件不存在 · 启动监控...")
            if start_monitor():
                restart_count += 1
            continue
        
        age = heartbeat_age(hb)
        status = hb.get("status", "unknown")
        
        if age > STALE_SECONDS:
            pid = hb.get("pid")
            alive = pid and pid_alive(int(pid))
            log(f"心跳停滞 {age:.0f}s · PID={pid} · 存活={alive} · 状态={status}")
            
            if not alive:
                log(f"进程已死（真崩溃）· 重启 (第{restart_count+1}次)")
                if start_monitor(emergency=True):
                    restart_count += 1
            else:
                log(f"进程存活但心跳超时 · 可能卡死 · 强制重启")
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                    time.sleep(2)
                except Exception:
                    pass
                if LOCK_FILE.exists():
                    try:
                        LOCK_FILE.unlink()
                    except FileNotFoundError:
                        pass
                if start_monitor():
                    restart_count += 1


if __name__ == "__main__":
    main()
