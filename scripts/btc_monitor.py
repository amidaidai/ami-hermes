#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -*- coding: utf-8 -*-
"""
棠溪 BTC 价格监控 v1 — no_agent 零token · 多区间检测 · 15m趋势 · 冷却防刷

用法 (cron no_agent):
  1m: python scripts/monitor/btc_monitor.py

输出: 命中关键区间 → stdout (投Telegram) · 其他 → 静默
"""

import json, os, sys, time, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import OrderedDict

TZ = timezone(timedelta(hours=8))

# Fixed root — ~/.hermes/scripts/ 运行时也能正确找到 data 目录
PROJECT_ROOT = Path("D:/Hermes agent")
DIR = PROJECT_ROOT / "data"
STATE_FILE = DIR / ".btc_monitor_state.json"
PENDING_FILE = DIR / "btc_signal.json"

COOLDOWN_S = 180  # 同区间3分钟不重复

# ── 监控区间（动态更新 · 按现价调整） ──
LEVELS = OrderedDict([
    ("大底",        {"lo": 62172, "hi": 62472, "prio": 1}),   # 62,272 ±100
    ("前低已破",    {"lo": 62473, "hi": 63370, "prio": 2}),   # 前低63,270已破·逼近大底
    ("VAL折价区",  {"lo": 63371, "hi": 63850, "prio": 3}),   # 价值区下方
    ("VWAP测试区", {"lo": 63851, "hi": 64250, "prio": 2}),   # VWAP附近
    ("VWAP上运行",  {"lo": 64251, "hi": 64507, "prio": 3}),   # VWAP上方·周VWAP下方
    ("周VWAP测试",  {"lo": 64507, "hi": 64750, "prio": 2}),   # 周VWAP阻力
    ("周VWAP上方",  {"lo": 64751, "hi": 99999, "prio": 4}),   # 强势延伸
])

PENDING_FILE = DIR / "btc_signal.json"


def write_pending(zone, price):
    """写触发信号给卡片生成器"""
    signal = {
        "status": "pending",
        "zone": zone,
        "price": price,
        "triggered_at": datetime.now(tz=TZ).isoformat(),
    }
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(signal, f, ensure_ascii=False, indent=2)


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())
    except Exception:
        return None


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(s, f)


def analyze_trend(bars):
    """分析15m K线趋势和量能"""
    if not bars or len(bars) < 4:
        return "数据不足", "?", "?"

    prices = [b["c"] for b in bars[-4:]]
    hi = [b["h"] for b in bars[-4:]]
    lo = [b["l"] for b in bars[-4:]]

    # 趋势判断
    if prices[-1] > prices[0] and hi[-1] > hi[0]:
        trend = "缓升"
    elif prices[-1] < prices[0] and lo[-1] < lo[0]:
        trend = "走弱"
    else:
        trend = "横盘"

    # 量能估算（从K线volume = 笔数简化）
    vols = [b["v"] for b in bars[-4:]]
    avg_v = sum(vols) / len(vols)
    last_v = vols[-1]
    vol_tag = "放量" if last_v > avg_v * 1.5 else ("缩量" if last_v < avg_v * 0.5 else "量平")

    # 动量区域：最近4根K线高低差
    range_4 = max(hi) - min(lo)

    return trend, vol_tag, f"{range_4:.0f}"


def detect_zone(price):
    """返回命中的区间名和分数"""
    for name, cfg in LEVELS.items():
        if cfg["lo"] <= price <= cfg["hi"]:
            return name, cfg["prio"]
    return None, 0


def main():
    # 1. 拉价格
    data = fetch("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
    if not data:
        print("[Monitor] ERR: price API unavailable")
        sys.exit(0)

    price = float(data["price"])
    now = datetime.now(tz=TZ)

    # 2. 判断区间
    zone, prio = detect_zone(price)

    # 3. 防重复
    state = load_state()
    ts = time.time()
    last = state.get(zone, 0) if zone else float("inf")
    if zone and (ts - last) < COOLDOWN_S:
        sys.exit(0)

    # 4. 拉15m K线做趋势分析
    kline_data = fetch(
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=6"
    )
    bars = []
    if kline_data:
        for k in kline_data:
            bars.append({
                "t": datetime.fromtimestamp(k[0] / 1000, tz=TZ).strftime("%H:%M"),
                "o": float(k[1]), "h": float(k[2]),
                "l": float(k[3]), "c": float(k[4]), "v": float(k[5]),
            })

    trend, vol, rng = analyze_trend(bars)

    # 5. 如果命中区间 → 写signal + 输出告警
    if zone:
        state[zone] = ts
        save_state(state)

        # 写pending信号给卡片生成器
        write_pending(zone, price)

        # 日线参考
        daily = fetch(
            "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1"
        )
        dop = float(daily[0][1]) if daily else 0

        vol_emoji = "🔥" if vol == "放量" else ("💧" if vol == "缩量" else "📊")
        lines = [
            f"↓ BTC · {zone} · `{price:.0f}` · {now.strftime('%H:%M')}",
            f"① 区间：{zone}（{LEVELS[zone]['lo']}-{LEVELS[zone]['hi']}）",
            f"② 15m：{trend} · {vol} · 振幅{rng}",
            f"③ 日开 `{dop:.0f}` · 当日 {price-dop:+.0f}",
        ]

        # 区间特定建议
        if zone == "大底":
            lines.insert(2, "   大底62,272周级别 · 守→双底多 64K+ · 破→空 61K")
        elif zone == "前低已破":
            lines.insert(2, f"   前低63,270已破 · 距大底 `{price-62272:.0f}`")
        elif zone == "VWAP测试区":
            lines.insert(2, "   视：回踩确认做多 / 拒绝做空")
        elif zone == "周VWAP测试":
            lines.insert(2, "   周VWAP阻力 · 突破看65K+ · 被拒空回VWAP")

        print("\n".join(lines))
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
