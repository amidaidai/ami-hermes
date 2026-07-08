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


def _norm_symbol_for_cache(symbol: str) -> str:
    """归一化品种标识，供跨缓存品种门禁比对。"""
    s = str(symbol or "").upper()
    s = s.replace("BINANCE:", "").replace("OANDA:", "").replace("TVC:", "")
    s = s.replace(".P", "")
    return s

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


def read_indicators(symbol=None):
    """读取指标值：VWAP/EMA/CVD/POC/VAH/VAL等。

    symbol 给定时 --symbol 直读目标品种，避免图表停在别的品种污染。
    """
    args = ["values"]
    if symbol:
        args += ["--symbol", symbol]
    data = _tv_json(*args, timeout=15)
    if not data:
        return {}
    indicators = {}
    for study in data.get("studies", []):
        for key, val in (study.get("values") or {}).items():
            indicators[key.lower().replace(" ", "_")] = val
    return indicators


def read_dmi_table(symbol=None):
    """读取行动格/决策表。symbol 给定时 --symbol 直读。"""
    args = ["data", "tables", "--study-filter", "SVP"]
    if symbol:
        args += ["--symbol", symbol]
    data = _tv_json(*args, timeout=15)
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


def read_pine_lines(symbol=None):
    """读取Pine绘制线（关键位）。symbol 给定时 --symbol 直读。"""
    args = ["data", "lines", "--study-filter", "SVP"]
    if symbol:
        args += ["--symbol", symbol]
    data = _tv_json(*args, timeout=15)
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


def read_state_symbol():
    """v9.6 修复 XAU/BTC 缓存交叉污染：读 chart_get_state 真实 symbol。

    旧实现硬编码 symbol=BINANCE:BTCUSDT.P，导致当前图表停在 OANDA:XAUUSD
    时，XAU 的 POC/VAH/VAL 被错标成 BTC symbol 写进 tv_dmi_cache.json，
    auto_card BTC 分支直接采信 → BTC 卡被 XAU 价位污染（P0 复发）。
    """
    data = _tv_json("state", timeout=10)
    if not data:
        return None
    sym = data.get("symbol") or data.get("ticker") or ""
    return sym.strip() or None


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


def collect_and_cache(alert_mode=False, expect_symbol=None):
    """
    采集TV数据 → 写缓存。

    alert_mode=True: 仅在等级为A多/A空/X时输出一行。
    alert_mode=False: 静默写入，零stdout。
    expect_symbol: 期望品种（如 "BINANCE:BTCUSDT.P"）。传入时通过 --symbol
        直读目标品种，彻底绕开"图表当前停在别的品种"导致的交叉污染，
        不再依赖全局图表状态。读不到目标品种有效数据时回退旧缓存并标 stale。
    """
    if not tv_available():
        return None

    # 有期望品种时 --symbol 直读目标品种，避免图表污染
    read_sym = expect_symbol

    indicators = read_indicators(read_sym)
    dmi = read_dmi_table(read_sym)
    lines = read_pine_lines(read_sym)
    quote = read_quote(expect_symbol or "BINANCE:BTCUSDT.P")

    # 品种门禁（兼容无 expect_symbol 的旧路径：仍读全局图表状态比对）
    if not expect_symbol:
        real_symbol = read_state_symbol()
        if real_symbol and _norm_symbol_for_cache(real_symbol) != _norm_symbol_for_cache("BINANCE:BTCUSDT.P"):
            old = load_cache()
            if old:
                old.setdefault("stale", True)
                save_cache(old)
                return old
            return None

    grade = dmi.get("等级", dmi.get("grade", "?"))
    old_cache = load_cache()
    old_grade = old_cache.get("grade", "")

    # 构建缓存
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
    for k, v in dmi.items():
        kc = str(k).strip()
        if kc in ("结论", "方向", "进场", "止损", "目标", "核对", "磁吸↑", "磁吸↓"):
            action_grid[kc] = str(v).strip()

    # 直读失败时回退旧缓存并标 stale，避免下游误用空/错数据
    if not indicators and not dmi and old_cache:
        old_cache.setdefault("stale", True)
        save_cache(old_cache)
        return old_cache

    cache = {
        "timestamp": datetime.now(TZ).isoformat(),
        "symbol": expect_symbol or read_state_symbol() or "UNKNOWN",
        "fresh": True,
        "stale": False,
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
    result = collect_and_cache(alert_mode="--alert" in sys.argv)
    if result is None:
        print("tv cache refresh failed: TradingView CDP unavailable")
        sys.exit(1)
