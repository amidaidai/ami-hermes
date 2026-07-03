#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orion 雷达 no_agent 分析卡。

替代高频 LLM cron，避免模型/Grok 额度 403；直接读取 data/orion_radar.json，
输出手机可读的 3 张 Markdown 窄表。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data" / "orion_radar.json"


def fmt_price(v: Any) -> str:
    try:
        f = float(v)
        if f >= 100:
            return f"${f:,.0f}"
        if f >= 1:
            return f"${f:,.3f}"
        return f"${f:.6f}".rstrip("0").rstrip(".")
    except Exception:
        return "—"


def fmt_pct(v: Any) -> str:
    try:
        return f"{float(v):+.2f}%"
    except Exception:
        return "—"


def fmt_usd(v: Any) -> str:
    try:
        f = float(v)
        if f >= 1e9:
            return f"${f/1e9:.2f}B"
        if f >= 1e6:
            return f"${f/1e6:.2f}M"
        if f >= 1e3:
            return f"${f/1e3:.1f}K"
        return f"${f:.0f}"
    except Exception:
        return "—"


def signal(c: dict[str, Any]) -> str:
    oi = c.get("oi_chg")
    chg = c.get("chg_1h")
    funding = c.get("funding")
    parts = []
    try:
        oi_f = float(oi)
        parts.append("🟢OI涨" if oi_f > 2 else "🔴OI降" if oi_f < -2 else "📊OI平")
    except Exception:
        parts.append("📊OI缺")
    try:
        chg_f = float(chg)
        parts.append("🚀价涨" if chg_f > 3 else "💧价跌" if chg_f < -3 else "→价平")
    except Exception:
        parts.append("→价缺")
    try:
        fund_f = float(funding)
        parts.append("🔥负费" if fund_f < -0.005 else "💰正费" if fund_f > 0.005 else "⚪费平")
    except Exception:
        parts.append("⚪费缺")
    return " · ".join(parts[:3])


def main() -> int:
    if not DATA.exists():
        print("○ Orion雷达无数据 · data/orion_radar.json缺失")
        return 0
    d = json.loads(DATA.read_text(encoding="utf-8"))
    candidates = d.get("candidates") or []
    candidates = [c for c in candidates if isinstance(c, dict)]
    candidates.sort(key=lambda c: (float(c.get("confidence") or 0), abs(float(c.get("oi_chg") or 0))), reverse=True)
    top = candidates[:6]
    ts = d.get("ts") or "2026年7月3日10：40"
    high = sum(1 for c in candidates if float(c.get("confidence") or 0) >= 7)
    mid = sum(1 for c in candidates if 4 <= float(c.get("confidence") or 0) < 7)
    print(f"⚡ Orion雷达 · 候选{len(candidates)}个 · 高{high}中{mid} · {ts}")
    print()
    print("表1 · 验证链")
    print("| 来源 | 状态 | 备注 |")
    print("|:----|:----|:----|")
    print(f"| Orion Binance | ✅{len(candidates)}候选 | 高{high}·中{mid} |")
    hl_ok = sum(1 for c in candidates if c.get("hl") or c.get("hyperliquid"))
    cg_ok = sum(1 for c in candidates if c.get("coingecko"))
    print(f"| Hyperliquid | {'✅' if hl_ok else '⏳'}{hl_ok}确认 | 跨所验证 |")
    print(f"| Binance/CG | ✅{cg_ok}深验 | 量价/OI/费率 |")
    print()
    print("表2 · 候选数据")
    print("| 品种 | 数据 | 信号 |")
    print("|:----|:----|:----|")
    for c in top[:4]:
        sym = c.get("symbol", "?")
        data = f"价`{fmt_price(c.get('price'))}`·1h`{fmt_pct(c.get('chg_1h'))}`·OI`{fmt_usd(c.get('oi_usd'))}`"
        sig = f"OI`{fmt_pct(c.get('oi_chg'))}`·费`{fmt_pct((c.get('funding') or 0) * 100)}`·信`{float(c.get('confidence') or 0):.1f}`"
        print(f"| {sym} | {data} | {sig} |")
    print()
    print("表3 · 判断")
    print("| 品种 | 判断 | 动作 |")
    print("|:----|:----|:----|")
    for c in top[:4]:
        sym = c.get("symbol", "?")
        conf = float(c.get("confidence") or 0)
        action = "只看不追" if conf < 7 else "等回踩确认" if float(c.get("chg_1h") or 0) > 0 else "等止跌确认"
        print(f"| {sym} | {signal(c)} | {action} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
