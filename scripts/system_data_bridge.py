#!/usr/bin/env python3
"""System Data Bridge v1.0 — 跨脚本宏观数据桥接
为 auto_card.py 提供资产类别感知的宏观富集。

用法:
    from system_data_bridge import asset_macro_enrich, enrich_engine_data
    macro = asset_macro_enrich("XAUUSD")    # → {asset_class, dxy, event_flag, ...}
    ed = enrich_engine_data("BTCUSDT", ed)  # → 富集后的 engine_data
"""

from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ===== 资产类别识别 =====
def _asset_class(symbol: str) -> str:
    su = symbol.upper()
    if "XAU" in su or "GOLD" in su or "XAG" in su:
        return "gold"
    forex = ["EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"]
    if any(x in su for x in forex) and "USDT" not in su:
        return "forex"
    if su.endswith("USDT") or "BTC" in su or "ETH" in su or "SOL" in su:
        return "crypto"
    # Futures
    futures_codes = {"ES", "CL", "NQ", "GC", "ZC", "ZS", "ZW", "NG", "SI", "HG", "PL", "PA"}
    if su in futures_codes:
        return "futures"
    if su.isalpha() and len(su) <= 5:
        return "stock"
    return "other"


# ===== 宏观缓存 =====
def _read_macro_cache() -> dict:
    """读取 data_gatherer 产出的宏观数据"""
    try:
        macro_file = DATA_DIR / "macro_context.json"
        if macro_file.exists():
            return json.loads(macro_file.read_text(encoding="utf-8"))
    except Exception:
        pass

    # Fallback: try xau_macro_context
    try:
        xau_file = DATA_DIR / "xau_macro_context.json"
        if xau_file.exists():
            return json.loads(xau_file.read_text(encoding="utf-8"))
    except Exception:
        pass

    return {}


def _read_etf_cache() -> dict | None:
    try:
        f = DATA_DIR / "etf_flow_cache.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _read_cot_cache() -> dict | None:
    try:
        f = DATA_DIR / "cot_data.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _read_deribit_cache() -> dict | None:
    try:
        f = DATA_DIR / "deribit_options.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


# ===== 公开接口 =====
def asset_macro_enrich(symbol: str) -> dict:
    """返回资产宏观上下文 dict"""
    ac = _asset_class(symbol)
    macro = _read_macro_cache()

    result = {
        "asset_class": ac,
        "symbol": symbol,
        "dxy": macro.get("dxy") or macro.get("DXY"),
        "us10y": macro.get("us10y") or macro.get("US10Y"),
        "spx": macro.get("spx") or macro.get("SPX"),
        "vix": macro.get("vix") or macro.get("VIX"),
        "event_flag": "",
    }

    # 财报检测（仅股票）
    if ac == "stock":
        now = datetime.now(BJT)
        # 简单启发式：季报月份 (Jan/Apr/Jul/Oct)
        if now.month in (1, 4, 7, 10) and now.day <= 25:
            result["event_flag"] = "财报季"

    # COT 数据附加
    cot = _read_cot_cache()
    if cot and cot.get("markets"):
        result["cot"] = cot["markets"]

    # ETF Flow (仅加密)
    if ac == "crypto":
        etf = _read_etf_cache()
        if etf:
            result["etf_flow"] = etf.get("daily_net", "?")
            result["etf_signal"] = etf.get("signal", "?")

    # Deribit 期权 (仅加密)
    if ac == "crypto":
        deriv = _read_deribit_cache()
        if deriv:
            result["deribit"] = {
                k: {"cp_ratio": v.get("cp_ratio"), "max_pain": v.get("max_pain")}
                for k, v in deriv.items() if k in ("BTC", "ETH")
            }

    return result


def enrich_engine_data(symbol: str, engine_data: dict) -> dict:
    """富集 engine_data — 注入宏观数据"""
    if not engine_data:
        engine_data = {}

    macro = asset_macro_enrich(symbol)

    # Merge macro into engine_data._macro
    engine_data["_macro"] = {
        "dxy": macro.get("dxy"),
        "us10y": macro.get("us10y"),
        "spx": macro.get("spx"),
        "vix": macro.get("vix"),
        "event_flag": macro.get("event_flag", ""),
    }

    # Inject asset-specific data
    ac = macro["asset_class"]
    if ac == "crypto":
        engine_data["etf_flow"] = macro.get("etf_flow")
        engine_data["etf_signal"] = macro.get("etf_signal")
        engine_data["deribit"] = macro.get("deribit")
    elif ac in ("gold", "forex", "stock"):
        engine_data["cot"] = macro.get("cot")

    return engine_data


def snapshot(symbol: str) -> dict:
    """Backward-compatible snapshot() for legacy monitor/review callers.

    Older modules imported ``snapshot`` from this bridge. The bridge now exposes
    richer asset-aware macro context; keep this alias so monitoring errors do
    not break runtime while callers migrate to ``asset_macro_enrich``.
    """
    return asset_macro_enrich(symbol)


# ===== CLI =====
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", default="BTCUSDT")
    args = ap.parse_args()
    result = asset_macro_enrich(args.symbol)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
