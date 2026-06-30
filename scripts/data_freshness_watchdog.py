#!/usr/bin/env python3
"""
数据新鲜度看门狗 v1.1
检查关键JSON数据文件的最后修改时间，过期超过阈值推告警。
只检查实际存在的文件，静默=健康。
"""
import json, sys, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
PROJECT_DATA = Path("D:/Hermes agent/data")
HERMES_DATA = Path(os.path.expanduser("~/AppData/Local/hermes/data"))

# 实际存在的文件 + 阈值（小时）
# 注意：棠溪系统有两套落盘目录。之前只看 HERMES_DATA，导致项目目录内刚更新的
# btc_ref_levels/tv_dmi_cache/monitor_heartbeat 被误判为 10h 过期。
# paths 会取“存在文件中的最新 mtime”，避免双落盘期间误报。
WATCH_FILES = {
    "btc_history.jsonl": {"threshold": 24, "paths": [PROJECT_DATA / "btc_history.jsonl", HERMES_DATA / "btc_history.jsonl"]},
    "btc_ref_levels.json": {"threshold": 8, "paths": [PROJECT_DATA / "btc_ref_levels.json", HERMES_DATA / "btc_ref_levels.json"]},
    ".btc_daemon_heartbeat.json": {"threshold": 0.1, "paths": [PROJECT_DATA / ".btc_daemon_heartbeat.json"]},
    "macro_snapshot.json": {"threshold": 6, "paths": [HERMES_DATA / "macro_snapshot.json", PROJECT_DATA / "macro_snapshot.json"]},
    "polymarket_sentiment.json": {"threshold": 6, "paths": [HERMES_DATA / "polymarket_sentiment.json", PROJECT_DATA / "polymarket_sentiment.json"]},
    "tv_dmi_cache.json": {"threshold": 4, "paths": [PROJECT_DATA / "tv_dmi_cache.json", HERMES_DATA / "tv_dmi_cache.json"]},
    "sentiment.json": {"threshold": 4, "paths": [HERMES_DATA / "sentiment.json", PROJECT_DATA / "sentiment.json"]},
    "liquidation_pressure.json": {"threshold": 4, "paths": [HERMES_DATA / "liquidation_pressure.json", PROJECT_DATA / "liquidation_pressure.json"]},
    "stablecoin_snapshot.json": {"threshold": 6, "paths": [HERMES_DATA / "stablecoin_snapshot.json", PROJECT_DATA / "stablecoin_snapshot.json"]},
    "oi_snapshot_BTCUSDT.json": {"threshold": 1, "paths": [HERMES_DATA / "oi_snapshot_BTCUSDT.json", PROJECT_DATA / "oi_snapshot_BTCUSDT.json"]},
    "oi_snapshot_ETHUSDT.json": {"threshold": 1, "paths": [HERMES_DATA / "oi_snapshot_ETHUSDT.json", PROJECT_DATA / "oi_snapshot_ETHUSDT.json"]},
    "monitor_heartbeat.json": {"threshold": 0.3, "paths": [PROJECT_DATA / "monitor_heartbeat.json", HERMES_DATA / "monitor_heartbeat.json"]},
}


def _best_existing(paths):
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def _fmt_hours(h: float) -> str:
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
        
        mtime = fp.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600
        
        if age_hours > threshold_hours:
            stale.append((fname, round(age_hours, 2), threshold_hours, str(fp)))
        else:
            fresh.append((fname, round(age_hours, 2), str(fp)))
    
    if not stale:
        # 干净无异状，完全静默
        return 0

    lines = [f"## 数据过期告警 — {ts}", ""]
    lines.append("| 文件 | 过期时间 | 阈值 | 落后幅度 |")
    lines.append("|---|---|---:|:---|")
    for fname, age, threshold, fp in stale:
        over_pct = round((age - threshold) / threshold * 100) if threshold > 0 else 999
        lines.append(f"| {fname} | {_fmt_hours(age)} | {_fmt_hours(threshold)} | 💀 +{over_pct}% |")
    lines.append("")
    lines.append(f"正常文件: {len(fresh)} 个 · 过期文件: {len(stale)} 个")

    output = "\n".join(lines)
    try:
        from alert_dedup import dedup_wrapper
        dedup_wrapper("data_freshness", output, force_seconds=14400)
    except ImportError:
        print(output)
    # no_agent 语义：stdout 非空即推送，非零退出会被 cron 标记为脚本错误
    return 0


if __name__ == "__main__":
    sys.exit(main())
