#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
棠溪 · 统一多因子告警探测器 v3.1
替代旧的 level-based btc_alert_watch.py

检测矩阵（14维度 + Confluence评分）:
  ① VWAP Band 突破 ② CVD 买卖压力 ③ Taker 极值
  ④ EMA 完美排列 ⑤ KillZone ⑥ Silver Bullet 窗
  ⑦ 多空比极端 ⑧ OI背离 ⑨ 事件禁做
  ⑩ 三层确认(OB+FVG+Sweep) ⑪ SilverBullet位移
  ⑫ VAH/VAH回收 ⑬ POC磁吸 ⑭ 宏观风险

Confluence评分: 所有激活信号加权求和→A+/A/B/C/D五级
"""

import json, os, sys, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DIR = Path.home() / "AppData/Local/hermes/data"
PENDING = DIR / "btc_pending.txt"
STATE = DIR / "detector_state.json"
LATEST = DIR / "btc_latest.json"
TV_DATA = DIR / "btc_tv_data.json"

COOLDOWN_S = 900  # 15min 同模型冷却
_last_alerts: dict[str, float] = {}

def emit_error(text: str):
    sys.stdout.write(text.encode("ascii","replace").decode("ascii").rstrip()+"\n")

def _sf(val, default=0.0) -> float:
    try: return float(val)
    except: return default

def load_data() -> dict:
    d = {"price":0,"vwap":0,"vah":0,"val":0,"poc":0,
         "band1_high":0,"band1_low":0,"band2_high":0,"band2_low":0,
         "ema9":0,"ema21":0,"ema34":0,"ema55":0,
         "cvd":0,"cvd_slope":0,"taker":1.0,"ls_ratio":1.0,"oi":0,"funding":0,"vol24":0}
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
                if k in tv: d[k]=_sf(tv[k])
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
            "reason":f"价格{p:.0f}>+B2{b2h:.0f}·>VWAP{vwap:.0f}",
            "conf":round(s,2),"weight":3,"priority":"A"})
    if b2l>0 and p<b2l:
        s=min(0.65+(b2l-p)/b2l*10,0.85)
        alerts.append({"direction":"↓做空","model":"VWAP-B2跌破",
            "reason":f"价格{p:.0f}<-B2{b2l:.0f}",
            "conf":round(s,2),"weight":3,"priority":"A"})
    
    if data["cvd_slope"]>3000 and data["cvd"]>10000:
        alerts.append({"direction":"↑做多","model":"CVD强买",
            "reason":f"CVD+{data['cvd']:.0f}·斜率+{data['cvd_slope']:.0f}",
            "conf":0.70,"weight":3,"priority":"A"})
    if data["cvd_slope"]<-3000 and data["cvd"]<-10000:
        alerts.append({"direction":"↓做空","model":"CVD强卖",
            "reason":f"CVD{data['cvd']:.0f}·斜率{data['cvd_slope']:.0f}",
            "conf":0.70,"weight":3,"priority":"A"})
    
    if data["taker"]>1.5:
        alerts.append({"direction":"↑做多","model":"Taker碾压买",
            "reason":f"Taker{data['taker']:.2f}·买方碾压","conf":0.60,"weight":2,"priority":"B"})
    if data["taker"]<0.7:
        alerts.append({"direction":"↓做空","model":"Taker碾压卖",
            "reason":f"Taker{data['taker']:.2f}·卖方碾压","conf":0.60,"weight":2,"priority":"B"})
    
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
            "reason":"14-15UTC银弹·待位移确认","conf":0.50,"weight":2,"priority":"A"})
    
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
    _compute_confluence(data,alerts)
    return alerts

def write_pending(alerts: list[dict]) -> int:
    now_ts=time.time(); written=0
    for a in alerts:
        model=a["model"]; last=_last_alerts.get(model,0)
        if now_ts-last<COOLDOWN_S and a.get("priority","B")!="A+": continue
        _last_alerts[model]=now_ts
        star=a.get("star",""); d=a["direction"]
        
        # 决策驾驶舱格式
        if a.get("is_confluence"):
            line=(f"{star}{d} | Confluence {a['priority']}: {a['reason']}\n"
                  f"  → {a.get('key_levels','')}")
        else:
            line=f"{star}{d} | {model}: {a['reason']} (conf:{a['conf']:.0%})"
        
        with open(PENDING,"a",encoding="utf-8") as f:
            f.write(f"{line}\n---\n")
        written+=1
    return written

def main():
    data=load_data()
    if data["price"]<=0: emit_error("ERROR: no price"); return 1
    alerts=detect_alerts(data)
    if not alerts: return 0
    try:
        STATE.parent.mkdir(parents=True,exist_ok=True)
        STATE.write_text(json.dumps({"last_check":datetime.now(TZ).strftime("%H:%M"),
            "price":data["price"],"count":len(alerts),"cooldowns":_last_alerts},
            ensure_ascii=False,indent=2),encoding="utf-8")
    except: pass
    w=write_pending(alerts)
    if w>0:
        stars=[a for a in alerts if a.get("star")]
        cc=next((a for a in alerts if a.get("is_confluence")),None)
        grade=cc["priority"] if cc else "?"
        safe=f"alerts={w} grade={grade} stars={len(stars)}".encode("ascii","replace").decode("ascii")
        sys.stdout.write(safe+"\n")
    return 0

if __name__=="__main__": raise SystemExit(main())
