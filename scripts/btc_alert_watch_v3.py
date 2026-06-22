#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
棠溪 · 统一多因子告警探测器 v4.0
对标 SVP+ICT+VWAP+EMA+CVD 指标内 DMI 决策表

检测矩阵（14维度 → DMI决策引擎）:
  ① VWAP Band 突破 ② CVD 买卖压力 ③ Taker 极值
  ④ EMA 完美排列 ⑤ KillZone ⑥ Silver Bullet 窗
  ⑦ 多空比极端 ⑧ OI背离 ⑨ 事件禁做
  ⑩ 三层确认(OB+FVG+Sweep) ⑪ SilverBullet位移
  ⑫ VAH/VAH回收 ⑬ POC磁吸 ⑭ 宏观风险

v4.0: DMI决策引擎 — 趋势分+反转分双轨 → A/B/C/X四级
      对标 Pine 指标内 DMI Strategy Table
      仅 A 级推送（趋势分≥8·CVD确认·关键位门控·HTF过滤）
"""

import json, os, sys, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DIR = Path.home() / "AppData/Local/hermes/data"
PENDING = DIR / "btc_pending.txt"
STATE = DIR / "detector_state.json"
LATEST = DIR / "btc_latest.json"
TV_DATA = DIR / "BTCUSDT.P_tv_data.json"  # matches fetch_tv_data.cjs output

COOLDOWN_S = 900  # 15min 同模型冷却
_last_alerts: dict[str, float] = {}

# v4.0: DMI决策引擎
try:
    from dmi_decision import compute_scores, compute_dmi, compute_atr
except ImportError:
    # fallback: add scripts dir to path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from dmi_decision import compute_scores, compute_dmi, compute_atr

def emit_error(text: str):
    sys.stdout.write(text.encode("ascii","replace").decode("ascii").rstrip()+"\n")

def _sf(val, default=0.0) -> float:
    try: return float(val)
    except: return default

def load_data() -> dict:
    d = {"price":0,"vwap":0,"vah":0,"val":0,"poc":0,
         "band1_high":0,"band1_low":0,"band2_high":0,"band2_low":0,
         "ema9":0,"ema21":0,"ema34":0,"ema55":0,
         "cvd":0,"cvd_slope":0,"taker":1.0,"ls_ratio":1.0,"oi":0,"funding":0,"vol24":0,
         "w_vwap":0,"m_vwap":0,"labels":[],"levels":[],"ohlcv_bars":[]}
    try:
        if LATEST.exists():
            r=json.loads(LATEST.read_text(encoding="utf-8"))
            for k in ["price","oi","funding","ls_ratio","taker_ratio","vol24","vwap"]:
                if k in r: d[k if k!="taker_ratio" else "taker"]=_sf(r[k])
        if not d["price"]:
            # 自愈：直接从Binance拉
            import urllib.request
            req=urllib.request.Request("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                headers={"User-Agent":"D/1.0"})
            with urllib.request.urlopen(req,timeout=5) as resp:
                d["price"]=float(json.loads(resp.read())["price"])
    except: pass
    try:
        if TV_DATA.exists():
            tv=json.loads(TV_DATA.read_text(encoding="utf-8"))
            for k in d:
                if k in tv: d[k]=_sf(tv[k]) if k not in ("labels","levels","ohlcv_bars") else tv.get(k,d[k])
            # Extract OHLCV bars for DMI computation
            if "ohlcv" in tv and "bars" in tv.get("ohlcv",{}):
                d["ohlcv_bars"] = tv["ohlcv"]["bars"]
            # Labels/levels for ICT sweep detection
            if "labels" in tv:
                d["labels"] = tv["labels"]
            if "levels" in tv:
                d["levels"] = tv["levels"]
    except: pass
    return d

def _get_session() -> dict:
    try:
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"hermes"/"scripts"))
        from session_strategy import get_session, get_active_killzone
        s=get_session(); kz=get_active_killzone()
        return {"session":s["name"],"strategy":s["strategy"],"killzone":kz,
                "is_silver_bullet":bool(kz and kz.get("key")=="silver_bullet")}
    except: return {"session":"?","strategy":"default","killzone":None,"is_silver_bullet":False}

# ═══════════════ 检测函数 ═══════════════

def _detect_basic(data: dict, alerts: list, si: dict):
    p=data["price"]; b2h,b2l=data["band2_high"],data["band2_low"]
    b1h,b1l=data["band1_high"],data["band1_low"]; vwap=data["vwap"]
    
    if b2h>0 and p>b2h:
        s=min(0.65+(p-b2h)/b2h*10,0.85)
        alerts.append({"direction":"↑做多","model":"VWAP+B2突破",
            "reason":f"价{p:,.0f}>B2上{b2h:,.0f}",
            "conf":round(s,2),"weight":3,"priority":"A"})
    if b2l>0 and p<b2l:
        s=min(0.65+(b2l-p)/b2l*10,0.85)
        alerts.append({"direction":"↓做空","model":"VWAP-B2跌破",
            "reason":f"价{p:,.0f}<B2下{b2l:,.0f}",
            "conf":round(s,2),"weight":3,"priority":"A"})
    
    if data["cvd_slope"]>3000 and data["cvd"]>10000:
        alerts.append({"direction":"↑做多","model":"CVD强买",
            "reason":f"+{data['cvd']:,.0f}·斜率+{data['cvd_slope']:,.0f}",
            "conf":0.70,"weight":3,"priority":"A"})
    if data["cvd_slope"]<-3000 and data["cvd"]<-10000:
        alerts.append({"direction":"↓做空","model":"CVD强卖",
            "reason":f"{data['cvd']:,.0f}·斜率{data['cvd_slope']:,.0f}",
            "conf":0.70,"weight":3,"priority":"A"})
    
    if data["taker"]>1.5:
        alerts.append({"direction":"↑做多","model":"Taker碾压买",
            "reason":f"{data['taker']:.2f}买方主导","conf":0.60,"weight":2,"priority":"B"})
    if data["taker"]<0.7:
        alerts.append({"direction":"↓做空","model":"Taker卖压",
            "reason":f"{data['taker']:.2f}卖方主导","conf":0.55,"weight":2,"priority":"B"})
    
    e9,e21,e34,e55=data["ema9"],data["ema21"],data["ema34"],data["ema55"]
    if all(x>0 for x in[e9,e21,e34,e55]):
        if p>e9>e21>e34>e55:
            alerts.append({"direction":"↑做多","model":"EMA完美多头",
                "reason":f"P>{e9:.0f}>{e21:.0f}>{e34:.0f}>{e55:.0f}",
                "conf":0.65,"weight":2,"priority":"B"})
        if p<e9<e21<e34<e55:
            alerts.append({"direction":"↓做空","model":"EMA完美空头",
                "reason":f"P<{e9:.0f}<{e21:.0f}<{e34:.0f}<{e55:.0f}",
                "conf":0.65,"weight":2,"priority":"B"})
    
    if si.get("killzone") and si["killzone"]["volatility"]=="high":
        alerts.append({"direction":"○等待","model":"KillZone",
            "reason":f"{si['killzone']['name']}·波高·待突破",
            "conf":0.30,"weight":1,"priority":"C"})
    
    if si.get("is_silver_bullet"):
        alerts.append({"direction":"○监测","model":"★SilverBullet窗",
            "reason":"14-15UTC银弹·待位移确认","conf":0.50,"weight":2,"priority":"B"})
    
    if data["ls_ratio"]>2.0:
        alerts.append({"direction":"↓做空","model":"多拥挤反转",
            "reason":f"L/S{data['ls_ratio']:.1f}·拥挤·防踩踏","conf":0.45,"weight":1,"priority":"C"})
    if 0<data["ls_ratio"]<0.5:
        alerts.append({"direction":"↑做多","model":"空拥挤反转",
            "reason":f"L/S{data['ls_ratio']:.1f}·空拥挤","conf":0.45,"weight":1,"priority":"C"})
    
    # VAH 回收
    vah=data["vah"]; val=data["val"]
    if vah>0 and abs(p-vah)<min(300,p*0.005):
        alerts.append({"direction":"↑做多" if p>vah else "○等待","model":"VAH磁吸",
            "reason":f"距VAH{vah:.0f}·{abs(p-vah):.0f}点·观察回收",
            "conf":0.50 if p>vah else 0.35,"weight":2,"priority":"B"})
    if val>0 and abs(p-val)<min(300,p*0.005):
        alerts.append({"direction":"↓做空" if p<val else "○等待","model":"VAL磁吸",
            "reason":f"距VAL{val:.0f}·{abs(p-val):.0f}点",
            "conf":0.50 if p<val else 0.35,"weight":2,"priority":"B"})


def _detect_triple_confirm(data: dict, alerts: list):
    """三层确认 (OB+FVG+Sweep) — 从 triple_confirm 模块加载。"""
    try:
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"hermes"/"scripts"))
        from triple_confirm import triple_confirmation_score
        ohlcv=data.get("klines",{}).get("15m",[])
        tv={"vwap":data["vwap"],"vah":data["vah"],"val":data["val"],
            "poc":data["poc"],"cvd":data["cvd"],"cvd_slope":data["cvd_slope"]}
        tc_dir,tc_conf,tc_reason=triple_confirmation_score(data["price"],ohlcv or[],tv,{})
        if tc_dir!="null" and tc_conf>0.30:
            dir_label="↑做多" if tc_dir=="long" else "↓做空"
            priority="A" if tc_conf>=0.6 else "B"
            alerts.append({"direction":dir_label,"model":"三层确认",
                "reason":tc_reason,"conf":round(tc_conf,2),"weight":3,"priority":priority})
    except Exception: pass


def _detect_silver_bullet_displacement(data: dict, alerts: list, si: dict):
    """Silver Bullet 位移确认 — 银弹窗内有大实体+确认。"""
    if not si.get("is_silver_bullet"): return
    try:
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"hermes"/"scripts"))
        from triple_confirm import detect_fvg, detect_liquidity_sweep
        ohlcv=data.get("klines",{}).get("15m",[])
        if not ohlcv: return
        fvg=detect_fvg(ohlcv) if ohlcv else None
        sweep=detect_liquidity_sweep(ohlcv,{"cvd":data["cvd"],"cvd_slope":data["cvd_slope"]}) if ohlcv else None
        if fvg or sweep:
            parts=[]; direction="○监测"; conf=0.45
            if fvg: parts.append(f"FVG({fvg['type']})")
            if sweep: parts.append(f"Sweep({sweep['type']})")
            if fvg and fvg["type"]=="bullish": direction="↑做多"; conf=0.55
            if sweep and sweep["type"]=="bullish_sweep": direction="↑做多"; conf=0.55
            alerts.append({"direction":direction,"model":"银弹确认",
                "reason":"·".join(parts),"conf":conf,"weight":2,"priority":"A" if conf>0.5 else "B"})
    except Exception: pass


def _compute_confluence(data: dict, alerts: list):
    """Confluence 综合评分: 所有信号加权求和 → 综合质量评级。"""
    if not alerts: return
    
    # 加权求和
    long_w=sum(a.get("weight",1) for a in alerts if "做多" in a["direction"])
    short_w=sum(a.get("weight",1) for a in alerts if "做空" in a["direction"])
    total_w=long_w+short_w
    dominant="↑做多" if long_w>short_w else "↓做空" if short_w>long_w else "○震荡"
    
    # 评级
    if total_w>=8: grade="A+"; desc="极强共振·多因子一致"
    elif total_w>=6: grade="A"; desc="强共振·高胜率窗口"
    elif total_w>=4: grade="B"; desc="中等共振·需确认"
    elif total_w>=2: grade="C"; desc="弱信号·建议等待"
    else: grade="D"; desc="噪音"
    
    # A级及以上同方向≥2 → ★标记
    a_count=len([a for a in alerts if a["priority"]=="A"])
    if a_count>=2 and long_w>short_w*2:
        for a in alerts:
            if "做多" in a["direction"]: a["star"]="★"; a["priority"]="A+"
    if a_count>=2 and short_w>long_w*2:
        for a in alerts:
            if "做空" in a["direction"]: a["star"]="★"; a["priority"]="A+"
    
    # 插入综合评分作为第一条
    kz=next((a for a in alerts if a["model"]=="KillZone"),None)
    vah_val=next((a for a in alerts if "磁吸" in a["model"]),None)
    key_str=""
    if kz: key_str=kz["reason"]
    if vah_val: key_str+=f" · {vah_val['reason']}"
    
    confluence_alert={
        "direction":dominant,"model":f"Confluence {grade}",
        "reason":f"权重{long_w}/{short_w}·{desc}",
        "conf":round(min(total_w/10,1.0),2),"weight":0,"priority":grade,
        "is_confluence":True,"key_levels":key_str
    }
    alerts.insert(0,confluence_alert)

# ═══════════════ 写入 ═══════════════

def detect_alerts(data: dict) -> list[dict]:
    alerts=[]; si=_get_session()
    _detect_basic(data,alerts,si)
    try: _detect_triple_confirm(data,alerts)
    except: pass
    try: _detect_silver_bullet_displacement(data,alerts,si)
    except: pass
    # ═══ v3.1: CVD趋势线破 ═══
    try:
        _detect_cvd_trendline(data, alerts)
    except: pass
    
    # ═══ v3.1: Confluence 综合评分 ═══
    _compute_confluence(data, alerts)
    return alerts

def write_pending(alerts: list[dict], data: dict) -> int:
    """v3.4: 分层可读格式 — 短信风格 + conf过滤 + 精简reason"""
    now_ts = time.time()
    # 过滤: 冷却 + 低置信 + 纯噪音
    active = []
    for a in alerts:
        model = a["model"]
        last = _last_alerts.get(model, 0)
        # 冷却跳过（A+除外）
        if now_ts - last < COOLDOWN_S and a.get("priority", "B") != "A+":
            continue
        # confluence 行永远通过
        if a.get("is_confluence"):
            _last_alerts[model] = now_ts
            active.append(a)
            continue
        # 低置信跳过
        conf = a.get("conf", 0.5)
        priority = a.get("priority", "B")
        if priority == "D":
            continue
        if conf < 0.35:
            continue
        # ○等待类如果没有方向信号则跳过
        if "等待" in a.get("direction", "") or "监测" in a.get("direction", ""):
            if _last_alerts.get(model, 0) > 0:
                _last_alerts[model] = now_ts
                continue  # 只推一次，之后冷却
        _last_alerts[model] = now_ts
        active.append(a)
    if not active:
        return 0

    # ── v3.6: 只有A+/A高胜率信号才推送（≥80%）──
    confluence = next((a for a in active if a.get("is_confluence")), None)
    if not confluence or confluence.get("priority", "D") not in ("A+", "A"):
        return 0  # B/C/D: 静默，不写pending文件

    # 分离信号行
    signals = [a for a in active if not a.get("is_confluence")]

    # 按方向分组
    longs = [s for s in signals if "做多" in s.get("direction", "")]
    shorts = [s for s in signals if "做空" in s.get("direction", "")]
    neutrals = [s for s in signals if s not in longs and s not in shorts]

    # ── 数据快照 ──
    price = data.get("price", 0)
    vwap = data.get("vwap", 0)
    now_str = datetime.now(TZ).strftime("%H:%M")

    lines = []
    lines.append(f"══ BTC · {price:,.0f} · VWAP {vwap:,.0f} · {now_str} ══")

    # ── 综合评定 ──
    grade = confluence["priority"] if confluence else "?"
    n_long = len(longs)
    n_short = len(shorts)
    dominant = ""
    if n_long > n_short:
        dominant = "偏多"
    elif n_short > n_long:
        dominant = "偏空"
    else:
        dominant = "中性"

    star_mark = ""
    if confluence and confluence.get("star"):
        star_mark = " ★高胜率"
    lines.append(f"综合: {grade} {dominant} (多{n_long} vs 空{n_short}){star_mark}")

    # ── 一句话总结 ──
    summary = _gen_summary(longs, shorts, neutrals, data, dominant, grade)
    if summary:
        lines.append(f"  {summary}")

    # ── 多头信号 ──
    if longs:
        lines.append("")
        for s in longs:
            model = s["model"]
            reason = s["reason"]
            conf = s.get("conf", 0)
            conf_str = f" · {conf:.0%}" if conf > 0 else ""
            lines.append(f"  + {model} → {reason}{conf_str}")

    # ── 空头信号 ──
    if shorts:
        lines.append("")
        for s in shorts:
            model = s["model"]
            reason = s["reason"]
            conf = s.get("conf", 0)
            conf_str = f" · {conf:.0%}" if conf > 0 else ""
            lines.append(f"  - {model} → {reason}{conf_str}")

    # ── 中性/窗口 ──
    if neutrals:
        lines.append("")
        for s in neutrals:
            model = s["model"]
            reason = s["reason"]
            lines.append(f"  ~ {model} → {reason}")

    # ── 关键位 ──
    vah = data.get("vah", 0)
    val = data.get("val", 0)
    poc = data.get("poc", 0)
    b2h = data.get("band2_high", 0)
    b2l = data.get("band2_low", 0)
    key_parts = []
    if vwap: key_parts.append(f"VWAP {vwap:,.0f}")
    if vah: key_parts.append(f"VAH {vah:,.0f}")
    if val: key_parts.append(f"VAL {val:,.0f}")
    if b2h: key_parts.append(f"B2上 {b2h:,.0f}")
    if b2l: key_parts.append(f"B2下 {b2l:,.0f}")
    if key_parts:
        lines.append("")
        lines.append(f"关键位: {' · '.join(key_parts)}")

    # ── 指标速览 ──
    cvd = data.get("cvd", 0)
    taker = data.get("taker", 1)
    oi = data.get("oi", 0)
    metrics = []
    if cvd: metrics.append(f"CVD {cvd:+,.0f}")
    if taker != 1: metrics.append(f"Taker {taker:.2f}")
    if oi and oi > 1000: metrics.append(f"OI {oi/1000:,.0f}K")
    if metrics:
        lines.append(f"指标: {' · '.join(metrics)}")

    # ── 下一步: 作战建议 ──
    next_step = _gen_next_step(longs, shorts, neutrals, data, dominant, grade)
    if next_step:
        lines.append("")
        lines.append(f"下一步: {next_step}")

    # 写入
    content = "\n".join(lines) + "\n"
    with open(PENDING, "w", encoding="utf-8") as f:
        f.write(content)
    return len(active)

# ═══════════════ 一句话总结生成 ═══════════════

def _gen_summary(longs: list, shorts: list, neutrals: list,
                 data: dict, dominant: str, grade: str) -> str:
    """v3.4: 精炼预警句 — ≤40字，带'谨慎/关注/警惕'关键词。"""
    price = data.get("price", 0)
    vwap = data.get("vwap", 0)
    vah = data.get("vah", 0)
    val = data.get("val", 0)
    b2h = data.get("band2_high", 0)
    b2l = data.get("band2_low", 0)
    cvd = data.get("cvd", 0)
    taker = data.get("taker", 1)

    # ── 核心矛盾检测 ──
    has_b2_break = any("B2" in s.get("model","") for s in longs)
    has_b2_fall = any("B2" in s.get("model","") for s in shorts)
    has_cvd_long = any("CVD" in s.get("model","") and "强买" in s.get("direction","") for s in longs)
    has_cvd_short = any("CVD" in s.get("model","") and "强卖" in s.get("direction","") for s in shorts)
    has_taker_sell = taker < 0.7
    has_taker_buy = taker > 1.5
    has_sb = any("SilverBullet" in n.get("model","") for n in neutrals)
    has_kz = any("KillZone" in n.get("model","") for n in neutrals)
    has_fvg = any("FVG" in s.get("model","") for s in longs+shorts)

    # ── 核心逻辑: 方向 + 矛盾 + 行动提示 ──
    if dominant == "偏多":
        if has_b2_break and has_taker_sell:
            return f"多头控盘但Taker卖压({taker:.1f})，关注B2({b2h:,.0f})能否守稳"
        if has_b2_break:
            if has_sb:
                return f"站上B2({b2h:,.0f})，银弹窗临，关注14-15UTC突破确认"
            return f"站上B2({b2h:,.0f})，多头控盘，回踩{price:,.0f}上方做多"
        if has_cvd_long:
            return f"CVD强买支撑，守VWAP({vwap:,.0f})上方偏多"
        if has_sb:
            return f"价格{price:,.0f}偏多，银弹窗临，注意追高风险"
        return f"VWAP({vwap:,.0f})上方偏多，关注{price:,.0f}附近阻力"

    elif dominant == "偏空":
        if has_b2_fall:
            return f"失守B2({b2l:,.0f})，空头加速，关注VWAP({vwap:,.0f})支撑"
        if has_cvd_short and has_taker_sell:
            return f"CVD+Taker双卖压，若破VWAP({vwap:,.0f})则空头确认"
        if has_taker_sell:
            return f"Taker卖压({taker:.1f})持续，谨慎追空，等VWAP({vwap:,.0f})确认"
        return f"VWAP({vwap:,.0f})下方偏空，关注{val:,.0f}能否回收"

    else:  # 中性
        if has_sb:
            return f"多空均衡，银弹窗(14-15UTC)待选方向，观望为宜"
        if has_kz:
            return f"价格{price:,.0f}贴VWAP({vwap:,.0f})拉锯，KillZone活，等突破"
        if has_fvg:
            return f"价格{price:,.0f}附近拉锯，关注FVG回补方向"
        return f"价格{price:,.0f}贴VWAP({vwap:,.0f})，多空均衡，等信号"

    return ""

# ═══════════════ 下一步作战建议 ═══════════════

def _gen_next_step(longs: list, shorts: list, neutrals: list,
                   data: dict, dominant: str, grade: str) -> str:
    """根据信号方向 + 关键位，生成'看哪、做什么'的行动建议。"""
    price = data.get("price", 0)
    vwap = data.get("vwap", 0)
    vah = data.get("vah", 0)
    val = data.get("val", 0)
    b2h = data.get("band2_high", 0)
    b2l = data.get("band2_low", 0)
    taker = data.get("taker", 1)
    has_sb = any("SilverBullet" in n.get("model","") for n in neutrals)

    # ── 选最紧关键位 ──
    levels_above = []
    levels_below = []
    # 阻力：在价格上方
    if vah and vah > price: levels_above.append(("VAH", vah))
    if b2h and b2h > price: levels_above.append(("B2上", b2h))
    if b2l and b2l > price: levels_above.append(("B2下", b2l))
    # 支撑：在价格下方
    if b2h and b2h < price: levels_below.append(("B2上", b2h))
    if vwap and vwap < price: levels_below.append(("VWAP", vwap))
    if b2l and b2l < price: levels_below.append(("B2下", b2l))
    if val and val < price: levels_below.append(("VAL", val))

    nearest_resist = min(levels_above, key=lambda x: x[1]) if levels_above else None
    nearest_support = min(levels_below, key=lambda x: price-x[1]) if levels_below else None

    def _fmt(lv): return f"{lv[0]}({lv[1]:,.0f})" if lv else ""

    if dominant == "偏多":
        watch = nearest_support if nearest_support else ("VWAP", vwap)
        if nearest_resist:
            target_str = _fmt(nearest_resist)
        else:
            target_str = f"新高(>{price:,.0f})"
        if has_sb:
            return (f"守{_fmt(watch)}上方等银弹窗(14-15UTC)确认。"
                    f"若突破向上，目标{target_str}；"
                    f"若跌破{_fmt(watch)}则观望")
        if taker < 0.7:
            return (f"多头控盘但Taker背离({taker:.1f})，"
                    f"关注{_fmt(watch)}能否守稳。"
                    f"守稳做多目标{target_str}；失守则减仓")
        return (f"守{_fmt(watch)}上方做多，目标{target_str}。"
                f"若破{_fmt(watch)}则止损观望；若站上{target_str}则加仓")

    elif dominant == "偏空":
        watch = nearest_resist if nearest_resist else ("VWAP", vwap)
        target = nearest_support if nearest_support else ("VAL", val)
        return (f"守{_fmt(watch)}下方做空，目标{_fmt(target)}。"
                f"若站回{_fmt(watch)}则止损；若跌破{_fmt(target)}则空头加速")

    else:  # 中性
        if has_sb:
            sup = _fmt(nearest_support) if nearest_support else f"VWAP({vwap:,.0f})"
            if price > b2h > 0:
                return (f"银弹窗(14-15UTC)内观望。"
                        f"守{sup}做多看新高；若跌破{sup}则转空")
            if price < b2l and b2l > 0:
                return (f"银弹窗(14-15UTC)内观望。"
                        f"站回{sup}做多；若继续下破则等VWAP")
            return (f"银弹窗(14-15UTC)内观望。"
                    f"上破{_fmt(nearest_resist) if nearest_resist else 'B2上'}做多，"
                    f"下破{sup}做空")
        if nearest_resist and nearest_support:
            return (f"价格{price:,.0f}拉锯。"
                    f"上破{_fmt(nearest_resist)}做多，"
                    f"下破{_fmt(nearest_support)}做空，区间内观望")
        return f"价格{price:,.0f}附近等方向确认，观望为宜"

# ═══════════════ v4.0: DMI决策卡片 ═══════════════

def build_decision_card(data: dict, decision: dict, dmi: dict, atr: float) -> str:
    """对标 Pine 指标决策表格式: 等级+处理+背景+位置+量能+CVD+执行+风控"""
    price = data.get("price", 0)
    vwap = data.get("vwap", 0)
    vah = data.get("vah", 0)
    val = data.get("val", 0)
    now_str = datetime.now(TZ).strftime("%H:%M")

    grade = decision["grade"]
    bias = decision["bias"]
    treatment = decision["treatment"]
    trend_l = decision["trend_long"]
    trend_s = decision["trend_short"]
    rev_l = decision["reversal_long"]
    rev_s = decision["reversal_short"]

    lines = []
    lines.append(f"══ BTC · {price:,.0f} · VWAP {vwap:,.0f} · {now_str} ══")

    # ── 等级+处理 ──
    grade_symbol = {"A": "🟢", "B": "🟡", "C": "⚪", "X": "🔴"}.get(grade, "⚪")
    lines.append(f"等级: {grade_symbol} {grade} {bias} · 处理: {treatment}")

    # ── 评分 ──
    lines.append(f"趋势: 多{trend_l}/空{trend_s} · 反转: 多{rev_l}/空{rev_s}")

    # ── DMI ──
    dmi_text = f"ADX {dmi['adx']} · DI+{dmi['di_plus']}/DI-{dmi['di_minus']}"
    if dmi["bull_confirm"]: dmi_text += " · 顺多"
    elif dmi["bear_confirm"]: dmi_text += " · 顺空"
    elif dmi["hot"]: dmi_text += " · 过热⚠"
    elif dmi["trend_weak"]: dmi_text += " · 走弱"
    lines.append(f"DMI: {dmi_text}")

    # ── CVD ──
    cvd = data.get("cvd", 0)
    cvd_state = decision["cvd_state"]
    lines.append(f"CVD: {cvd:+,.0f} · {cvd_state}")

    # ── 位置 ──
    pos_parts = []
    if decision["price_above_vah"]: pos_parts.append("VAH上方")
    elif decision["price_below_val"]: pos_parts.append("VAL下方")
    elif decision["price_in_va"]: pos_parts.append("VA内")
    if decision["price_above_s"]: pos_parts.append("VWAP上方")
    else: pos_parts.append("VWAP下方")
    lines.append(f"位置: {' · '.join(pos_parts)}")

    # ── EMA ──
    ema9 = data.get("ema9", 0)
    ema21 = data.get("ema21", 0)
    ema34 = data.get("ema34", 0)
    ema55 = data.get("ema55", 0)
    if decision["ema_bull"]: ema_text = "多头排列 ✓"
    elif decision["ema_bear"]: ema_text = "空头排列 ✓"
    else: ema_text = "纠缠"
    lines.append(f"EMA: 9={ema9:,.0f} 21={ema21:,.0f} 34={ema34:,.0f} 55={ema55:,.0f} · {ema_text}")

    # ── 关键位 ──
    key_parts = []
    if vwap: key_parts.append(f"VWAP {vwap:,.0f}")
    if vah: key_parts.append(f"VAH {vah:,.0f}")
    if val: key_parts.append(f"VAL {val:,.0f}")
    b2h = data.get("band2_high", 0)
    b2l = data.get("band2_low", 0)
    if b2h: key_parts.append(f"B2上 {b2h:,.0f}")
    if b2l: key_parts.append(f"B2下 {b2l:,.0f}")
    if key_parts:
        lines.append(f"关键位: {' · '.join(key_parts)}")

    # ── 指标速览 ──
    taker = data.get("taker", 1)
    oi = data.get("oi", 0)
    metrics = []
    if taker != 1: metrics.append(f"Taker {taker:.2f}")
    if oi and oi > 1000: metrics.append(f"OI {oi/1000:,.0f}K")
    vol = decision.get("rel_vol", 0)
    if vol > 0: metrics.append(f"相对量 {vol:.1f}x")
    if metrics:
        lines.append(f"指标: {' · '.join(metrics)}")

    # ── 下一步 — 复用旧函数 ──
    # Build simplified alerts list for the old next_step generator
    fake_longs = []
    fake_shorts = []
    fake_neutrals = []
    if bias == "偏多":
        fake_longs.append({"model": "DMI决策", "direction": "↑做多"})
    elif bias == "偏空":
        fake_shorts.append({"model": "DMI决策", "direction": "↓做空"})
    else:
        fake_neutrals.append({"model": "DMI决策", "direction": "○等待"})

    next_step = _gen_next_step(fake_longs, fake_shorts, fake_neutrals, data, bias, grade)
    if next_step:
        lines.append("")
        lines.append(f"下一步: {next_step}")

    # ── 风控 ──
    lines.append("")
    lines.append(f"风控: {treatment} · 失效条件见决策表")

    return "\n".join(lines) + "\n"

# ═══════════════ main (v4.0) ═══════════════

def main():
    data = load_data()
    if data["price"] <= 0:
        emit_error("ERROR: no price")
        return 1

    ohlcv_bars = data.get("ohlcv_bars", [])
    if not ohlcv_bars or len(ohlcv_bars) < 20:
        # Fallback: use Binance Klines if TV OHLCV not available
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=30",
                headers={"User-Agent": "D/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = json.loads(resp.read())
                ohlcv_bars = [
                    {"time": k[0] // 1000, "open": float(k[1]), "high": float(k[2]),
                     "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                    for k in raw
                ]
        except Exception:
            pass

    if not ohlcv_bars or len(ohlcv_bars) < 20:
        emit_error("ERROR: no OHLCV data")
        return 1

    # Compute DMI + ATR
    highs = [b.get("high", 0) for b in ohlcv_bars]
    lows = [b.get("low", 0) for b in ohlcv_bars]
    closes = [b.get("close", 0) for b in ohlcv_bars]

    dmi = compute_dmi(highs, lows, closes)
    atr = compute_atr(highs, lows, closes)

    # DMI Decision Engine → grade
    decision = compute_scores(data, dmi, atr, ohlcv_bars)
    grade = decision["grade"]

    # Save state
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({
            "last_check": datetime.now(TZ).strftime("%H:%M"),
            "price": data["price"],
            "grade": grade,
            "trend_long": decision["trend_long"],
            "trend_short": decision["trend_short"],
            "reversal_long": decision["reversal_long"],
            "reversal_short": decision["reversal_short"],
            "dmi_adx": dmi["adx"],
            "dmi_di_plus": dmi["di_plus"],
            "dmi_di_minus": dmi["di_minus"],
            "atr": atr,
            "cvd_state": decision["cvd_state"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    # Only push A grade
    if grade != "A":
        return 0

    # Build & write decision card
    card = build_decision_card(data, decision, dmi, atr)
    if not card:
        return 0

    with open(PENDING, "w", encoding="utf-8") as f:
        f.write(card)

    safe = f"alerts=1 grade={grade} bias={decision['bias']} trend={decision['trend_long']}/{decision['trend_short']}".encode("ascii", "replace").decode("ascii")
    sys.stdout.write(safe + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ═══ v3.2: CVD趋势线破检测 ═══
def _detect_cvd_trendline(data: dict, alerts: list):
    """CVD趋势线突破检测 — LEADING信号(领先价格2-5根K线)。"""
    try:
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"hermes"/"scripts"))
        sys.path.insert(0,str(Path(__file__).resolve().parent/"scripts"))
        from orderflow_absorption import cvd_trendline_alert_line, detect_cvd_trendline_break
        
        # Build CVD series from TV data or use mock
        cvd_series = []
        cvd_val = data.get("cvd", 0)
        cvd_slope = data.get("cvd_slope", 0)
        if cvd_val != 0:
            # Simulate 20-point series from current CVD value
            cvd_series = [cvd_val - cvd_slope * (19-i)/2 for i in range(20)]
        else:
            return
        
        result = detect_cvd_trendline_break(cvd_series, window=10)
        if result.get("trendline_broken"):
            direction = "↑做多" if "上破" in result.get("direction","") else "↓做空" if "下破" in result.get("direction","") else "○监测"
            alerts.append({
                "direction": direction,
                "model": "CVD趋势线破",
                "reason": result.get("signal", ""),
                "conf": round(result.get("confidence", 50) / 100, 2),
                "weight": 3,
                "priority": "A" if result.get("confidence", 0) >= 70 else "B",
            })
    except Exception:
        pass
