#!/usr/bin/env python3
"""棠溪分析系统只读预检：运行态、数据身份、新鲜度和Cron。"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CRON = Path.home() / "AppData/Local/hermes/cron/jobs.json"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": str(exc)}


def parse_ts(value):
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def age_hours(value) -> float:
    ts = parse_ts(value)
    return 999.0 if ts is None else max(0.0, (time.time() - ts) / 3600)


def cache_report(
    name: str,
    max_hours: float,
    *,
    expected_symbol: str | None = None,
    data_dir: Path | None = None,
):
    return _cache_report(
        name, max_hours, expected_symbol=expected_symbol, data_dir=data_dir,
    )


def _cache_report(
    name: str,
    max_hours: float,
    *,
    expected_symbol: str | None = None,
    data_dir: Path | None = None,
) -> dict:
    """Inspect semantic payload freshness; never substitute file mtime."""
    root = data_dir or DATA
    path = root / name
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from source_health import inspect_json_file
        result = inspect_json_file(
            path, max_age_hours=max_hours, expected_symbol=expected_symbol,
        )
    except Exception as exc:
        result = {
            "exists": path.exists(), "fresh": False, "status": "unavailable",
            "timestamp": None, "age_hours": None, "symbol": None,
            "reason": f"健康检查不可用: {type(exc).__name__}: {exc}",
        }
    age = result.get("age_hours")
    return {
        "name": name,
        "exists": bool(result.get("exists")),
        "age_h": round(float(age), 2) if isinstance(age, (int, float)) else None,
        "fresh": bool(result.get("fresh")),
        "symbol": result.get("symbol"),
        "status": result.get("status"),
        "timestamp": result.get("timestamp"),
        "reason": result.get("reason") or "",
    }


def strict_market_contracts() -> dict[str, dict]:
    """Run the same five-TF/pair validators used by production cards."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from tv_five_tf_contract import load_five_tf_snapshot
        from xau_tv_sync import validate_xau_outputs

        btc = load_five_tf_snapshot("BTCUSDT", data_dir=DATA, max_age_minutes=30.0)
        state = read_json(DATA / "xau_tv_state.json")
        live = read_json(DATA / "tv_live_XAUUSD.json")
        xau = validate_xau_outputs(state, live, require_batch_id=True)
        return {"btc_five_tf": btc, "xau_pair": xau}
    except Exception as exc:
        error = {"usable": False, "reason": f"严格契约检查失败: {type(exc).__name__}: {exc}"}
        return {"btc_five_tf": error, "xau_pair": error}


def cron_policy_issues(jobs: list[dict]) -> list[str]:
    """Find stale direct-push instructions in enabled no-agent jobs."""
    stale_markers = ("必须推送 386", "send_telegram_reliable", "telegram_direct")
    issues = []
    for job in jobs:
        if not isinstance(job, dict) or not job.get("enabled") or job.get("no_agent") is not True:
            continue
        prompt = str(job.get("prompt") or "")
        if any(marker in prompt for marker in stale_markers):
            issues.append(f"{job.get('name', '?')}:过期直接推送指令")
    return issues


def keylevel_runtime_report(max_age_seconds: float = 120.0) -> dict:
    """Validate the active keylevel guard, not retired daemon heartbeats."""
    heartbeat = DATA / ".keylevel_guard_heartbeat.json"
    result = {"process_count": None, "heartbeat_age_s": None, "usable": False, "reason": ""}
    try:
        import psutil
        matches = []
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "keylevel_guard.py" in cmd and "watchdog" not in cmd:
                    matches.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        result["process_count"] = len(matches)
    except Exception as exc:
        result["reason"] = f"进程检查不可用: {type(exc).__name__}"
        return result
    payload = read_json(heartbeat)
    stamp = parse_ts(payload.get("ts")) if isinstance(payload, dict) else None
    if stamp is None:
        result["reason"] = "关键位守护心跳缺失或无显式时间戳"
        return result
    result["heartbeat_age_s"] = round(max(0.0, time.time() - stamp), 1)
    result["usable"] = result["process_count"] == 1 and result["heartbeat_age_s"] <= max_age_seconds
    result["reason"] = (
        "现役关键位守护单实例且心跳新鲜" if result["usable"]
        else f"进程数={result['process_count']}·心跳年龄={result['heartbeat_age_s']}s"
    )
    return result


def cron_runtime_issues(jobs: list[dict]) -> list[str]:
    """Fail health checks when an enabled job is currently failing."""
    issues = []
    bad_states = {"error", "failed", "timeout", "timed_out"}
    for job in jobs:
        if not isinstance(job, dict) or not job.get("enabled"):
            continue
        name = str(job.get("name") or "?")
        state = str(job.get("state") or "").strip().lower()
        last_status = str(job.get("last_status") or "").strip().lower()
        if state in bad_states or last_status in bad_states:
            detail = state if state in bad_states else last_status
            issues.append(f"{name}:最近运行失败({detail})")
    return issues


def main() -> int:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"棠溪分析系统预检 · {now}")
    sock = socket.socket(); sock.settimeout(2)
    try:
        cdp_ok = sock.connect_ex(("127.0.0.1", 9222)) == 0
    finally:
        sock.close()
    print(f"TV CDP: {'OK' if cdp_ok else 'DOWN'}")

    cache_specs = (
        ("tv_live_BTCUSDT.json", 2, "BTCUSDT"),
        ("tv_live_XAUUSD.json", 2, "XAUUSD"),
        ("source_snapshot_BTCUSDT.json", 1, "BTCUSDT"),
        ("source_snapshot_XAUUSD.json", 1, "XAUUSD"),
    )
    cache_results = []
    for name, limit, expected in cache_specs:
        r = _cache_report(name, limit, expected_symbol=expected)
        cache_results.append(r)
        age = f"{r['age_h']}h" if r["age_h"] is not None else "—"
        print(f"数据 {name}: {'OK' if r['fresh'] else 'STALE/MISSING'} age={age} symbol={r['symbol'] or '-'} status={r['status']} reason={r['reason']}")

    contracts = strict_market_contracts()
    btc_contract = contracts["btc_five_tf"]
    xau_contract = contracts["xau_pair"]
    print(
        "BTC TV五周期: "
        f"{'OK' if btc_contract.get('usable') else 'FAIL'} "
        f"coverage={btc_contract.get('coverage', 0)}/5 reason={btc_contract.get('reason', '')}"
    )
    print(
        "XAU五周期+5m行动格: "
        f"{'OK' if xau_contract.get('usable') else 'FAIL'} "
        f"reason={xau_contract.get('reason', '')}"
    )

    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from keylevel_guard import config_health
        # 走 read_json 读配置再交给 config_health：既不重复解析，也让本检查
        # 可被测试注入（历史测试 monkeypatch audit.read_json 却打不到这里，
        # 因为旧实现是 config_health() 直读文件）。
        kl_config = read_json(DATA / "keylevels_config.json")
        kl_health = config_health(kl_config if isinstance(kl_config, dict) else {})
    except Exception as exc:
        kl_health = {
            "status": "degraded",
            "active_approved_levels": 0,
            "configured_levels": 0,
            "enabled_levels": 0,
            "push_enabled_levels": 0,
            "monitoring_intent": "undeclared",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    kl_status = str(kl_health.get("status") or "degraded")
    kl_intent = str(kl_health.get("monitoring_intent") or "undeclared")
    kl_label = {"ok": "OK", "idle": "IDLE", "degraded": "DEGRADED"}.get(kl_status, kl_status.upper())
    print(
        f"批准关键位: {kl_label} "
        f"active={kl_health.get('active_approved_levels')} "
        f"configured={kl_health.get('configured_levels')} "
        f"enabled={kl_health.get('enabled_levels')} "
        f"pushable={kl_health.get('push_enabled_levels')} "
        f"intent={kl_intent}"
    )
    # 「idle」只说明当前没有位在监控，**不等于健康**。
    # 它混了两种语义：用户主动静默（合法）与监控意外失效（事故）。
    # 历史教训：批准位全失效、到价监控停摆时，旧判定 `kl_status in {"ok","idle"}`
    # 仍返回绿灯，没人发现。现在只有显式声明静默/退役才放过，其余一律 fail closed。
    kl_ok = kl_status == "ok" or (
        kl_status == "idle" and kl_intent in {"user_silenced", "retired"}
    )
    keylevel_runtime = keylevel_runtime_report()
    print(
        "关键位守护运行态: "
        f"{'OK' if keylevel_runtime.get('usable') else 'FAIL'} "
        f"processes={keylevel_runtime.get('process_count')} "
        f"heartbeat_age={keylevel_runtime.get('heartbeat_age_s')}s "
        f"reason={keylevel_runtime.get('reason', '')}"
    )

    jobs_payload = read_json(CRON)
    jobs = (
        [job for job in jobs_payload.get("jobs", []) if isinstance(job, dict)]
        if isinstance(jobs_payload, dict)
        else []
    )
    print(f"Cron: total={len(jobs)} enabled={sum(bool(j.get('enabled')) for j in jobs)}")
    policy_issues = cron_policy_issues(jobs)
    runtime_issues = cron_runtime_issues(jobs)
    cron_issues = policy_issues + runtime_issues
    if cron_issues:
        print(f"Cron策略: FAIL {';'.join(cron_issues)}")
    else:
        print("Cron策略: OK")
    for job in jobs:
        if job.get("enabled") or job.get("last_status") == "error":
            print(f"  {job.get('name','?')} enabled={job.get('enabled')} state={job.get('state')} last={job.get('last_status','?')} script={job.get('script','')}")

    missing = []
    for module in ("requests", "pydantic", "aiohttp", "numpy", "pandas", "websockets"):
        try:
            __import__(module)
        except Exception:
            missing.append(module)
    print(f"Python deps: {'OK' if not missing else 'MISSING '+','.join(missing)}")
    # Dependency failures are a runtime blocker too: the preflight must not
    # report healthy market contracts while the collector interpreter cannot
    # import its required data stack.
    core_ok = bool(
        cdp_ok
        and all(result.get("fresh") for result in cache_results)
        and kl_ok
        and keylevel_runtime.get("usable")
        and btc_contract.get("usable")
        and xau_contract.get("usable")
        and not cron_issues
        and not missing
    )
    if not kl_ok:
        print(f"批准关键位判定: FAIL ({kl_status}/{kl_intent}) —— 监控不可用或静默未声明")
    return 0 if core_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
