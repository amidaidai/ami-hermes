#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
棠溪 · 宏观过滤器 v1.0
跨资产验证层：DXY/VIX/SPX/美债/黄金 → BTC方向确认

数据源优先级: FinanceKit MCP > Yahoo Finance > 缓存
"""

import json, urllib.request, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
CACHE_FILE = Path.home() / "AppData/Local/hermes/data/macro_snapshot.json"


def _safe_fetch(url: str, timeout: int = 8) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def fetch_macro_snapshot() -> dict:
    """
    获取宏观快照：DXY, VIX, SPX, 美债10Y, 黄金, 白银。
    
    Returns:
        {
            "dxy": float, "vix": float, "spx": float,
            "us10y": float, "gold": float, "silver": float,
            "timestamp": str,
            "risk_sentiment": "risk_on" | "risk_off" | "neutral",
            "btc_correlation": "positive" | "negative" | "neutral",
        }
    """
    snapshot = {
        "dxy": None, "vix": None, "spx": None,
        "us10y": None, "gold": None, "silver": None,
        "timestamp": datetime.now(TZ).isoformat(),
    }
    
    # 并行获取（简化：顺序获取）
    tickers = {
        "dxy": "DX-Y.NYB",
        "vix": "^VIX",
        "spx": "^GSPC",
        "us10y": "^TNX",
        "gold": "GC=F",
        "silver": "SI=F",
    }
    
    for key, ticker in tickers.items():
        data = _safe_fetch(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d",
            timeout=8
        )
        if data:
            try:
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                if meta.get("regularMarketPrice"):
                    snapshot[key] = round(float(meta["regularMarketPrice"]), 4)
            except Exception:
                pass
    
    # ═══ 风险情绪分类 ═══
    vix = snapshot.get("vix")
    dxy = snapshot.get("dxy")
    spx = snapshot.get("spx")
    
    if vix and dxy and spx:
        if vix > 25 and dxy > 105:
            snapshot["risk_sentiment"] = "risk_off"
            snapshot["risk_label"] = "恐慌避险·美元强"
        elif vix > 20 and spx and spx < 5800:
            snapshot["risk_sentiment"] = "risk_off"
            snapshot["risk_label"] = "风险厌恶·股市弱"
        elif vix < 15 and dxy and dxy < 100:
            snapshot["risk_sentiment"] = "risk_on"
            snapshot["risk_label"] = "风险偏好·美元弱"
        elif dxy and dxy < 105:
            snapshot["risk_sentiment"] = "risk_on"
            snapshot["risk_label"] = "中性偏多"
        else:
            snapshot["risk_sentiment"] = "neutral"
            snapshot["risk_label"] = "震荡·无明显方向"
    else:
        snapshot["risk_sentiment"] = "neutral"
        snapshot["risk_label"] = "数据不足"
    
    # ═══ BTC 与风险资产关联 ═══
    if dxy and spx:
        # DXY弱 + SPX强 = 风险偏好 → BTC偏多
        # DXY强 + VIX高 = 避险 → BTC偏空
        if dxy < 100 and vix and vix < 20:
            snapshot["btc_correlation"] = "positive"
        elif dxy > 105 or (vix and vix > 25):
            snapshot["btc_correlation"] = "negative"
        else:
            snapshot["btc_correlation"] = "neutral"
    
    # 缓存
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return snapshot


def macro_filter_bias(snapshot: dict | None = None) -> tuple[str, float, str]:
    """
    宏观层方向过滤。
    
    Returns:
        (bias: "long"|"short"|"neutral", strength: 0-1, label: str)
    """
    if snapshot is None:
        snapshot = fetch_macro_snapshot()
    
    dxy = snapshot.get("dxy")
    vix = snapshot.get("vix")
    sentiment = snapshot.get("risk_sentiment", "neutral")
    label = snapshot.get("risk_label", "未知")
    
    # 默认中性
    bias = "neutral"
    strength = 0.0
    
    if sentiment == "risk_on":
        bias = "long"
        strength = 0.3  # 宏观层权重较低，作为辅助
        label = f"🟢 {label} → 偏多"
    elif sentiment == "risk_off":
        bias = "short"
        strength = 0.3
        label = f"🔴 {label} → 偏空"
    else:
        label = f"⚪ {label} → 中性"
    
    return bias, strength, label


def get_macro_line() -> str:
    """一行宏观摘要，用于分析卡片。"""
    snap = fetch_macro_snapshot()
    parts = []
    if snap.get("dxy"): parts.append(f"DXY `{snap['dxy']:.1f}`")
    if snap.get("vix"): parts.append(f"VIX `{snap['vix']:.1f}`")
    if snap.get("spx"): parts.append(f"SPX `{snap['spx']:.0f}`")
    if snap.get("us10y"): parts.append(f"10Y `{snap['us10y']:.2f}%`")
    parts.append(snap.get("risk_label", ""))
    return " · ".join(parts)


if __name__ == "__main__":
    print("拉取宏观快照...")
    snap = fetch_macro_snapshot()
    bias, strength, label = macro_filter_bias(snap)
    print(f"DXY: {snap.get('dxy')} | VIX: {snap.get('vix')} | SPX: {snap.get('spx')}")
    print(f"情绪: {snap.get('risk_sentiment')}")
    print(f"BTC关联: {snap.get('btc_correlation')}")
    print(f"过滤: {label} (强度{strength})")
