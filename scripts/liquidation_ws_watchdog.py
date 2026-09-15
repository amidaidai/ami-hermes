#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清算 WS 采集保活看门狗 —— 心跳陈旧即杀旧重启（零 token，no_agent cron）。

被守护者：`scripts/ws_liquidation_listener.py`（币安 `!forceOrder@arr` 强平流）。
它每有事件/每 60 秒刷 `data/.liquidation_ws_heartbeat.json`；本看门狗每 5 分钟检查：

- 心跳新鲜（<180s）且实例数 == 1 → 静默（退出码 0）
- 心跳缺失/陈旧，或实例数 0/≥2 → 杀旧 + detached 重启

设计教训（照抄 keylevel_guard 看门狗的两条）：
1. uv venv 的 `python.exe` 是 redirector stub，会再 spawn 真实解释器 → psutil 会数到 2 个
   实例。这里启动用 `pyvenv.cfg` 里的真实解释器，计数时跳过 stub。
2. **降级是状态、不是故障**：进程活着只是没收到强平（市场平静）属正常，不写非零退出码、
   不制造 cron incident；只有「重启失败」这类真故障才非零。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconf = getattr(_stream, "reconfigure", None)
    if callable(_reconf):
        _reconf(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_json import atomic_write_json  # noqa: E402

COLLECTOR = ROOT / "scripts/ws_liquidation_listener.py"
HEARTBEAT = ROOT / "data/.liquidation_ws_heartbeat.json"
HEALTH = ROOT / "data/.liquidation_ws_health.json"
LOG = ROOT / "data/liquidation_ws_collector.log"
STALE_SECONDS = 180          # 心跳超时阈值（采集器每 60s 至少刷一次）
# STUB_MARK 已废弃：改用 _is_collector_proc 精确匹配参数（见其 docstring）
TZ = timezone(timedelta(hours=8))


def log(message: str) -> None:
    line = f"[{datetime.now(TZ).isoformat()}] {message}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def real_python() -> str:
    """从 pyvenv.cfg 拿真实解释器（uv stub 会让 psutil 数到两个实例）。"""
    cfg = Path(sys.prefix) / "pyvenv.cfg"
    try:
        if cfg.exists():
            for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith("executable") and "=" in line:
                    exe = line.split("=", 1)[1].strip()
                    if exe and Path(exe).exists():
                        return exe
    except OSError:
        pass
    return sys.executable


def _is_collector_proc(cmdline) -> bool:
    """精确匹配：cmdline 里有一个**独立参数**等于/以 `ws_liquidation_listener.py` 结尾。

    不能用「cmdline 字符串包含脚本名」：诊断脚本 `python -c "...ws_liquidation_listener.py..."`
    会把脚本名当代码字面量带进 cmdline，造成误判成采集器实例。
    """
    for arg in cmdline or []:
        a = str(arg).replace("\\", "/")
        if a == "ws_liquidation_listener.py" or a.endswith("/ws_liquidation_listener.py"):
            return True
    return False


def collector_pids() -> list[int] | None:
    """返回采集器进程 PID 列表；psutil 不可用时返回 None（交给心跳判定）。"""
    try:
        import psutil
    except ImportError:
        return None
    found: list[int] = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        if proc.info["pid"] == os.getpid():
            continue
        if _is_collector_proc(proc.info.get("cmdline")):
            found.append(proc.info["pid"])
    return found


def heartbeat_age() -> float | None:
    try:
        hb = json.loads(HEARTBEAT.read_text(encoding="utf-8"))
        stamp = datetime.fromisoformat(str(hb.get("ts")))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=TZ)
        return (datetime.now(TZ) - stamp).total_seconds()
    except Exception:
        return None


def restart_collector() -> bool:
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "cmdline"]):
            if _is_collector_proc(proc.info.get("cmdline")):
                if proc.info["pid"] != os.getpid():
                    try:
                        proc.terminate()
                        log(f"killed PID={proc.info['pid']}")
                    except Exception:
                        pass
    except Exception as exc:
        log(f"psutil kill skipped: {type(exc).__name__}: {exc}")
    try:
        with open(LOG, "a", encoding="utf-8") as logf:
            subprocess.Popen(
                [real_python(), str(COLLECTOR)],
                stdout=logf, stderr=logf, cwd=str(ROOT),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                start_new_session=(os.name != "nt"),
            )
        log("collector restarted")
        return True
    except Exception as exc:
        log(f"restart FAILED: {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    pids = collector_pids()
    age = heartbeat_age()
    problems: list[str] = []
    if isinstance(pids, list) and len(pids) != 1:
        problems.append(f"instance_count={len(pids)}")
    if age is None:
        problems.append("heartbeat_missing")
    elif age > STALE_SECONDS:
        problems.append(f"heartbeat_stale={age:.0f}s")

    if not problems:
        row = {"status": "live", "pids": pids, "heartbeat_age_s": round(age or 0, 1),
               "updated_at": datetime.now(TZ).isoformat()}
        atomic_write_json(HEALTH, row)
        log(f"OK collector alive hb_age={age:.0f}s pid={pids}")
        return 0

    log(f"RESTART needed: {', '.join(problems)} (pids={pids}, hb_age={age})")
    ok = restart_collector()
    atomic_write_json(HEALTH, {
        "status": "live" if ok else "unavailable",
        "restarted": ok,
        "reasons": problems,
        "heartbeat_age_s": round(age or -1, 1),
        "updated_at": datetime.now(TZ).isoformat(),
    })
    if ok:
        return 0
    log("collector unavailable after restart attempt")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
