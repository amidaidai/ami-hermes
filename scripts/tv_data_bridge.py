#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -*- coding: utf-8 -*-
"""
TV数据桥 v1.0 — 行情守望内嵌TV数据采集。

用法:
  python tv_data_bridge.py              # 更新cache，无输出（正常）
  python tv_data_bridge.py --alert      # 等级A/X时输出一行（供警报）

CLI依赖: tools/tradingview-mcp/src/cli/index.js (tv命令)
TV需以CDP模式运行 (端口9222)，否则fallback到已有cache。

采集: tv values + tv data tables + tv data lines + tv quote
缓存: data/tv_dmi_cache.json
"""

import subprocess, json, sys, os
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
ROOT = Path(os.environ.get("HERMES_ROOT", "D:/Hermes agent"))
TV_CLI = ROOT / "tools" / "tradingview-mcp" / "src" / "cli" / "index.js"
CACHE = ROOT / "data" / "tv_dmi_cache.json"

# ═══ 报警阈值 ═══
ALERT_GRADES = {"A多", "A空", "X"}  # 只有这三个等级触发警报


def _tv(*args, timeout=15):
    """调用 tv CLI。返回(stdout, success)。"""
    try:
        cp = subprocess.run(
            ["node", str(TV_CLI)] + list(args),
            cwd=str(ROOT / "tools" / "tradingview-mcp"),
            capture_output=True, text=True, timeout=timeout
        )
        return cp.stdout.strip(), cp.returncode == 0
    except subprocess.TimeoutExpired:
        return "", False
    except FileNotFoundError:
        return "", False


def _tv_json(*args, timeout=15):
    """调用 tv CLI 并解析JSON。"""
    out, ok = _tv(*args, timeout=timeout)
    if not ok or not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    return data if data.get("success", False) else None


def _num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace("\u202f", "").replace(" ", ""))
    except ValueError:
        return None


def tv_available():
    """检查TV是否可连接。"""
    data = _tv_json("status", timeout=5)
    return bool(data and data.get("cdp_connected"))


def read_indicators():
    """读取指标值：VWAP/EMA/CVD/POC/VAH/VAL等。"""
    data = _tv_json("values", timeout=15)
    if not data:
        return {}
    indicators = {}
    for study in data.get("studies", []):
        for key, val in (study.get("values") or {}).items():
            indicators[key.lower().replace(" ", "_")] = val
    return indicators


def read_dmi_table():
    """读取行动格/决策表。"""
    data = _tv_json("data", "tables", "--study-filter", "SVP", timeout=15)
    if not data:
        return {}
    table = {}
    for study in data.get("studies", []):
        for tbl in study.get("tables", []):
            for row in tbl.get("rows", []):
                if "|" in row:
                    key, val = row.split("|", 1)
                    table[key.strip()] = val.strip()
    return table


def read_pine_lines():
    """读取Pine绘制线（关键位）。"""
    data = _tv_json("data", "lines", "--study-filter", "SVP", timeout=15)
    if not data:
        return []
    levels = []
    for study in data.get("studies", []):
        for price in study.get("horizontal_levels", []):
            levels.append({"label": "level", "price": price})
    return levels


def read_quote(symbol="BINANCE:BTCUSDT.P"):
    """读取实时报价。"""
    out, ok = _tv("quote", "--symbol", symbol, timeout=10)
    if not ok:
        return None
    try:
        return float(out.strip().split()[-1])
    except:
        return None


def load_cache():
    """加载已有缓存。"""
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except:
            pass
    return {}


def save_cache(data):
    """写入缓存。"""
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def collect_and_cache(alert_mode=False):
    """
    采集TV数据 → 写缓存。
    
    alert_mode=True: 仅在等级为A多/A空/X时输出一行。
    alert_mode=False: 静默写入，零stdout。
    """
    if not tv_available():
        return None

    indicators = read_indicators()
    dmi = read_dmi_table()
    lines = read_pine_lines()
    quote = read_quote()
    
    grade = dmi.get("等级", dmi.get("grade", "?"))
    old_cache = load_cache()
    old_grade = old_cache.get("grade", "")
    
    # 构建缓存
    # v9.6: 解析POC/VAH/VAL/行动格从已读取数据
    poc = _num(indicators.get("poc_price"))
    vah = _num(indicators.get("vah_price"))
    val = _num(indicators.get("val_price"))
    action_grid = {}
    for lvl in lines:
        lbl = str(lvl.get("label", "")).upper()
        p = lvl.get("price")
        if "POC" in lbl and poc is None: poc = p
        elif "VAH" in lbl and vah is None: vah = p
        elif "VAL" in lbl and val is None: val = p
    # 从decision_table提取行动格
    for k, v in dmi.items():
        kc = str(k).strip()
        if kc in ("结论","方向","进场","止损","目标","核对","磁吸↑","磁吸↓"):
            action_grid[kc] = str(v).strip()
    
    cache = {
        "timestamp": datetime.now(TZ).isoformat(),
        "symbol": "BINANCE:BTCUSDT.P",
        "fresh": True,
        "grade": grade,
        "last_price": quote,
        "decision_table": dmi,
        "indicators": indicators,
        "key_levels": lines,
        "source": "tv_data_bridge",
        "poc": poc,
        "vah": vah,
        "val": val,
        "action_grid": action_grid,
    }
    save_cache(cache)
    
    # 警报模式：仅等级变化(A/X)时输出
    if alert_mode and grade in ALERT_GRADES:
        if grade != old_grade or old_cache.get("source") != "tv_data_bridge":
            treatment = dmi.get("处理", dmi.get("treatment", "?"))
            cvd_state = dmi.get("CVD", dmi.get("cvd", "?"))
            position = dmi.get("位置", dmi.get("position", "?"))
            price_str = f" `{quote}`" if quote else ""
            print(f"🚨 TV DMI: {grade} · {treatment} · CVD{cvd_state} · {position}{price_str}")
    
    return cache


if __name__ == "__main__":
    alert_mode = "--alert" in sys.argv
    result = collect_and_cache(alert_mode=alert_mode)
    if result is None:
        sys.exit(1)
