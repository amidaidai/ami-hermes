#!/usr/bin/env python3
"""COT Collector v1.2 — CFTC 持仓报告采集
每周五更新（数据截至周二收盘）
覆盖：外汇(G10)、金属(黄金/白银/铜/原油)、股指(ES/NQ/Russell/DJIA/Nikkei)
免费 · 无需API Key · 自动缓存

用法:
    python scripts/cot_collector.py                 # 详细摘要
    python scripts/cot_collector.py --full           # 完整JSON
    python scripts/cot_collector.py --line           # 单行摘要（嵌入分析卡）
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from datetime import datetime, timedelta

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import trading_system as ts

CACHE_FILE = ts.DATA_DIR / "cot_data.json"
CACHE_HOURS = 6

# ===== TFF 品种映射（fut+opt 版本，列名含 _All）=====
TFF_WATCH = {
    "EURO FX":            "欧元",
    "JAPANESE YEN":       "日元",
    "BRITISH POUND":      "英镑",
    "AUSTRALIAN DOLLAR":  "澳元",
    "CANADIAN DOLLAR":    "加元",
    "SWISS FRANC":        "瑞郎",
    "E-MINI S&P 500":     "标普迷你",
    "NASDAQ MINI":        "纳指迷你",
    "RUSSELL E-MINI":     "罗素迷你",
}

TFF_CLASSES = {
    "Dealer":            "交易商",
    "Asset_Mgr":         "资管",
    "Lev_Money":         "杠杆基金",
    "Other_Rept":        "其他",
    "NonRept":           "非报告",
}

# ===== Legacy 品种映射（列名含空格，无 _All 后缀）=====
LEGACY_WATCH = {
    "GOLD - COMMODITY":    "黄金",
    "SILVER - COMMODITY":  "白银",
    "COPPER-":             "铜",
    "CRUDE OIL, LIGHT":    "原油",
    "NATURAL GAS":         "天然气",
    "DJIA Consolidated":   "道指",
    "NIKKEI STOCK AVERAGE YEN": "日经",
}

LEGACY_CLASSES = {
    "Noncommercial":  "投机",
    "Commercial":     "商业",
    "Nonreportable":  "非报告",
}


def fetch_cot() -> dict:
    try:
        import cot_reports as cot
    except ImportError:
        return {"error": "pip install cot_reports"}

    year = datetime.now().year
    results = {"source": "CFTC COT", "report_date": "", "markets": {}}

    # 1. TFF fut+opt（外汇/股指最新数据最全）
    try:
        df = cot.cot_year(year=year, cot_report_type="traders_in_financial_futures_futopt")
        if df is not None and not df.empty:
            col_date = "Report_Date_as_YYYY-MM-DD"
            col_mkt = "Market_and_Exchange_Names"
            latest = df[col_date].max()
            results["report_date"] = str(latest) if not results["report_date"] else results["report_date"]
            latest_df = df[df[col_date] == latest]
            for _, row in latest_df.iterrows():
                name = str(row.get(col_mkt, ""))
                for key, label in TFF_WATCH.items():
                    if key in name.upper():
                        entry = _parse_tff(row)
                        entry["label"] = label
                        results["markets"][label] = entry
                        break
    except Exception as e:
        results["error_tff"] = str(e)

    # 2. Legacy fut+opt（金属/能源 + 兜底品种）
    try:
        df2 = cot.cot_year(year=year, cot_report_type="legacy_futopt")
        if df2 is not None and not df2.empty:
            col_date2 = "As of Date in Form YYYY-MM-DD"
            col_mkt2 = "Market and Exchange Names"
            latest2 = df2[col_date2].max()
            if not results["report_date"] or str(latest2) > results["report_date"]:
                results["report_date"] = str(latest2)
            latest_df2 = df2[df2[col_date2] == latest2]
            for _, row in latest_df2.iterrows():
                name = str(row.get(col_mkt2, ""))
                for key, label in LEGACY_WATCH.items():
                    if key.upper() in name.upper():
                        if label not in results["markets"]:
                            entry = _parse_legacy(row)
                            entry["label"] = label
                            results["markets"][label] = entry
                        break
    except Exception as e:
        results["error_legacy"] = str(e)

    return results


def _parse_tff(row) -> dict:
    oi = int(row.get("Open_Interest_All", 0) or 0)
    entry = {"oi": oi, "positions": {}}
    for col_key, label in TFF_CLASSES.items():
        long_val = int(row.get(f"{col_key}_Positions_Long_All", 0) or 0)
        short_val = int(row.get(f"{col_key}_Positions_Short_All", 0) or 0)
        net = long_val - short_val
        pct_l = float(row.get(f"Pct_of_OI_{col_key}_Long_All", 0) or 0)
        pct_s = float(row.get(f"Pct_of_OI_{col_key}_Short_All", 0) or 0)
        chg_l = int(row.get(f"Change_in_{col_key}_Long_All", 0) or 0)
        chg_s = int(row.get(f"Change_in_{col_key}_Short_All", 0) or 0)
        entry["positions"][label] = {
            "long": long_val, "short": short_val, "net": net,
            "pct_long": round(pct_l, 1), "pct_short": round(pct_s, 1),
            "chg_long": chg_l, "chg_short": chg_s,
        }
    return entry


def _parse_legacy(row) -> dict:
    oi = int(row.get("Open Interest (All)", 0) or 0)
    entry = {"oi": oi, "positions": {}}
    for col_key, label in LEGACY_CLASSES.items():
        long_val = int(row.get(f"{col_key} Positions-Long (All)", 0) or 0)
        short_val = int(row.get(f"{col_key} Positions-Short (All)", 0) or 0)
        net = long_val - short_val
        entry["positions"][label] = {"long": long_val, "short": short_val, "net": net}
    return entry


def _signal(positions: dict, label: str) -> str:
    """投机资金方向信号。优先看杠杆基金/TFF，回落看 Legacy 投机"""
    lev = positions.get("杠杆基金", {})
    spec = positions.get("投机", {})
    net = lev.get("net", 0)
    if net == 0:
        net = spec.get("net", 0)
    if net > 0:
        return f"{label}{net:+}多"
    elif net < 0:
        return f"{label}{net:+}空"
    return f"{label}—"


def line_summary(data: dict) -> str:
    if "error" in data and "markets" not in data:
        return f"COT: {data['error']}"
    mkts = data.get("markets", {})
    if not mkts:
        return f"COT({data.get('report_date','?')}): 无匹配品种"
    priority = ["欧元", "日元", "英镑", "黄金", "标普迷你", "纳指迷你"]
    parts = []
    for label in priority:
        if label in mkts:
            parts.append(_signal(mkts[label].get("positions", {}), label))
    date = data.get("report_date", "?")
    return f"COT({date}): " + " · ".join(parts[:8]) if parts else f"COT({date}): N/A"


def full_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _load_cache():
    if not CACHE_FILE.exists():
        return None
    try:
        cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        ts_str = cached.get("_fetched_at", "")
        if ts_str and datetime.now() - datetime.fromisoformat(ts_str) < timedelta(hours=CACHE_HOURS):
            return cached
    except Exception:
        pass
    return None


def _save_cache(data: dict):
    data["_fetched_at"] = datetime.now().isoformat()
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="CFTC COT 报告采集")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--line", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not args.force:
        cached = _load_cache()
        if cached:
            if args.full:
                print(full_json(cached))
            else:
                print(line_summary(cached))
            sys.exit(0)

    print("拉取 CFTC COT...", file=sys.stderr)
    data = fetch_cot()
    _save_cache(data)

    if args.full:
        print(full_json(data))
    elif args.line:
        print(line_summary(data))
    else:
        print(line_summary(data))
        print()
        for label, entry in data.get("markets", {}).items():
            pos = entry.get("positions", {})
            if pos:
                oi = entry.get("oi", 0)
                print(f"\n{label} [总OI: {oi:,}]:")
                for trader, p in pos.items():
                    print(f"  {trader}: 多{p['long']:,}  空{p['short']:,}  净{p['net']:+}")
