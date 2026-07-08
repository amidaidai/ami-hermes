#!/usr/bin/env python3
"""
棠溪 · BTC结构位轻量读取 btc_levels_read.py v1.0

只读取 TV 缓存 JSON（tv_dmi_cache.json / tv_live.json / btc_ref_levels.json），
不触发任何刷新/推送。供作战室融合报告复用结构位，给出具体入场/止损/目标价位。

优先级：tv_dmi_cache.json(最新鲜) → tv_live.json → btc_ref_levels.json
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Optional

DATA = Path("D:/Hermes agent/data")


def _read(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_levels() -> dict:
    """返回 {poc,vwap,val,vah,do,w_vwap,spot,age_min,source}。"""
    candidates = [
        DATA / "tv_dmi_cache.json",
        DATA / "tv_live.json",
        DATA / "btc_ref_levels.json",
    ]
    best = None
    best_age = 1e9
    best_src = "?"
    for p in candidates:
        d = _read(p)
        if not d:
            continue
        # 需要至少含 vwap/val/vah/poc 才算有效
        if not all(k in d for k in ("vwap", "val", "vah", "poc")):
            continue
        age = (time.time() - p.stat().st_mtime) / 60
        if age < best_age:
            best_age = age
            best = d
            best_src = p.name
    if not best:
        return {"error": "no valid TV cache", "age_min": None, "source": "?"}

    # 现价优先：try fetch spot via Binance public (轻量, 不触发推送)
    spot = None
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            headers={"User-Agent": "Hermes/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            spot = float(json.loads(r.read()).get("price", 0))
    except Exception:
        spot = None

    return {
        "poc": float(best.get("poc")),
        "vwap": float(best.get("vwap")),
        "val": float(best.get("val")),
        "vah": float(best.get("vah")),
        "do": float(best.get("do")) if best.get("do") else None,
        "w_vwap": float(best.get("w_vwap")) if best.get("w_vwap") else None,
        "spot": spot,
        "age_min": round(best_age, 1),
        "source": best_src,
    }


if __name__ == "__main__":
    import pprint
    pprint.pprint(read_levels())
