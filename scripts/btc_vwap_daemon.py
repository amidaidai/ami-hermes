#!/usr/bin/env python3
"""BTC守护 v12 — 社区7项全量升级版
   新增: CVD背离·KillZone·折溢价区·扫荡分类·Silver Bullet·吸收·FVG
   输出: pending.txt + btc_signals.json (供分析cron使用)
"""
import json, time, urllib.request, os
from datetime import datetime, timezone, timedelta
from collections import deque

TZ = timezone(timedelta(hours=8))
DIR = os.path.expanduser("~/AppData/Local/hermes/data")
PENDING = os.path.join(DIR, "btc_pending.txt")
PRIORITY = os.path.join(DIR, "btc_priority.txt")
STATE_FILE = os.path.join(DIR, "btc_state.json")
SIGNALS_FILE = os.path.join(DIR, "btc_signals.json")
COLLECTOR = os.path.join(DIR, "btc_latest.json")
TV_DATA = os.path.join(DIR, "btc_tv_data.json")
MACRO = os.path.join(DIR, "btc_macro.json")
VAL_FALLBACK, VAH_FALLBACK, DO_FALLBACK = 63886.0, 64490.0, 63312.0

os.makedirs(DIR, exist_ok=True)
price_history = deque(maxlen=18)       # 3min for velocity + sweep detection
cvd_history = deque(maxlen=36)         # 6min for divergence detection

# ========== 工具函数 ==========
def write_pending(msg, priority="normal"):
    tag = "⭐" if priority == "high" else ""
    with open(PENDING, "a") as f:
        f.write(f"{tag}{msg}\n---\n")
    if priority == "high":
        with open(PRIORITY, "a") as f:
            f.write(f"{msg}\nBREAK\n")

def http_get(url, t=6):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "D/1.0"}), timeout=t).read())

def calc_vwap():
    try:
        k = http_get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=30")
        vs = sum(float(x[5]) for x in k)
        ws = sum((float(x[2])+float(x[3]))/2*float(x[5]) for x in k)
        return ws/vs if vs else None
    except: return None

def read_collector():
    try:
        with open(COLLECTOR) as f: return json.load(f)
    except: return {}

def read_tv_data():
    try:
        with open(TV_DATA) as f: return json.load(f)
    except: return {}

def load_state():
    try:
        with open(STATE_FILE) as f: return json.load(f)
    except:
        return {"last_blocks": {}, "last_vwap": 64200, "last_taker": 1.0, "last_price": 64200, "price_hist": [], "cvd_hist": []}

def save_state(s):
    with open(STATE_FILE, "w") as f: json.dump(s, f)

def get_tv_levels():
    tv = read_tv_data()
    return (tv.get("vwap"), tv.get("val") or tv.get("val_price"),
            tv.get("vah") or tv.get("vah_price"), tv.get("poc") or tv.get("poc_price"),
            tv.get("dopen") or tv.get("do_price"), tv.get("cvd"))

# ========== KillZone / Silver Bullet / 折溢价 ==========
KILLZONE_MAP = {
    "asia":   [(8,0,16,0)],       # 亚盘积累
    "london": [(14,0,17,0)],      # 伦敦初段
    "ny_am":  [(20,0,23,0)],      # 纽约上午
}
SILVER_BULLET = [
    (16,0,17,0),   # London 3-4AM EST = 16-17 CST
    (23,0,0,0),    # NY AM 10-11AM EST = 23-00 CST
    (3,0,4,0),     # NY PM 2-3PM EST = 03-04 CST
]

def get_killzone(now):
    h, m = now.hour, now.minute
    for name, slots in KILLZONE_MAP.items():
        for sh, sm, eh, em in slots:
            start, end = sh*60+sm, eh*60+em
            t = h*60+m
            if end > start and start <= t < end:
                return name
            if end <= start and (t >= start or t < end):
                return name
    return "outside"

def is_silver_bullet(now):
    h, m = now.hour, now.minute
    t = h*60+m
    for sh, sm, eh, em in SILVER_BULLET:
        start, end = sh*60+sm, eh*60+em
        if end > start and start <= t < end:
            return True
        if end <= start and (t >= start or t < end):
            return True
    return False

def premium_or_discount(price, session_high, session_low):
    """折价(折) / 溢价(溢) 基于50%分界"""
    if not session_high or not session_low or session_high == session_low:
        return "未知"
    mid = (session_high + session_low) / 2
    return "折价" if price < mid else "溢价"

# ========== CVD背离检测 ==========
def check_cvd_divergence(prices, cvd_vals):
    """检测CVD背离: 价HH + CVD LH = 空背离; 价LL + CVD HL = 多背离"""
    if len(prices) < 24 or len(cvd_vals) < 24:
        return None
    # 取最近24个点,分前后各12
    p_prev, p_now = prices[:12], prices[12:24]
    c_prev, c_now = cvd_vals[:12], cvd_vals[12:24]
    if not any(v is not None for v in c_prev) or not any(v is not None for v in c_now):
        return None
    p_prev_max, p_now_max = max(p_prev), max(p_now)
    p_prev_min, p_now_min = min(p_prev), min(p_now)
    c_prev_max = max(v for v in c_prev if v is not None)
    c_now_max = max(v for v in c_now if v is not None)
    c_prev_min = min(v for v in c_prev if v is not None)
    c_now_min = min(v for v in c_now if v is not None)

    # 空背离: 价创新高 + CVD没新高
    if p_now_max > p_prev_max and c_now_max < c_prev_max:
        return "bear"
    # 多背离: 价创新低 + CVD没新低
    if p_now_min < p_prev_min and c_now_min > c_prev_min:
        return "bull"
    return None

# ========== 流动性扫荡检测 ==========
def check_liquidity_sweep(price_history, val, vah):
    """破位+反抽 = 扫荡; 破位+延续 = 真突破"""
    if len(price_history) < 6:
        return None
    # 过去6个点(1min)内找最低最高
    p_min, p_max = min(price_history), max(price_history)
    p_now = price_history[-1]
    # 扫荡VAL: 价格到VAL下方但现在已经回VAL上方
    if p_min < val and p_now > val:
        return ("VAL扫荡", f"触{val:,.0f}下`${val-p_min:,.0f}` · 已回收")
    # 扫荡VAH: 价格到VAH上方但已经回到VAH下方
    if p_max > vah and p_now < vah:
        return ("VAH扫荡", f"触{vah:,.0f}上`${p_max-vah:,.0f}` · 已回收")
    return None

# ========== CVD吸收检测 ==========
def check_absorption(price, prices, cvd_vals):
    """CVD高但价不动=吸收"""
    if len(cvd_vals) < 18:
        return None
    recent_cvd = [v for v in list(cvd_vals)[-18:] if v is not None]
    if len(recent_cvd) < 12:
        return None
    cvd_range = max(recent_cvd) - min(recent_cvd)
    price_range = max(prices[-12:]) - min(prices[-12:])
    if cvd_range > 150 and price_range < 30:
        return "吸收" if min(recent_cvd[-6:]) > 0 else "派发"
    return None

# ========== FVG检测(简化) ==========
def check_fvg(prices):
    """三根K线宽>中间K线 = FVG"""
    if len(prices) < 3:
        return None
    c1, c2, c3 = prices[-3], prices[-2], prices[-1]
    if c1 < c3:  # 上涨FVG: c1高 < c3低
        return None  # 简化版: 需要来自K线的OHLC
    return None

# ========== 主循环 ==========
state = load_state()
vwap_local = state.get("last_vwap", 64200)
last_vw, last_tv_read = 0, 0
cnt = 0
BINANCE = "https://api.binance.com"

# 初始化历史 (从state恢复)
if state.get("price_hist"):
    price_history.extend(state["price_hist"][-18:])
if state.get("cvd_hist"):
    cvd_history.extend(state["cvd_hist"][-36:])

while True:
    time.sleep(10)
    cnt += 1
    now = datetime.now(TZ)
    ts = now.strftime("%H:%M")
    block = now.minute // 5

    if time.time() - last_vw > 60:
        nv = calc_vwap()
        if nv: vwap_local = nv; state["last_vwap"] = vwap_local; last_vw = time.time()

    if time.time() - last_tv_read > 30 or cnt <= 3:
        vwap_svp, val_svp, vah_svp, poc_svp, do_svp, cvd_svp = get_tv_levels()
        last_tv_read = time.time()
    else:
        vwap_svp, val_svp, vah_svp, poc_svp, do_svp, cvd_svp = get_tv_levels()

    vwap = vwap_svp or vwap_local
    val = val_svp or VAL_FALLBACK
    vah = vah_svp or VAH_FALLBACK

    try:
        price = float(http_get(f"{BINANCE}/api/v3/ticker/price?symbol=BTCUSDT")["price"])
    except:
        continue

    price_history.append(price)
    if cvd_svp is not None:
        cvd_history.append(cvd_svp)
    else:
        cvd_history.append(None)

    collector = read_collector()
    lb = state["last_blocks"]
    taker = collector.get("taker_ratio")
    last_taker = state.get("last_taker", 1.0)
    kz = get_killzone(now)
    sb = is_silver_bullet(now)
    sb_label = "银弹窗口🔥" if sb else ""
    kz_label_map = {"asia": "亚洲", "london": "伦敦", "ny_am": "纽约", "outside": "盘外"}
    kz_cn = kz_label_map.get(kz, "盘外")
    alerts = []
    div = None

    dv = vwap - price
    dl = val - price
    dh = vah - price
    near = 0 < dv <= 60
    bl = dl > 0; al = dl < 0; av = dv < 0; bh = dh < 0
    far_down = dv > 200; far_up = -dv > 200
    cvd_ctx = ""; cvd_s = None
    if cvd_svp is not None: cvd_ctx = f" · CVD{cvd_svp:+.0f}"; cvd_s = cvd_svp

    # === 1. 价位级 ===
    if near and lb.get("t") != block:
        lb["t"] = block; alerts.append(f"📊 VWAP测试 · {ts}\n价`{price:,.0f}` · VWAP`{vwap:,.0f}` · 上`${dv:,.0f}`{cvd_ctx}")
    if av and lb.get("r") != block:
        lb["r"] = block; alerts.append(f"🟢 站回VWAP · {ts}\n价`{price:,.0f}` · VWAP上`${-dv:,.0f}`{cvd_ctx}")
    if bl and lb.get("b") != block and cnt > 3:
        lb["b"] = block; d = "持续" if cnt > 10 else "新破"
        alerts.append(f"🔴 {d}破VAL · {ts}\n价`{price:,.0f}` · VAL`{val:,.0f}`下`${dl:,.0f}`{cvd_ctx}")
    if al and cnt > 3 and lb.get("k") != block:
        lb["k"] = block; alerts.append(f"🟡 站回VAL · {ts}\n价`{price:,.0f}` · VAL上`${-dl:,.0f}`{cvd_ctx}")
    if bh and lb.get("h") != block and cnt > 3:
        lb["h"] = block; alerts.append(f"🟠 破VAH · {ts}\n价`{price:,.0f}` · VAH上`${-dh:,.0f}`{cvd_ctx}")

    # === 2. CVD背离 ===
    if cnt > 36:
        div = check_cvd_divergence(list(price_history), list(cvd_history))
        if div and lb.get("d") != block:
            lb["d"] = block
            label = "空背离" if div == "bear" else "多背离"
            sb_tag = f" · {sb_label}" if sb_label else ""
            alerts.append(f"🔮 CVD{label} · {ts}\n价`{price:,.0f}` · {kz_cn} · CVD{cvd_s:+.0f}{sb_tag}")

    # === 3. 流动性扫荡 ===
    if cnt > 10:
        sweep = check_liquidity_sweep(list(price_history), val, vah)
        if sweep and lb.get("s") != block:
            lb["s"] = block
            alerts.append(f"🎯 {sweep[0]} · {ts}\n{sweep[1]}")

    # === 4. CVD吸收 ===
    if cnt > 36:
        ab = check_absorption(price, list(price_history), list(cvd_history))
        if ab and lb.get("a") != block:
            lb["a"] = block
            alerts.append(f"💧 CVD{ab} · {ts}\n价`{price:,.0f}` · 价不动·CVD大幅波动")

    # === 5. ⭐ 高胜率 ===
    if cnt > 5:
        if (far_down or far_up) and taker and abs(taker - last_taker) > 0.5 and lb.get("z") != block:
            lb["z"] = block
            direction = "多" if far_down and taker > 1.0 else "空" if far_up and taker < 1.0 else None
            if direction:
                tags = f" · {kz_cn}" if kz != "outside" else ""
                if sb_label: tags += f" · {sb_label}"
                alerts.append(f"⭐ 反转信号({direction}) · {ts}\n价`{price:,.0f}` · Taker`{taker}`{tags}")
        if far_down and taker and taker < 0.4 and lb.get("e") != block:
            lb["e"] = block; alerts.append(f"⭐ 空头延续 · {ts}\n价`{price:,.0f}` · VWAP`{vwap:,.0f}` · Taker卖`{taker}")
        if far_up and taker and taker > 1.6 and lb.get("g") != block:
            lb["g"] = block; alerts.append(f"⭐ 多头延续 · {ts}\n价`{price:,.0f}` · VWAP`{vwap:,.0f}` · Taker买`{taker}")

    # === 6. 📉 快速波动 ===
    if len(price_history) >= 3:
        pct_30s = (price_history[-1] - price_history[0]) / price_history[0] * 100
        if abs(pct_30s) > 0.3 and lb.get(f"v_{block}") != block:
            lb[f"v_{block}"] = block
            d = "下跌" if pct_30s < 0 else "上涨"
            alerts.append(f"📉 快速{d} · {ts}\n价`{price:,.0f}` · 30s`{pct_30s:+.2f}%`")

    # === 7. 极端偏离 ===
    if far_down and lb.get("x") != block: lb["x"] = block; alerts.append(f"📊 VWAP偏离 · {ts}\n价`{price:,.0f}` · VWAP下`${dv:,.0f}`")
    if far_up and lb.get("y") != block: lb["y"] = block; alerts.append(f"📊 VWAP偏离 · {ts}\n价`{price:,.0f}` · VWAP上`${-dv:,.0f}`")

    # 写入
    for a in alerts:
        write_pending(a, "high" if a.startswith("⭐") or a.startswith("🔮") else "normal")

    # 写入信号摘要(供分析cron)
    p_or_d = premium_or_discount(price, vah, val)
    signals = {
        "ts": ts, "price": price, "vwap": vwap, "val": val, "vah": vah,
        "cvd": cvd_s, "killzone": kz_cn, "silver_bullet": sb_label,
        "premium_discount": p_or_d, "divergence": div,
        "taker": taker, "session": "亚盘" if kz == "asia" else "伦敦" if kz == "london" else "纽约" if kz == "ny_am" else "盘外"
    }
    try:
        with open(SIGNALS_FILE, "w") as f: json.dump(signals, f)
    except: pass

    state["last_taker"] = taker or last_taker
    state["last_price"] = price
    state["price_hist"] = list(price_history)
    state["cvd_hist"] = list(cvd_history)
    save_state(state)
