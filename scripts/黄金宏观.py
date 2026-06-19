#!/usr/bin/env python3
"""黄金宏观层 v1.0 — DXY/美债/黄金期货代理，给 XAUUSD 监控做背景确认。"""
from __future__ import annotations
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import trading_system as ts

OUT = ts.DATA_DIR / "xau_macro_context.json"

SYMBOLS = {
    "DXY": "DX-Y.NYB",
    "EURUSD": "EURUSD=X",
    "USDJPY": "USDJPY=X",
    "US10Y": "^TNX",
    "US02Y": "^IRX",
    "REAL_RATE_PROXY": "TIP",
    "LONG_BOND_PROXY": "TLT",
    "GOLD_FUT": "GC=F",
    "GOLD_MICRO_FUT": "MGC=F",
    "SILVER_FUT": "SI=F",
    "GOLD_ETF": "GLD",
    "GOLD_MINERS": "GDX",
    "MOVE": "^MOVE",
}


def pct_change(now: float | None, prev: float | None) -> float | None:
    if not isinstance(now, (int, float)) or not isinstance(prev, (int, float)) or prev == 0:
        return None
    return round((now - prev) / prev * 100, 4)


def load_prev() -> dict:
    return ts.read_json(OUT, {})


def bias_from_changes(dxy_chg, ten_chg, gold_chg, tip_chg=None, silver_chg=None, miners_chg=None, move_chg=None) -> tuple[str, list[str]]:
    notes = []
    score = 0
    if isinstance(dxy_chg, (int, float)):
        if dxy_chg > 0.08:
            score -= 1; notes.append("DXY走强压制黄金")
        elif dxy_chg < -0.08:
            score += 1; notes.append("DXY走弱支撑黄金")
        else:
            notes.append("DXY变化温和")
    else:
        notes.append("DXY缺数据")
    if isinstance(ten_chg, (int, float)):
        if ten_chg > 0.5:
            score -= 1; notes.append("美债收益率上行压制黄金")
        elif ten_chg < -0.5:
            score += 1; notes.append("美债收益率回落支撑黄金")
        else:
            notes.append("美债变化温和")
    else:
        notes.append("美债缺数据")
    if isinstance(tip_chg, (int, float)):
        if tip_chg > 0.08:
            score += 1; notes.append("TIP走强，实际利率压力缓和")
        elif tip_chg < -0.08:
            score -= 1; notes.append("TIP走弱，实际利率压力上升")
    if isinstance(gold_chg, (int, float)):
        if gold_chg > 0.15:
            score += 1; notes.append("GC期货同步偏强（Yahoo无现货，用期货代理）")
        elif gold_chg < -0.15:
            score -= 1; notes.append("GC期货同步偏弱（Yahoo无现货，用期货代理）")
        else:
            notes.append("GC期货同步温和（Yahoo期货代理）")
    if isinstance(silver_chg, (int, float)):
        if silver_chg > 0.25:
            notes.append("白银同步偏强，贵金属风险偏好配合")
        elif silver_chg < -0.25:
            notes.append("白银同步偏弱，贵金属风险偏好不配合")
    if isinstance(miners_chg, (int, float)):
        if miners_chg > 0.25:
            notes.append("金矿股同步偏强")
        elif miners_chg < -0.25:
            notes.append("金矿股同步偏弱")
    if isinstance(move_chg, (int, float)):
        if move_chg > 1.0:
            notes.append("MOVE上行，利率波动风险升高")
        elif move_chg < -1.0:
            notes.append("MOVE回落，利率波动压力缓和")
    if score >= 2:
        return "偏多", notes
    if score <= -2:
        return "偏空", notes
    return "中性", notes


def main() -> None:
    ts.ensure_files()
    prev = load_prev().get("prices") or {}
    prices = {}
    changes = {}
    for name, ysym in SYMBOLS.items():
        price = ts.yahoo_chart_price(ysym)
        prices[name] = {"symbol": ysym, "price": price}
        changes[name] = pct_change(price, (prev.get(name) or {}).get("price"))
    bias, notes = bias_from_changes(
        changes.get("DXY"),
        changes.get("US10Y"),
        changes.get("GOLD_FUT"),
        changes.get("REAL_RATE_PROXY"),
        changes.get("SILVER_FUT"),
        changes.get("GOLD_MINERS"),
        changes.get("MOVE"),
    )
    quality = "A" if sum(1 for v in prices.values() if isinstance(v.get("price"), (int, float))) >= 3 else "C"
    row = {
        "schema": "xau_macro_context_v1",
        "time": ts.now_iso(),
        "quality": quality,
        "bias": bias,
        "prices": prices,
        "changes_pct": changes,
        "notes": notes,
        "rule": "DXY和美债上行压制黄金；DXY和收益率回落支撑黄金；TIP/TLT作实际利率与久期代理；金十Quote为XAU现货主价，Yahoo GC/MGC期货作跨市场验证、白银/GLD/GDX作贵金属同步确认；MOVE提示利率波动风险",
    }
    ts.write_json(OUT, row)
    print(json.dumps(row, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
