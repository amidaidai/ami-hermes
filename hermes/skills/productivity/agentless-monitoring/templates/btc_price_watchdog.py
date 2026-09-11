#!/usr/bin/env python3
"""
零 token BTC 价格看门狗 v4.1 — 全区间覆盖
每1分钟跑一次（no_agent cron），ZONES覆盖所有关心的价格区间，
MID兜底保证不会因为时间片跳跃而漏报。
同区域3分钟cooldown防刷屏。

用前修改 ZONES 字典的区间，修改 COOLDOWN 即可复用。

⚠️ 部署新版本后必须清空旧状态文件：
   rm -f ~/AppData/Local/hermes/data/.watchdog_state.json
"""
import json, os, time, urllib.request, sys
from datetime import datetime, timezone, timedelta

# ─── 配置区 ────────────────────────────────
VERSION = "4.1"         # 版本检测 — 变化时自动重置 cooldown 状态
COOLDOWN = 180          # 同区间3分钟内不重复
TZ = timezone(timedelta(hours=8))

# ⚠️ 必须用 expanduser！不要用 os.path.dirname(__file__)
# cron 环境下 __file__ 解析不可靠
STATE_FILE = os.path.expanduser("~/AppData/Local/hermes/data/.watchdog_state.json")

# 监控区间：name -> (lo, hi, 描述)
# 区间之间的价格也会被 MID 兜底捕获
# 修改后记得清空状态文件！
ZONES = {
    "VWAP_ZONE":   (63930, 64000, "反弹做空区(VWAP/DO附近)"),
    "BAND2_BREAK": (64153, 64200, "Band2上轨突破·看周VWAP"),
    "WVWAP_ZONE":  (64480, 64530, "周VWAP(64,507)附近"),
    "L1":          (63170, 63370, "前低63,270±100"),
    "L2":          (62172, 62372, "大底62,272±100"),
}
# ──────────────────────────────────────────

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_state(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(s, f)

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except:
        return None

def get_klines(limit=6):
    data = fetch(
        f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit={limit}"
    )
    if not data:
        return None
    bars = []
    for k in data:
        bars.append({
            "t": datetime.fromtimestamp(k[0]/1000, tz=TZ).strftime("%H:%M"),
            "o": float(k[1]), "h": float(k[2]),
            "l": float(k[3]), "c": float(k[4]), "v": float(k[5])
        })
    return bars

def trend_summary(bars):
    if not bars or len(bars) < 3:
        return "数据不足"
    c = [b["c"] for b in bars[-3:]]
    h = [b["h"] for b in bars[-3:]]
    l = [b["l"] for b in bars[-3:]]
    if c[-1] > c[0] and h[-1] > h[0]:
        t = "短线上移"
    elif c[-1] < c[0] and l[-1] < l[0]:
        t = "短线走弱"
    else:
        t = "横盘整理"
    avg_v = sum(b["v"] for b in bars) / len(bars)
    lv = bars[-1]["v"]
    vn = "放量" if lv > avg_v * 1.5 else ("缩量" if lv < avg_v * 0.5 else "量平")
    bc = sum(1 for b in bars[-3:] if b["c"] > b["o"])
    return f"{t}·{vn}·{bc}阳{3-bc}阴"

def main():
    data = fetch("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
    if not data:
        sys.exit(0)
    price = float(data["price"])
    now_str = datetime.now(tz=TZ).strftime("%H:%M")

    # 主区间检查
    triggered = None
    label = ""
    for name, (lo, hi, desc) in ZONES.items():
        if lo <= price <= hi:
            triggered = name
            label = desc
            break

    # MID 兜底 — 不在任何区间但仍属关注范围
    if not triggered:
        z = {k: v for k, v in ZONES.items()}
        b2_hi = z["BAND2_BREAK"][1]    # 64200
        wv_lo = z["WVWAP_ZONE"][0]     # 64480
        wv_hi = z["WVWAP_ZONE"][1]     # 64530
        vz_hi = z["VWAP_ZONE"][1]      # 64000
        l1_hi = z["L1"][1]             # 63370

        if price > b2_hi and price < wv_lo:
            triggered = "MID"
            label = "Band2上-周VWAP之间"
        elif price > wv_hi:
            triggered = "ABOVE_WVWAP"
            label = "周VWAP上方"
        elif price > vz_hi and price < z["BAND2_BREAK"][0]:  # 64000~64153
            triggered = "MID_LOW"
            label = "VWAP上方运行"
        elif price > l1_hi and price < vz_hi:  # 63370~63930
            triggered = "VAL_ZONE"
            label = "VAL-折价区运行"
        else:
            sys.exit(0)  # 低于L2或远高于WVWAP，静默

    # 防重复 + 版本检测（新版本自动重置）
    state = load_state()
    now = time.time()
    ver = state.get("_version", "")
    if ver != VERSION:
        state = {"_version": VERSION}  # 版本变了，清空所有 cooldown
    last = state.get(triggered, 0)
    if now - last < COOLDOWN:
        sys.exit(0)
    state[triggered] = now
    state["_version"] = VERSION
    save_state(state)

    # 拉数据
    bars = get_klines()
    trend = trend_summary(bars) if bars else "—"
    daily = fetch("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1")
    dop = float(daily[0][1]) if daily else 0

    lines = [f"↓ BTC 实时 — {now_str} · `{price:.0f}` · {label}"]

    if triggered == "VWAP_ZONE":
        lines.append("① 反弹做空区，等确认被拒再入场")
        lines.append(f"② 15m：{trend}")
        if bars:
            lines.append(f"   最新：`{bars[-3]['c']:.0f}`→`{bars[-2]['c']:.0f}`→`{bars[-1]['c']:.0f}`")
        lines.append("③ 入场区间做空·止损64,250·目标前低")

    elif triggered == "BAND2_BREAK":
        lines.append("① 突破Band2上轨，看向周VWAP")
        lines.append(f"② 15m：{trend}")
        if bars:
            lines.append(f"   最新：`{bars[-3]['c']:.0f}`→`{bars[-2]['c']:.0f}`→`{bars[-1]['c']:.0f}`")
        lines.append("③ 回踩VWAP不破试多·止损63,800·目标64,507")

    elif triggered == "WVWAP_ZONE":
        lines.append("① 周VWAP附近，重要阻力")
        lines.append(f"② 15m：{trend}")
        if bars:
            lines.append(f"   最新：`{bars[-3]['c']:.0f}`→`{bars[-2]['c']:.0f}`→`{bars[-1]['c']:.0f}`")
        lines.append("③ 突破看65K+ / 被拒空回64K")

    elif triggered == "L1":
        lines.append("① 前低附近，破/守决策")
        lines.append(f"② 15m：{trend}")
        if bars:
            lines.append(f"   最新：`{bars[-3]['c']:.0f}`→`{bars[-2]['c']:.0f}`→`{bars[-1]['c']:.0f}`")
        lines.append("③ 守→多弹64K+ / 破→追空看大底")

    elif triggered == "L2":
        lines.append("① 大底·日线级别")
        lines.append(f"② 15m：{trend}")
        if bars:
            lines.append(f"   最新：`{bars[-3]['c']:.0f}`→`{bars[-2]['c']:.0f}`→`{bars[-1]['c']:.0f}`")
        lines.append("③ 守→双底 / 破→趋势转空")

    elif triggered == "MID_LOW":
        lines.append("① VWAP上方运行，多头暂控")
        lines.append(f"② 15m：{trend}")

    elif triggered == "MID":
        lines.append("① Band2上-周VWAP之间")
        lines.append(f"② 15m：{trend}")

    elif triggered == "ABOVE_WVWAP":
        lines.append("① 周VWAP上方")
        lines.append(f"② 15m：{trend}")

    elif triggered == "VAL_ZONE":
        lines.append("① VAL-折价区运行")
        lines.append(f"② 15m：{trend}")
        lines.append("③ 等待前低或VWAP回抽信号")

    lines.append(f"④ 日线今开 `{dop:.0f}` · 当前 {price-dop:+.0f}")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
