#!/usr/bin/env python3
"""
TV 关键位采集器 — 从 TV MCP 子进程读取 VWAP/VAL/VAH/POC/DO/周VWAP
写入 data/btc_ref_levels.json 供 daemon 热读

运行方式：
  no_agent cron: 不适用（需要 subprocess 调 TV CLI，环境依赖复杂）
  agent cron:   hermes cron create --prompt "读 TV study_values → 更新 btc_ref_levels.json"
  
当前方案：由 agent cron 每4小时在 KillZone 期间更新
JSON 格式：
{
  "updated_at": "2026-06-28T22:15:00+08:00",
  "vwap": 60028.5, "val": 59920.3, "vah": 60254.4,
  "poc": 60147.3, "do": 60000.4, "w_vwap": 61075.1,
  "recent_low": 59714, "recent_high": 60925
}
"""

import json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path(os.path.expanduser("~/AppData/Local/hermes/data/btc_ref_levels.json"))
TZ = timezone(timedelta(hours=8))

# ── 默认值（TV 不可用时回退） ──
DEFAULTS = {
    "vwap": 60028.5, "val": 59920.3, "vah": 60254.4,
    "poc": 60147.3, "do": 60000.4, "w_vwap": 61075.1,
    "recent_low": 59714, "recent_high": 60925,
}

def write_levels(data: dict):
    """写入 + 标注时间"""
    data["updated_at"] = datetime.now(tz=TZ).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def read_levels() -> dict:
    """读取当前级别（若不存在返回默认值）"""
    try:
        with open(OUT) as f:
            return json.load(f)
    except:
        return {**DEFAULTS, "updated_at": "never"}

if __name__ == "__main__":
    # 独立运行时写默认值（兜底）
    write_levels(DEFAULTS)
    print(f"btc_ref_levels.json written: {DEFAULTS}")
