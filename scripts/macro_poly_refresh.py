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
        errors.append("DXY missing")
except Exception as e:
    errors.append(f"macro: {e}")

# Poly
try:
    from polymarket_bridge import polymarket_sentiment_score
    poly = polymarket_sentiment_score()
    if not poly.get("markets"):
        errors.append("Poly no markets")
except Exception as e:
    errors.append(f"poly: {e}")

# Event calendar — False means no events, not an error
try:
    from event_ban_live import refresh_event_cache
    refresh_event_cache()
except Exception as e:
    errors.append(f"event: {e}")

if errors:
    safe = "; ".join(str(e) for e in errors)
    print(f"ERROR: {safe}")
    sys.exit(1)
# success silent
