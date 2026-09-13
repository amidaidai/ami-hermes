#!/usr/bin/env python3
"""
数据新鲜度看门狗 v1.2（默认仅本地）
检查现役关键 JSON 的语义时间戳；缺失、陈旧或不可用均记为异常。
默认/check/report 均静默落盘；静默不代表健康，请读本地 JSON 报告。
仅显式 --send 可请求去重外发，HANGQING_NO_SEND=1 优先阻止发送。
"""
import json, sys, os, time
import importlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from source_health import payload_timestamp

TZ = timezone(timedelta(hours=8))
PROJECT_DATA = Path("D:/Hermes agent/data")
HERMES_DATA = Path(os.path.expanduser("~/AppData/Local/hermes/data"))

# 现役必需文件 + 阈值（小时）；所有候选路径缺失必须报异常。
# 两套落盘目录优先选择最新显式语义时间戳，不使用文件 mtime。
#
# 20260910 重写：原清单盯着 10 个**采集器已停用**的产出（x_sentiment / dune / qlib /
# stablecoin / oi_snapshot / deribit / orion / liquidation_pressure / polymarket …），
# 每次运行必然报 16 条过期 → 报警疲劳 → 看门狗被停用 → 真正的事故（BTC 到价监控
# 停摆 5 天）反而没人看见。
#
# 现在只盯**生产者还活着的**文件，并补上监控链自身的生命体征 —— 后者才是
# 「监控还活着吗」的直接证据，也是这次事故唯一能被提前发现的位置。
WATCH_FILES = {
    # source_snapshot.json is a shared compatibility file and may currently
    # belong to XAU after the last refresh.  It must not satisfy BTC freshness.
    # 20260910：阈值必须与刷新器自己的契约对齐 —— btc_tv_refresh.source_snapshot_status()
    # 用 max_age_hours=0.75（丢到 45 分钟才去刷）。看门狗若 30 分钟就报警，
    # 每个周期会白报 15 分钟（实测踩到），是自己造的噪声。
    "source_snapshot_BTCUSDT.json": {"threshold": 0.8, "paths": [PROJECT_DATA / "source_snapshot_BTCUSDT.json", HERMES_DATA / "source_snapshot_BTCUSDT.json"]},
    "source_snapshot_XAUUSD.json": {"threshold": 0.5, "paths": [PROJECT_DATA / "source_snapshot_XAUUSD.json", HERMES_DATA / "source_snapshot_XAUUSD.json"]},
    "tv_dmi_cache.json": {"threshold": 1, "paths": [PROJECT_DATA / "tv_dmi_cache.json", HERMES_DATA / "tv_dmi_cache.json"]},
    # 每品种专属缓存（btc_tv_refresh 每 20 分钟 / xau_tv_sync 每 15 分钟）
    "tv_live_BTCUSDT.json": {"threshold": 1, "paths": [PROJECT_DATA / "tv_live_BTCUSDT.json", HERMES_DATA / "tv_live_BTCUSDT.json"]},
    "xau_tv_state.json": {"threshold": 1, "paths": [PROJECT_DATA / "xau_tv_state.json", HERMES_DATA / "xau_tv_state.json"]},
    # 唯一批准监控源：批准位本身有 TTL，文件本身超过 24h 没被续期就是异常
    "keylevels_config.json": {"threshold": 24, "paths": [PROJECT_DATA / "keylevels_config.json", HERMES_DATA / "keylevels_config.json"]},
    # ── 监控链自身生命体征（20260910 新增，这次事故的直接教训）─────────
    ".keylevel_guard_heartbeat.json": {"threshold": 0.3, "paths": [PROJECT_DATA / ".keylevel_guard_heartbeat.json"]},
    ".keylevel_guard_health.json": {"threshold": 0.3, "paths": [PROJECT_DATA / ".keylevel_guard_health.json"]},
    # 结构复核：真正的时间戳在 keylevels_config.json 的 auto_approval_policy 里
    # （keylevels_structure_review.json 只是复核结果 {ok,valid,checked,stamped}，
    #  本身按设计不含时间戳 —— 盯它必然天天误报「无显式时间戳」→ 报警疲劳）。
    "structure_reviewed_at": {
        "threshold": 6,
        "payload_path": ("auto_approval_policy", "structure_reviewed_at"),
        "paths": [PROJECT_DATA / "keylevels_config.json", HERMES_DATA / "keylevels_config.json"],
    },
}

# 有意不监控的来源（生产者已停用）。列在这里是为了让「为什么没报」有据可查，
# 而不是让它们继续制造噪声把真事故淹掉。
#   需要恢复其中任何一个时，先把对应 cron 恢复运行，再把文件加回 WATCH_FILES。
PAUSED_SOURCES = {
    "btc_ref_levels.json": "btc_ref_levels_sync cron 已停用，能力由 keylevels_config 承担",
    "monitor_heartbeat.json": "旧行情守望守护（monitor/market_watchdog）已退役",
    ".btc_daemon_heartbeat.json": "旧 btc_daemon 守护已退役，现役为 keylevel_guard",
    "macro_snapshot.json / polymarket_sentiment.json": "宏观Poly刷新脚本已归档",
    "x_sentiment*.json / dune_cache.json / qlib_factors.json": "对应采集 cron 已停用",
    "stablecoin_snapshot.json / liquidation_pressure.json / oi_snapshot_*.json": "对应采集 cron 已停用",
    "deribit_options.json / orion_radar.json": "对应采集 cron 已停用",
}


def _nested(payload, payload_path):
    """Follow a declared key path; anything missing returns None."""
    node = payload
    for key in payload_path or ():
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _best_existing(paths, payload_path=None):
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    stamped = []
    for path in existing:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if payload_path:
                from source_health import parse_timestamp
                timestamp = parse_timestamp(_nested(payload, payload_path))
            else:
                timestamp = payload_timestamp(payload) if isinstance(payload, dict) else None
            if timestamp is not None:
                stamped.append((timestamp.timestamp(), path))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
    if stamped:
        return max(stamped, key=lambda item: item[0])[1]
    # No semantic timestamp exists. Return a deterministic candidate so the
    # caller can report the missing timestamp; do not use mtime as evidence.
    return existing[0]


def _nested_health(path: Path, payload_path, *, threshold_hours: float) -> dict:
    """Freshness of a nested timestamp key (e.g. auto_approval_policy.*)."""
    try:
        from source_health import parse_timestamp
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"fresh": False, "status": "unavailable", "timestamp": None,
                "age_hours": None, "reason": f"JSON不可读: {type(exc).__name__}"}
    timestamp = parse_timestamp(_nested(payload, payload_path)) if isinstance(payload, dict) else None
    if timestamp is None:
        return {"fresh": False, "status": "unavailable", "timestamp": None,
                "age_hours": None, "reason": "嵌套时间戳缺失/无效"}
    age_hours = (datetime.now(TZ) - timestamp.astimezone(TZ)).total_seconds() / 3600
    if age_hours <= threshold_hours:
        return {"fresh": True, "status": "live", "timestamp": timestamp.isoformat(),
                "age_hours": round(age_hours, 3), "reason": "嵌套时间戳新鲜"}
    return {"fresh": False, "status": "stale_cache", "timestamp": timestamp.isoformat(),
            "age_hours": round(age_hours, 3),
            "reason": f"嵌套时间戳过期+{round((age_hours - threshold_hours) / threshold_hours * 100)}%"}


def _payload_health(path: Path, *, threshold_hours: float, payload_path=None) -> dict:
    """Return semantic freshness; file mtime is never market evidence."""
    if payload_path:
        return _nested_health(path, payload_path, threshold_hours=threshold_hours)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from source_health import inspect_json_file
        return inspect_json_file(path, max_age_hours=threshold_hours)
    except Exception as exc:
        return {
            "fresh": False,
            "status": "unavailable",
            "timestamp": None,
            "age_hours": None,
            "reason": f"健康检查失败: {type(exc).__name__}: {exc}",
        }


def _quality_issue(fname: str, path: Path) -> str:
    """检测“时间新但内容坏”的假新鲜缓存。"""
    if fname != "liquidation_pressure.json":
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return "JSON损坏"
    rows = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        return "结果为空"
    valid = [row for row in rows if isinstance(row, dict) and row.get("status") not in ("api_error", "no_data") and float(row.get("oi") or 0) > 0]
    return "接口全部失败" if not valid else ""


def _fmt_hours(h: float | None) -> str:
    if h is None:
        return "—"
    if h < 1:
        return f"{h * 60:.0f}m"
    return f"{h:.1f}h" if h < 10 else f"{h:.0f}h"


def check():
    """Read active artifacts only, without importing any delivery code."""
    items = []
    for name, cfg in WATCH_FILES.items():
        path = _best_existing(cfg["paths"], cfg.get("payload_path"))
        health = (_payload_health(path, threshold_hours=float(cfg["threshold"]),
                                  payload_path=cfg.get("payload_path"))
                  if path is not None else
                  {"fresh": False, "status": "missing", "reason": "现役关键文件不存在",
                   "age_hours": None, "timestamp": None})
        quality = _quality_issue(name, path) if path is not None else ""
        if quality:
            health = dict(health, fresh=False, status="unavailable", reason=quality)
        items.append(dict(health, name=name, threshold_hours=float(cfg["threshold"]),
                          paths=[str(p) for p in cfg["paths"]],
                          selected_path=str(path) if path is not None else None))
    issues = sum(not item.get("fresh", False) for item in items)
    return {"generated_at": datetime.now(TZ).isoformat(), "healthy": issues == 0,
            "active_count": len(items), "issue_count": issues, "items": items,
            "paused_sources": dict(PAUSED_SOURCES)}


DEFAULT_REPORT = PROJECT_DATA / "data_freshness_watchdog_report.json"


def main(argv=None):
    """Quiet local report by default, including under no_agent cron.

    check/report both persist JSON. Only report --send authorizes delivery;
    HANGQING_NO_SEND=1 overrides it. Findings are data, not process errors.
    """
    import argparse
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("check", "report"), default="report")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--send", action="store_true", help="Explicitly authorize one deduplicated alert")
    args = parser.parse_args(argv)
    if args.command == "check" and args.send:
        parser.error("check is local-only; use report --send for explicit delivery")
    result = check()
    result["delivery"] = "local_only"
    authorized = args.send and os.environ.get("HANGQING_NO_SEND") != "1"
    if args.send and not authorized:
        result["delivery"] = "blocked_by_no_send"

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                                             prefix=args.output.name + ".", suffix=".tmp", delete=False) as handle:
                name = handle.name
                json.dump(result, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(name, args.output)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    save()  # Durable evidence before any optional external action.
    if authorized and result["issue_count"]:
        try:
            sender = importlib.import_module("alert_dedup").dedup_wrapper
            output = "数据新鲜度告警\n" + "\n".join(
                f"{item['name']}: {item['status']} — {item.get('reason', '')}"
                for item in result["items"] if not item.get("fresh"))
            sender("data_freshness", output, force_seconds=14400)
            result["delivery"] = "dedup_requested"  # Not proof of remote delivery.
        except Exception as exc:
            result["delivery"] = "failed"
            result["delivery_error"] = type(exc).__name__
            save()
            return 1
        save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
