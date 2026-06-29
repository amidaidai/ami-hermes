#!/usr/bin/env python3
"""
数据新鲜度看门狗 v1.1
检查关键JSON数据文件的最后修改时间，过期超过阈值推告警。
只检查实际存在的文件，静默=健康。
"""
import json, sys, os, time
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DATA_DIR = os.path.expanduser("~/AppData/Local/hermes/data")

# 实际存在的文件 + 阈值（小时）
WATCH_FILES = {
    "btc_history.jsonl": 24,
    "btc_ref_levels.json": 8,
    "fast_daemon_state.json": 0.5,
    "macro_snapshot.json": 6,
    "polymarket_sentiment.json": 6,
    "tv_dmi_cache.json": 4,
    "sentiment.json": 4,
    "liquidation_pressure.json": 4,
    "stablecoin_snapshot.json": 6,
    "oi_snapshot_BTCUSDT.json": 1,
    "oi_snapshot_ETHUSDT.json": 1,
    "monitor_heartbeat.json": 0.3,
}


def main():
    now = datetime.now(TZ)
    ts = now.strftime("%Y-%m-%d %H:%M BJT")
    
    stale = []
    fresh = []
    
    for fname, threshold_hours in WATCH_FILES.items():
        fp = os.path.join(DATA_DIR, fname)
        if not os.path.exists(fp):
            continue  # 跳过不存在的文件，不告警
        
        mtime = os.path.getmtime(fp)
        age_hours = (time.time() - mtime) / 3600
        
        if age_hours > threshold_hours:
            stale.append((fname, round(age_hours, 1), threshold_hours))
        else:
            fresh.append((fname, round(age_hours, 1)))
    
    if not stale:
        # 干净无异状，完全静默
        return 0

    lines = [f"## 数据过期告警 — {ts}", ""]
    lines.append("| 文件 | 过期时间 | 阈值 | 落后幅度 |")
    lines.append("|---|---|---:|:---|")
    for fname, age, threshold in stale:
        over_pct = round((age - threshold) / threshold * 100)
        lines.append(f"| {fname} | {age:.0f}h | {threshold:.0f}h | 💀 +{over_pct}% |")
    lines.append("")
    lines.append(f"正常文件: {len(fresh)} 个 · 过期文件: {len(stale)} 个")

    output = "\n".join(lines)
    try:
        from alert_dedup import dedup_wrapper
        dedup_wrapper("data_freshness", output, force_seconds=3600)
    except ImportError:
        print(output)
    # no_agent 语义：stdout 非空即推送，非零退出会被 cron 标记为脚本错误
    return 0


if __name__ == "__main__":
    sys.exit(main())
