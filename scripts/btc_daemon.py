#!/usr/bin/env python3
"""
棠溪 BTC 实时守护 v2 — 静默轮询 + 高置信度推送
核心原则：DMI只是参考，多因子评分才是决策。只有很确定才推送。

变化：
- 不再每次换区间就推（太频繁）
- 每60秒跑完整多因子评分（DMI引擎 + VWAP + CVD + EMA + 市场体制）
- 只有评分≥8/10才推完整分析卡
- 同方向推送冷却30分钟
"""

import json, os, sys, time, asyncio, subprocess, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import OrderedDict
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("D:/Hermes agent")
DATA_DIR = ROOT / "data"
DMI_SCRIPT = ROOT / "scripts/dmi_decision.py"
TV_SERVER = ROOT / "tools/tradingview-mcp/src/server.js"
TV_CLI = ROOT / "tools/tradingview-mcp/src/cli/index.js"
HERMES_VENV = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))

HEARTBEAT_FILE = DATA_DIR / ".btc_daemon_heartbeat.json"
SIGNAL_FILE = DATA_DIR / "btc_signal.json"
STATE_FILE = DATA_DIR / ".btc_daemon_state.json"
PID_FILE = DATA_DIR / ".btc_daemon.pid"

BINANCE_API = "https://api.binance.com"
TARGET = "telegram:-1003733144325:386"
TZ = timezone(timedelta(hours=8))
POLL_S = 15
DEEP_INTERVAL = 60
COOLDOWN_MINUTES = 30

# ── 7区间（对齐 TV 指标 2026-06-28） ──
# 基准：VWAP=60028 VAL=59920 VAH=60254 POC=60147 DO=60000 W_VWAP=61075 近期低点=59714
# 自动更新：读 data/btc_ref_levels.json（由 tv_levels_collector.py + cron 维护）
LEVELS = OrderedDict([
    ("大底",       {"lo": 59500, "hi": 59760, "prio": 1}),   # 近期低点59714±150
    ("前低已破",   {"lo": 59761, "hi": 59920, "prio": 2}),   # 低点到VAL
    ("VAL折价区", {"lo": 59921, "hi": 60028, "prio": 3}),   # VAL~VWAP
    ("VWAP测试区",{"lo": 60029, "hi": 60150, "prio": 2}),   # VWAP~VAH中途
    ("VWAP上运行", {"lo": 60151, "hi": 60254, "prio": 3}),   # VAH测试
    ("周VWAP测试", {"lo": 61000, "hi": 61150, "prio": 2}),   # 周VWAP±75
    ("周VWAP上方", {"lo": 61151, "hi": 99999, "prio": 4}),
])

ZONE_WEIGHT = {"大底": 3, "VWAP测试区": 2, "周VWAP测试": 2, "前低已破": 1, "VAL折价区": 1, "VWAP上运行": 1, "周VWAP上方": 1}

# ── 热读 TV 关键位（支持自动更新，无需重启 daemon） ──
REF_FILE = DATA_DIR / "btc_ref_levels.json"
_last_ref_mtime = 0

def load_dynamic_levels():
    """读 btc_ref_levels.json → 动态重算7区间。文件没变则跳过。"""
    global _last_ref_mtime
    try:
        mtime = REF_FILE.stat().st_mtime
        if mtime <= _last_ref_mtime:
            return  # 没变化
        _last_ref_mtime = mtime
        with open(REF_FILE) as f:
            ref = json.load(f)
        vwap = ref.get("vwap", 60028)
        val = ref.get("val", 59920)
        vah = ref.get("vah", 60254)
        w_vwap = ref.get("w_vwap", 61075)
        r_low = ref.get("recent_low", 59714)
        # 重算区间
        global LEVELS
        LEVELS = OrderedDict([
            ("大底",       {"lo": int(r_low - 250), "hi": int(r_low + 50), "prio": 1}),
            ("前低已破",   {"lo": int(r_low + 51),  "hi": int(val),        "prio": 2}),
            ("VAL折价区", {"lo": int(val + 1),      "hi": int(vwap),       "prio": 3}),
            ("VWAP测试区",{"lo": int(vwap + 1),     "hi": int(vwap + 120), "prio": 2}),
            ("VWAP上运行", {"lo": int(vwap + 121),   "hi": int(vah),        "prio": 3}),
            ("周VWAP测试", {"lo": int(w_vwap - 75),  "hi": int(w_vwap + 75), "prio": 2}),
            ("周VWAP上方", {"lo": int(w_vwap + 76),  "hi": 99999,           "prio": 4}),
        ])
        log(f"Levels reloaded: VWAP={vwap} VAL={val} VAH={vah} W_VWAP={w_vwap} low={r_low}")
    except Exception as e:
        log(f"Levels reload failed: {e}")
def now_ts(): return datetime.now(tz=TZ)
def log(m):
    safe = m.encode("ascii", "replace").decode("ascii")
    sys.stderr.write(f"[daemon] {safe}\n")

def fetch(url):
    try:
        r = urllib.request.urlopen(url, timeout=8)
        return json.loads(r.read().decode())
    except: return None

def get_price():
    d = fetch(f"{BINANCE_API}/api/v3/ticker/price?symbol=BTCUSDT")
    return float(d["price"]) if d and "price" in d else None

def get_klines(limit=30):
    d = fetch(f"{BINANCE_API}/api/v3/klines?symbol=BTCUSDT&interval=15m&limit={limit}")
    if d:
        return [{"t":k[0],"o":float(k[1]),"h":float(k[2]),"l":float(k[3]),"c":float(k[4]),"v":float(k[5])} for k in d]
    return None

def detect_zone(price):
    for name, cfg in LEVELS.items():
        if cfg["lo"] <= price <= cfg["hi"]:
            return name
    return None

def fmt_price(v):
    return f"{v:,.0f}" if v else "?"

# ── 多因子评分（轻量版·15秒轮询用） ──
def score_opportunity(price, zone, bars):
    """
    多因子评分 0-10
    因子：区间重要性 + 15m趋势方向 + 量能 + EMA排列
    仅评分≥8才推送
    """
    score = 0
    
    # 1. 区间权重 (max 3)
    score += ZONE_WEIGHT.get(zone, 0)
    
    if not bars or len(bars) < 5:
        return score
    
    closes = [b["c"] for b in bars[-5:]]
    
    # 2. 趋势方向 (max 2) — 价格在区间内且趋势有利
    trending_down = closes[-1] < closes[0]
    score += 2 if trending_down and zone in ("大底", "前低已破", "VAL折价区") else (1 if trending_down else 0)
    
    # 3. 量能 (max 2) — 放量下跌更可信
    vol = [b["v"] for b in bars[-5:]]
    avg_v = sum(vol) / len(vol)
    last_v = vol[-1]
    if last_v > avg_v * 1.5 and trending_down:
        score += 2  # 放量下跌 = 确认下跌
    elif last_v > avg_v * 1.2:
        score += 1
    
    # 4. 波动率 (max 1) — 大底区波动大 = 博弈激烈
    rng = [b["h"] - b["l"] for b in bars[-3:]]
    avg_rng = sum(rng) / len(rng)
    if zone in ("大底", "VWAP测试区") and avg_rng > 300:
        score += 1  # 大波动 = 关键位博弈
    
    # 5. 距离关键位 (max 2) — 靠近大底=重要
    if zone == "大底":
        dist_to_bottom = price - 59500
        if dist_to_bottom < 100:
            score += 2  # 逼近大底 = 最高优先级
        elif dist_to_bottom < 200:
            score += 1
    
    return min(score, 10)


# ── 多因子评分（深度版·TV MCP数据） ──
def run_deep_scoring():
    """
    使用Python DMI引擎 + F&G 做深度评分
    返回 {score, direction, reason} 或 None
    """
    try:
        # Run DMI engine as subprocess
        script_path = str(DMI_SCRIPT)
        r = subprocess.run([sys.executable, script_path], capture_output=True, text=True, timeout=30)
        dmi_result = json.loads(r.stdout) if r.stdout else {}
    except Exception as e:
        log(f"DMI engine: {e}")
        dmi_result = {}

    # Get F&G
    fng = None
    try:
        r = urllib.request.urlopen("https://api.alternative.me/fng/?limit=1", timeout=5)
        d = json.loads(r.read())
        fng = int(d["data"][0]["value"])
    except: pass

    # Score from DMI engine
    trend_long = dmi_result.get("trend_long", 0)
    trend_short = dmi_result.get("trend_short", 0)
    grade = dmi_result.get("grade", "C")
    is_x = grade == "X"
    cvd_state = dmi_result.get("cvd_state", "")
    near_key = dmi_result.get("near_key_level", False)

    # Multi-factor confidence score (not just TV grade)
    confidence = 0
    reasons = []
    
    # Trend score (max 3)
    max_trend = max(trend_long, trend_short)
    if max_trend >= 8: confidence += 3
    elif max_trend >= 6: confidence += 2
    elif max_trend >= 4: confidence += 1
    
    # CVD confirmation (max 2)
    if "顺多" in cvd_state or "顺空" in cvd_state: confidence += 2
    elif "买盘" in cvd_state or "卖盘" in cvd_state: confidence += 1
    
    # Near key level (max 2)
    if near_key: confidence += 2
    
    # Not overheated (max 1)
    if not is_x: confidence += 1
    
    # F&G extreme (max 2) — extreme fear/ greed = high conviction
    if fng is not None:
        if fng < 25: confidence += 2; reasons.append("极端恐慌")
        elif fng < 40: confidence += 1
    
    direction = "空" if trend_short > trend_long else "多" if trend_long > trend_short else "观望"
    
    return {
        "score": confidence,
        "direction": direction,
        "grade": grade,
        "cvd_state": cvd_state,
        "trend_long": trend_long,
        "trend_short": trend_short,
        "near_key": near_key,
        "fng": fng,
    }


# ── 推送 ──
def push_tg(text):
    try:
        safe_text = text.replace("'", "'\\''").replace("`", "\\`")[:3800]
        script_path = str(ROOT / "scripts")
        code = f"""import sys
sys.path.insert(0, r'{script_path}')
from telegram_direct import send_telegram_direct
ok, rs = send_telegram_direct('{TARGET}', '''{safe_text}''')
print('OK' if ok else 'FAIL:' + str(rs))
"""
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
        return r.stdout.strip()
    except Exception as e:
        return f"FAIL:{e}"


# ── 信号文件 ──
def write_signal(zone, price):
    s = {"status": "pending", "zone": zone, "price": price, "triggered_at": now_ts().isoformat()}
    with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def read_signal():
    try:
        with open(SIGNAL_FILE) as f:
            return json.load(f)
    except: return None

def mark_done(signal):
    if signal:
        signal["status"] = "completed"
        signal["completed_at"] = now_ts().isoformat()
        with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(signal, f, ensure_ascii=False, indent=2)


# ── 心跳 ──
def write_heartbeat(zone="", score=0):
    hb = {"ts": now_ts().isoformat(), "zone": zone, "score": score, "pid": os.getpid()}
    with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
        json.dump(hb, f, ensure_ascii=False)

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"last_zone": None, "last_push_dir": None, "last_push_ts": 0}

def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


# ── TV MCP 深度分析（调用card_gen） ──
def run_tv_analysis():
    try:
        cg = ROOT / "scripts/btc_card_gen.py"
        r = subprocess.run([sys.executable, str(cg)], capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        log(f"card gen: rc={r.returncode}")
        return None
    except Exception as e:
        log(f"card gen fail: {e}")
        return None


# ── 主循环 ──
def main_loop():
    state = load_state()
    tick = 0
    alert_cooldown_until = 0  # 冷却结束时间戳

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    log(f"Daemon v2 started PID={os.getpid()}")

    while True:
        tick += 1
        now = time.time()
        ts = now_ts()

        # ── 热读 TV 关键位（每次循环检查 JSON 是否更新） ──
        load_dynamic_levels()

        price = get_price()
        if price is None:
            time.sleep(POLL_S)
            continue

        zone = detect_zone(price)
        bars = get_klines(15)

        # ── 15秒轮询: 更新状态（静默） ──
        score = score_opportunity(price, zone, bars) if (zone and bars) else 0
        write_heartbeat(zone or "", score)
        state["last_zone"] = zone
        state["last_price"] = price

        # ── 每60秒: 深度评分 + 推送 ──
        if tick % max(1, DEEP_INTERVAL // POLL_S) == 0:
            deep = run_deep_scoring()
            if deep:
                conf_score = deep["score"]
                direction = deep["direction"]
                grade = deep["grade"]
                log(f"Deep score={conf_score}/10 dir={direction} grade={grade} cvd={deep['cvd_state']}")

                # 决策：只有评分≥8 且 不在冷却期 才推送
                can_push = conf_score >= 8
                same_dir_cooldown = False
                
                if can_push:
                    last_dir = state.get("last_push_dir")
                    last_ts = state.get("last_push_ts", 0)
                    # 同方向冷却30分钟
                    if direction == last_dir and (now - last_ts) < COOLDOWN_MINUTES * 60:
                        same_dir_cooldown = True
                        log(f"Same dir {direction} in cooldown, skip")
                
                if can_push and not same_dir_cooldown:
                    # 写signal → 触发card_gen → 出完整卡推送
                    write_signal(zone, price)
                    log(f"High conf score={conf_score}: writing signal, triggering card gen...")
                    
                    card = run_tv_analysis()
                    if card:
                        push_result = push_tg(card)
                        log(f"Push: {push_result}")
                        state["last_push_dir"] = direction
                        state["last_push_ts"] = now
                        state["last_push_zone"] = zone
                        state["last_push_score"] = conf_score

        save_state(state)
        time.sleep(POLL_S)


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        log("Shutdown")
        if PID_FILE.exists():
            PID_FILE.unlink()
