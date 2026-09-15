#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC 关键位实时守护看门狗 — 心跳超时自动重启。零token no_agent。

守护进程(keylevel_guard.py)每 0.5s 轮询并写心跳。本看门狗每 2min 检查心跳：
- 心跳 < 90s 新鲜 → 静默（守护正常）
- 心跳陈旧/缺失 → 杀旧进程 + 重启守护（nohup 拉起）
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

_stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(_stdout_reconfigure):
    _stdout_reconfigure(encoding="utf-8", errors="replace")
_stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if callable(_stderr_reconfigure):
    _stderr_reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_json import atomic_write_json
GUARD = ROOT / "scripts/keylevel_guard.py"
CONFIG = ROOT / "data/keylevels_config.json"
HEARTBEAT = ROOT / "data/.keylevel_guard_heartbeat.json"
HEALTH = ROOT / "data/.keylevel_guard_health.json"
LOG = ROOT / "data/keylevel_guard.log"
STALE_SECONDS = 90   # 心跳超时阈值
MIN_ACTIVE_APPROVED_LEVELS = 1

TZ = timezone(timedelta(hours=8))


def auto_renew_existing_approved_levels(now: datetime | None = None) -> dict:
    """Renew already-approved levels when the persisted policy authorizes it."""
    now = now or datetime.now(TZ)
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return {"changed": False, "error": f"config_read:{type(exc).__name__}"}
    policy = config.get("auto_approval_policy") or {}
    if not isinstance(policy, dict) or policy.get("enabled") is not True:
        return {"changed": False, "reason": "policy_disabled"}
    if policy.get("scope") != "existing_levels_only":
        return {"changed": False, "error": "unsupported_scope"}
    try:
        ttl_hours = float(policy.get("ttl_hours", 6))
        renew_before_minutes = float(policy.get("renew_before_minutes", 30))
    except (TypeError, ValueError):
        return {"changed": False, "error": "invalid_policy_window"}
    if ttl_hours <= 0 or renew_before_minutes < 0:
        return {"changed": False, "error": "invalid_policy_window"}

    max_structure_age = policy.get("max_structure_age_hours")
    structure_deadline = None
    if max_structure_age is not None:
        try:
            max_structure_age = float(max_structure_age)
            reviewed_raw = policy.get("structure_reviewed_at") or policy.get("authorized_at")
            reviewed_at = datetime.fromisoformat(str(reviewed_raw).replace("Z", "+00:00"))
            if reviewed_at.tzinfo is None:
                reviewed_at = reviewed_at.replace(tzinfo=TZ)
        except (TypeError, ValueError):
            return {"changed": False, "error": "invalid_structure_review_window"}
        if max_structure_age <= 0:
            return {"changed": False, "error": "invalid_structure_review_window"}
        structure_deadline = reviewed_at.astimezone(TZ) + timedelta(hours=max_structure_age)
        structure_age_hours = (now - reviewed_at.astimezone(TZ)).total_seconds() / 3600.0
        if structure_age_hours > max_structure_age:
            return {
                "changed": False,
                "error": "structure_review_required",
                "structure_age_hours": round(structure_age_hours, 2),
                "max_structure_age_hours": max_structure_age,
            }

    threshold = now + timedelta(minutes=renew_before_minutes)
    new_until = now + timedelta(hours=ttl_hours)
    if structure_deadline is not None:
        new_until = min(new_until, structure_deadline)
    renewed = 0
    for block in (config.get("symbols", {}) or {}).values():
        if not isinstance(block, dict):
            continue
        for level in block.get("levels", []) or []:
            if not isinstance(level, dict) or level.get("enabled", True) is False:
                continue
            raw = level.get("valid_until") or level.get("expires_at")
            try:
                expires = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=TZ)
            except (TypeError, ValueError):
                expires = now
            if expires <= threshold:
                level["valid_until"] = new_until.isoformat()
                renewed += 1
    if not renewed:
        return {"changed": False, "reason": "not_due"}

    stamp = now.isoformat()
    config["updated_at"] = stamp
    config["approval_renewal"] = {
        "mode": "existing_levels_only",
        "renewed_at": stamp,
        "valid_until": new_until.isoformat(),
        "source": "用户持久授权自动续期(现有批准位)",
        "renewed_count": renewed,
    }
    atomic_write_json(CONFIG, config)
    return {"changed": True, "renewed_count": renewed, "valid_until": new_until.isoformat()}

# uv venv 的 python.exe 是 redirector stub：启动时会再 spawn 一个真实 uv python 子进程
# 跑同一个 keylevel_guard.py → psutil 会数到 2 个实例（stub+real）→ watchdog 误判
# count=2 → 每 2 分钟杀杀重启死循环。这里直接解析 pyvenv.cfg 拿真实解释器用于 Popen；
# is_guard_alive 计数时也跳过 stub（cmdline 指向 hermes-agent\\venv\\Scripts\\python.exe 的）。
PYVENV_CFG = Path(sys.prefix) / "pyvenv.cfg"
REAL_PYTHON = sys.executable
STUB_MARK = "hermes-agent\\venv\\Scripts\\python.exe"


def _resolve_real_python() -> str:
    """从 pyvenv.cfg 的 executable 字段解析真实解释器路径（uv venv 场景）。"""
    try:
        if PYVENV_CFG.exists():
            for line in PYVENV_CFG.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("executable") and "=" in line:
                    exe = line.split("=", 1)[1].strip()
                    if exe and Path(exe).exists():
                        return exe
    except Exception:
        pass
    return sys.executable


REAL_PYTHON = _resolve_real_python()


def log(m):
    line = f"[{datetime.now(tz=TZ).isoformat()}] {m}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def check_config_health() -> dict:
    """Check the approved source, not just process liveness."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from keylevel_guard import config_health
        return config_health()
    except Exception as exc:
        return {
            "status": "degraded",
            "active_approved_levels": 0,
            "source": str(ROOT / "data/keylevels_config.json"),
            "error": f"{type(exc).__name__}: {str(exc)[:120]}",
        }


def write_health(health: dict) -> None:
    row = dict(health)
    row["updated_at"] = datetime.now(TZ).isoformat()
    atomic_write_json(HEALTH, row)


def is_guard_alive():
    """用 psutil 精确判断守护进程是否存在（过滤自身/子进程虚警 + uv stub 套娃）。"""
    try:
        import psutil
        me = os.getpid()
        matches = []
        for p in psutil.process_iter(["pid", "cmdline"]):
            cmdline = " ".join(p.info.get("cmdline") or [])
            if "keylevel_guard.py" in cmdline and "watchdog" not in cmdline:
                if p.info["pid"] != me:
                    # uv venv stub：cmdline python 指向 hermes-agent\\venv\\Scripts\\python.exe，
                    # 且其子进程是同一个 keylevel_guard.py（真实解释器）→ stub 不算实例。
                    pypath = (p.info.get("cmdline") or [""])[0]
                    if STUB_MARK in pypath:
                        # stub 会带一个 real 子进程；若没有子进程（独立启动）则仍算实例
                        try:
                            children = p.children()
                            real_child = any(
                                "keylevel_guard.py" in " ".join(c.info.get("cmdline") or [])
                                for c in children
                            )
                            if real_child:
                                continue
                        except Exception:
                            continue
                    matches.append(p.info["pid"])
        # 0=死，1=正常，>1=重复实例；重复也必须重启收敛。
        return matches
    except ImportError:
        return None  # psutil 不可用时无法判断，交给心跳逻辑


def _run_structure_review() -> dict:
    """先做一次结构复核；通过才盖 structure_reviewed_at，否则安全闸照常落下。

    这是 auto_approval_policy.max_structure_age_hours=24 那道闸的唯一合法来源 ——
    此前没有任何脚本会写该字段，导致任何一次人工复核后最多 24 小时监控必停摆。
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from keylevels_structure_review import review, apply_review
        return apply_review(result=review())
    except Exception as exc:
        return {"ok": False, "stamped": False,
                "stamp_reason": f"结构复核不可用: {type(exc).__name__}: {str(exc)[:90]}"}


def main():
    review_result = _run_structure_review()
    if review_result.get("stamped"):
        log(f"STRUCTURE-REVIEW ok {review_result.get('valid')}/{review_result.get('checked')} "f"→ structure_reviewed_at 已更新")
    elif review_result.get("ok"):
        log(f"STRUCTURE-REVIEW ok (skip write): {review_result.get('stamp_reason')}")
    else:
        log(f"STRUCTURE-REVIEW FAILED: {review_result.get('stamp_reason')}")
    renewal = auto_renew_existing_approved_levels()
    if renewal.get("changed"):
        log(f"AUTO-RENEW approved levels={renewal['renewed_count']} valid_until={renewal['valid_until']}")
    elif renewal.get("error"):
        log(f"AUTO-RENEW skipped error={renewal['error']}")
    health = check_config_health()
    write_health(health)
    active_levels = int(health.get("active_approved_levels", 0) or 0)
    if health.get("status") == "idle":
        log(
            "IDLE: 全部批准位已用户静默（enabled=false）；"
            "守护保持单实例，不记 DEGRADED"
        )
    elif active_levels < MIN_ACTIVE_APPROVED_LEVELS:
        log("DEGRADED: keylevels_config 当前无有效批准关键位；不把进程存活误报为监控正常")
        # 2026-09-15 修：这里原来 `sys.exit(2)`。实测 9/1–9/12 该条件持续 12 天，
        # 每 2 分钟生成一条 cron incident（共 3,745 条）；且错误文本带时间戳 →
        # 每次签名都不同，Hermes 无法去重，incident 表被单一条件刷爆、无人看。
        # 降级是**状态**不是**故障**：可见性靠 stdout（deliver=local 会落
        # cron/output/<job_id>/），再结构化写进 health 文件供审计读取；
        # 退出码留给真故障（脚本崩/依赖缺失），不再拿它喊状态。
        write_health({**health, "active_approved_levels": active_levels,
                      "degraded": True, "degraded_reason": "no_active_approved_levels"})
        sys.exit(0)

    alive_info = is_guard_alive()
    alive = bool(alive_info) if isinstance(alive_info, list) else alive_info
    hb_age = None
    hb_pid = None
    try:
        with open(HEARTBEAT) as f:
            hb = json.load(f)
        hb_pid = hb.get("pid")
        t = datetime.fromisoformat(hb["ts"])
        now = datetime.now(tz=TZ)
        hb_age = (now - t).total_seconds()
    except Exception:
        hb_age = None

    # 判定是否需要重启
    needs_restart = False
    reason = ""
    if isinstance(alive_info, list) and len(alive_info) != 1:
        needs_restart, reason = True, f"guard process count={len(alive_info)}"
    elif hb_age is None:
        needs_restart, reason = True, "heartbeat missing"
    elif hb_age > STALE_SECONDS:
        needs_restart, reason = True, f"heartbeat stale {hb_age:.0f}s"
    elif alive is False:
        needs_restart, reason = True, "process not alive"

    if not needs_restart:
        log(f"OK guard alive(alive={alive}) hb_age={hb_age:.0f}s pid={hb_pid}")
        sys.exit(0)

    log(f"RESTART needed: {reason} (alive={alive} hb_age={hb_age})")
    # 杀旧守护（用 psutil 精确匹配，忽略自身）
    try:
        import psutil
        for p in psutil.process_iter(["pid", "cmdline"]):
            cmdline = " ".join(p.info.get("cmdline") or [])
            if "keylevel_guard.py" in cmdline and "watchdog" not in cmdline:
                if p.info["pid"] != os.getpid():
                    try:
                        p.terminate()
                        log(f"killed PID={p.info['pid']}")
                    except Exception:
                        pass
    except Exception as e:
        log(f"psutil kill failed: {e}")

    # 重启（detached）——用真实解释器（pyvenv.cfg executable），避免 uv stub 双节点
    try:
        python = REAL_PYTHON
        with open(LOG, "a", encoding="utf-8") as logf:
            subprocess.Popen(
                [python, str(GUARD)],
                stdout=logf, stderr=logf,
                cwd=str(ROOT),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                if os.name == "nt" else 0,
                start_new_session=(os.name != "nt"),
            )
        log("guard restarted")
    except Exception as e:
        log(f"restart failed: {e}")


if __name__ == "__main__":
    main()
