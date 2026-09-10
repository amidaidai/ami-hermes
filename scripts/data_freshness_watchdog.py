#!/usr/bin/env python3
"""
数据新鲜度看门狗 v1.1
检查关键JSON数据文件的最后修改时间，过期超过阈值推告警。
只检查实际存在的文件，静默=健康。
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

# 实际存在的文件 + 阈值（小时）
# 注意：棠溪系统有两套落盘目录。paths 会取“存在文件中的最新 mtime”，避免双落盘期间误报。
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
    # 结构复核结果：盖不上章说明关键位正在失效，必须在闸落下前被看见
    "keylevels_structure_review.json": {"threshold": 6, "paths": [PROJECT_DATA / "keylevels_structure_review.json", HERMES_DATA / "keylevels_structure_review.json"]},
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


def _best_existing(paths):
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    stamped = []
    for path in existing:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
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


def _payload_health(path: Path, *, threshold_hours: float) -> dict:
    """Return semantic freshness; file mtime is never market evidence."""
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


def main():
    now = datetime.now(TZ)
    ts = now.strftime("%Y年%m月%d日%H：%M")
    
    stale = []
    fresh = []
    
    for fname, cfg in WATCH_FILES.items():
        threshold_hours = float(cfg["threshold"])
        fp = _best_existing(cfg["paths"])
        if fp is None:
            continue  # 跳过不存在的文件，不告警
        
        payload_health = _payload_health(fp, threshold_hours=threshold_hours)
        raw_age_hours = payload_health.get("age_hours")
        age_hours = float(raw_age_hours) if isinstance(raw_age_hours, (int, float)) else None
        quality_issue = _quality_issue(fname, fp)

        if not payload_health.get("fresh") or quality_issue or age_hours is None:
            stale.append((fname, age_hours, threshold_hours, str(fp), quality_issue or payload_health.get("reason", "")))
        else:
            fresh.append((fname, round(age_hours, 2), str(fp)))
    
    if not stale:
        # 干净无异状，完全静默
        return 0

    lines = [f"## 数据过期/质量告警 — {ts}", ""]
    lines.append("| 文件 | 数据年龄 | 阈值 | 问题 |")
    lines.append("|---|---:|---:|:---|")
    over_values = []
    for fname, age, threshold, fp, quality_issue in stale:
        over_pct = round((age - threshold) / threshold * 100) if isinstance(age, (int, float)) and threshold > 0 else None
        if isinstance(age, (int, float)) and age > threshold:
            over_values.append(over_pct)
        issue = quality_issue or (f"过期+{over_pct}%" if over_pct is not None else "无显式时间戳")
        lines.append(f"| {fname} | {_fmt_hours(age)} | {_fmt_hours(threshold)} | 💀 {issue} |")
    lines.append("")
    lines.append(f"正常文件: {len(fresh)} 个 · 异常文件: {len(stale)} 个")
    lines.append("")
    worst = f"最严重过期+{max(over_values)}%" if over_values else "内容质量失败"
    lines.append(f"**总体结论**: **{len(stale)}个数据源异常**（{worst}），**需检查对应采集脚本/接口**。")

    output = "\n".join(lines)
    try:
        dedup_wrapper = importlib.import_module("alert_dedup").dedup_wrapper
        dedup_wrapper("data_freshness", output, force_seconds=14400)
    except (ImportError, AttributeError):
        print(output)
    # v9.8: 同时推 TG 真表格（原本漏发）
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from telegram_reliable import push_tg_rich
        push_tg_rich("", output)
    except Exception as _te:
        print(f"⚠ 数据新鲜度RichMarkdown推送失败: {_te}", file=sys.stderr)
    # no_agent 语义：stdout 非空即推送，非零退出会被 cron 标记为脚本错误
    return 0


if __name__ == "__main__":
    sys.exit(main())
