#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宏观+Polymarket 缓存刷新 — no_agent cron wrapper · 静默成功"""
import sys, json, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hermes" / "scripts"))

errors = []

# Macro
try:
    from macro_filter import fetch_macro_snapshot
    snap = fetch_macro_snapshot()
    if not snap.get("dxy"):
        errors.append("DXY缺失")
except Exception as e:
    errors.append(f"宏观: {e}")

# Poly
try:
    from polymarket_bridge import polymarket_sentiment_score
    poly = polymarket_sentiment_score()
    if not poly.get("markets"):
        errors.append("Poly无市场")
except Exception as e:
    errors.append(f"Poly: {e}")

# Event calendar
try:
    from event_ban_live import refresh_event_cache
    if not refresh_event_cache():
        errors.append("日历刷新失败")
except Exception as e:
    errors.append(f"日历: {e}")

if errors:
    safe = "; ".join(errors).encode("ascii", "replace").decode("ascii")
    print(f"ERROR: {safe}")
    sys.exit(1)
# 成功静默
