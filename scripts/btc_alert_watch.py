#!/usr/bin/env python3
"""BTC价位提醒 v3 — 动态关键位 · 中文告警 · stdout静默"""
import os, sys, json, urllib.request
from datetime import datetime, timezone, timedelta


def emit_error(text):
    """仅故障时输出ASCII，避免no_agent cron把中文stdout回传成乱码。"""
    safe = text.encode("ascii", "replace").decode("ascii")
    sys.stdout.write(safe.rstrip() + "\n")
    sys.stdout.flush()

TZ = timezone(timedelta(hours=8))
DIR = os.path.expanduser("~/AppData/Local/hermes/data")
TV_DATA = os.path.join(DIR, "btc_tv_data.json")
LATEST = os.path.join(DIR, "btc_latest.json")
STATE = os.path.join(DIR, "btc_alert_state.json")

def build_watch_levels(ctx):
    """从TV缓存生成动态提醒位，只盯真正有交易意义的价位。"""
    return {
        "VAH_accept": {"level": ctx["vah"], "thresh": 18, "bias": "↑做多", "desc": "站上VAH并接受，偏多延续"},
        "VAH_reject": {"level": ctx["vah"], "thresh": 18, "bias": "○等待", "desc": "VAH附近观察接受/拒绝"},
        "VWAP_reclaim": {"level": ctx["vwap"], "thresh": 18, "bias": "↑做多", "desc": "站回VWAP，修复短线结构"},
        "VWAP_lost": {"level": ctx["vwap"], "thresh": 18, "bias": "↓做空", "desc": "跌回VWAP下方，反弹失败"},
        "VAL_break": {"level": ctx["val"], "thresh": 18, "bias": "↓做空", "desc": "破VAL，空头加速"},
        "B2_low": {"level": ctx["band2_low"], "thresh": 15, "bias": "↓做空", "desc": "跌破-B2，波动扩张"},
    }


def _now():
    return datetime.now(TZ).strftime("%H:%M")

def _read_json(fp):
    try:
        with open(fp, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _write_state(state):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def get_price():
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        req = urllib.request.Request(url, headers={"User-Agent": "D/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return float(json.loads(resp.read())["price"])
    except Exception:
        return None

def _safe_float(val, default=0.0):
    """安全转浮点，防None/null。"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def read_tv_cache():
    tv = _read_json(TV_DATA)
    latest = _read_json(LATEST)
    return {
        "vwap": _safe_float(tv.get("vwap")),
        "vah": _safe_float(tv.get("vah")),
        "val": _safe_float(tv.get("val")),
        "poc": _safe_float(tv.get("poc")),
        "band1_high": _safe_float(tv.get("band1_high")),
        "band1_low": _safe_float(tv.get("band1_low")),
        "band2_high": _safe_float(tv.get("band2_high")),
        "band2_low": _safe_float(tv.get("band2_low")),
        "cvd": _safe_float(tv.get("cvd")),
        "cvd_slope": _safe_float(tv.get("cvd_slope")),
        "ema9": _safe_float(tv.get("ema9")),
        "ema21": _safe_float(tv.get("ema21")),
        "price": _safe_float(latest.get("price")),
        "ls_ratio": _safe_float(latest.get("ls_ratio"), 1.0),
        "funding": _safe_float(latest.get("funding")),
        "taker": _safe_float(latest.get("taker_ratio"), 1.0),
    }

def choose_direction(name, price, ctx):
    above_vwap = price > ctx["vwap"]
    above_poc = price > ctx["poc"]
    above_vah = price > ctx["vah"]
    cvd_bad = ctx["cvd"] < 0 and ctx["cvd_slope"] < 0
    taker_buy = ctx["taker"] > 1.05

    if name == "VAH_accept" and above_vah and taker_buy:
        return "↑做多", "VAH接受 + Taker买方增强，偏多延续"
    if name == "VAH_reject" and not above_vah and cvd_bad:
        return "↓做空", "VAH拒绝 + CVD顺空，防假突破回落"
    if name == "VWAP_reclaim" and above_vwap and above_poc:
        return "↑做多", "站回VWAP/POC，短线结构修复"
    if name == "VWAP_lost" and not above_vwap and cvd_bad:
        return "↓做空", "跌回VWAP下方，CVD继续走弱"
    if name in ("VAL_break", "B2_low"):
        return "↓做空", "破下方关键位，空头波动扩张"
    if above_vwap and taker_buy:
        return "↑做多等待", "VWAP上方但需要收盘确认"
    if cvd_bad:
        return "↓做空等待", "CVD负斜率，等关键位失守"
    return "○等待", "信号不完整，先看收盘确认"


def analyze(name, info, price, ctx):
    bias, reason = choose_direction(name, price, ctx)
    level = info["level"]
    lines = []
    lines.append(f"{bias} BTC价位提醒 · {_now()}")
    lines.append(f"触发：{info['desc']}")
    lines.append(f"现价`{price:,.0f}` · 关键位`{level:,.0f}` · 距离`${abs(price-level):.0f}`")
    lines.append(f"判断：{reason}")
    lines.append(f"VWAP`{ctx['vwap']:.0f}` · POC`{ctx['poc']:.0f}` · VAH`{ctx['vah']:.0f}` · VAL`{ctx['val']:.0f}`")
    lines.append(f"CVD`{ctx['cvd']:+.0f}` · 斜率`{ctx['cvd_slope']:+.0f}` · 多空比`{ctx['ls_ratio']:.2f}` · Taker`{ctx['taker']:.2f}`")

    if "做多" in bias:
        lines.append(f"★最值得看：15m收在`{ctx['vah']:.0f}`上方且CVD斜率止跌，才追多。")
        lines.append(f"失效：跌回VWAP`{ctx['vwap']:.0f}`下方。")
    elif "做空" in bias:
        lines.append(f"★最值得看：15m收回`{ctx['vwap']:.0f}`下方且CVD继续负，才顺空。")
        lines.append(f"失效：重新站回VAH`{ctx['vah']:.0f}`上方。")
    else:
        lines.append("★最值得看：等收盘确认，不预入场。")

    return "\n".join(lines)

def main():
    now = _now()
    state = _read_json(STATE)
    triggered = state.get("triggered", {})

    price = get_price()
    if not price:
        emit_error(f"[{now}] price fetch failed")
        return

    ctx = read_tv_cache()
    watch_levels = build_watch_levels(ctx)
    alerts = []

    for name, info in watch_levels.items():
        lv = info["level"]
        if lv <= 0:
            continue
        dist = abs(price - lv)
        if dist <= info["thresh"]:
            last = triggered.get(name)
            if last and ":" in str(last):
                lh, lm = map(int, str(last).split(":"))
                nh, nm = map(int, now.split(":"))
                if (nh - lh) * 60 + (nm - lm) < 15:
                    continue
            alert = analyze(name, info, price, ctx)
            alerts.append(alert)
            triggered[name] = now

    if alerts:
        # 告警内容走 pending 文件 (UTF-8安全)
        import os
        PENDING = os.path.join(DIR, "btc_pending.txt")
        for a in alerts:
            with open(PENDING, "a", encoding="utf-8") as f:
                f.write(f"{a}\n---\n")
        _write_state({"triggered": triggered, "last_check": now})
    else:
        # 无事件时保持静默，避免no_agent cron把心跳消息回传到Telegram。
        _write_state({"triggered": triggered, "last_check": now})

if __name__ == "__main__":
    main()
