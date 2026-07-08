#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宏观+Polymarket 缓存刷新 — no_agent cron wrapper · 推 TG 真表格
v9.8: 成功也推宏观面板（DXY/VIX/SPX/美债/黄金/白银 + 风险情绪 + Poly情绪），失败推错误表。
"""
import sys, json, os
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hermes" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

errors = []
snap = {}
poly = {}

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

import datetime
TZ = datetime.timezone(datetime.timedelta(hours=8))
ts = datetime.datetime.now(TZ).strftime("%Y年%m月%d日%H：%M")

target = "telegram:-1003733144325:846"
def _push(text):
    try:
        from telegram_reliable import push_tg_rich
        push_tg_rich(target, text)
    except Exception as _te:
        print(f"⚠ 宏观Poly RichMarkdown推送失败: {_te}", file=sys.stderr)

if errors:
    safe = "; ".join(str(e) for e in errors)
    print(f"ERROR: {safe}")
    _push(f"⚠ 宏观Poly刷新异常 · {ts}\n\n| 模块 | 状态 |\n|:----|:----|\n" + "\n".join(f"| {e.split(':')[0]} | ❌ {e} |" for e in errors))
    sys.exit(1)

# success: 推宏观面板
lines = [f"🌐 宏观+Poly面板 · {ts}", ""]
lines.append("| 指标 | 数值 | 信号 |")
lines.append("|:----|:----:|:----|")
def _fmt(v, suffix=""):
    return f"{v:.2f}{suffix}" if isinstance(v, (int, float)) else "—"
lines.append(f"| DXY美元指数 | {_fmt(snap.get('dxy'))} | {snap.get('risk_label','—')} |")
lines.append(f"| VIX恐慌指数 | {_fmt(snap.get('vix'))} | — |")
lines.append(f"| SPX标普 | {_fmt(snap.get('spx'))} | — |")
lines.append(f"| 美债10Y | {_fmt(snap.get('us10y'))}% | — |")
lines.append(f"| 黄金 | {_fmt(snap.get('gold'))} | — |")
lines.append(f"| 白银 | {_fmt(snap.get('silver'))} | — |")
lines.append("")
lines.append(f"风险情绪: {snap.get('risk_label','—')}")
poly_bias = poly.get("label", "—")
lines.append(f"Polymarket: {poly_bias}")
# 决策：综合宏观与Poly
risk = snap.get("risk_sentiment", "")
if risk == "risk_off":
    lines.append("📉 宏观避险→BTC承压，减仓/观望为主")
elif risk == "risk_on":
    lines.append("📈 宏观风险偏好→BTC偏多环境")
else:
    lines.append("○ 宏观中性，按结构交易")

output = "\n".join(lines)
print(output)
_push(output)
# success silent to cron (no stdout needed but we printed for log)
