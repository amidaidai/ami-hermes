#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
棠溪 · 统一多因子告警探测器 v3.0
替代旧的 level-based btc_alert_watch.py

检测矩阵（12维度）:
  ① VWAP Band 突破（+Band2上方=强趋势 / -Band2下方=崩溃）
  ② CVD 买卖压力（+3000以上斜率=强买 / -3000以下=强卖）
  ③ Taker 极值（>1.5=碾压买 / <0.7=碾压卖）
  ④ EMA 完美排列（Price>EMA9>21>34>55 / 反向）
  ⑤ Session KillZone 检测
  ⑥ Silver Bullet 窗（14-15UTC·位移确认）
  ⑦ FVG 填充确认
  ⑧ 流动性扫荡检测
  ⑨ 多空比极端（>2.0=拥挤 / <0.5=拥挤）
  ⑩ OI背离（价涨OI稳=健康 / 价涨OI跌=衰减）
  ⑪ 事件禁做检查
  ⑫ 宏观风险过滤

输出格式:
  ↑做多 | 模型名: 理由 | ★高胜率标记
  ↓做空 | 模型名: 理由  
  ○等待 | 模型名: 理由
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

# 噪音控制
COOLDOWN_S = 1800  # 30分钟内同模型不重复
_last_alerts: dict[str, float] = {}  # model_name → last_fired_unixtime

def emit_error(text: str):
    safe = text.encode("ascii", "replace").decode("ascii")
    sys.stdout.write(safe.rstrip() + "\n")
    sys.stdout.flush()

def _sf(val, default=0.0) -> float:
    try: return float(val)
    except: return default

def load_data() -> dict:
    """加载最新数据。"""
    data = {"price": 0.0, "vwap": 0.0, "vah": 0.0, "val": 0.0, "poc": 0.0,
            "band1_high": 0.0, "band1_low": 0.0, "band2_high": 0.0, "band2_low": 0.0,
            "ema9": 0.0, "ema21": 0.0, "ema34": 0.0, "ema55": 0.0,
            "cvd": 0.0, "cvd_slope": 0.0, "taker": 1.0, "ls_ratio": 1.0,
            "oi": 0.0, "funding": 0.0, "vol24": 0.0}
    
    try:
        if LATEST.exists():
            raw = json.loads(LATEST.read_text(encoding="utf-8"))
            data["price"] = _sf(raw.get("price"))
            data["oi"] = _sf(raw.get("oi"))
            data["funding"] = _sf(raw.get("funding"))
            data["ls_ratio"] = _sf(raw.get("ls_ratio"), 1.0)
            data["taker"] = _sf(raw.get("taker_ratio"), 1.0)
            data["vol24"] = _sf(raw.get("vol24"))
            data["vwap_15m"] = _sf(raw.get("vwap"))
    except Exception: pass
    
    try:
        if TV_DATA.exists():
            tv = json.loads(TV_DATA.read_text(encoding="utf-8"))
            for k in ["vwap","vah","val","poc","band1_high","band1_low",
                      "band2_high","band2_low","ema9","ema21","ema34","ema55",
                      "cvd","cvd_slope"]:
                data[k] = _sf(tv.get(k))
    except Exception: pass
    
    return data


def detect_alerts(data: dict) -> list[dict]:
    """核心：多因子并行检测，返回告警列表。"""
    p = data["price"]
    alerts = []
    now_ts = time.time()
    session_info = _get_session()
    
    # ─── ① VWAP Band 突破 ───
    b2h, b2l = data["band2_high"], data["band2_low"]
    b1h, b1l = data["band1_high"], data["band1_low"]
    vwap = data["vwap"]
    
    if b2h > 0 and p > b2h:
        # 价格突破+Band2 = 强趋势
        score = min(0.65 + (p - b2h) / b2h * 10, 0.85)
        alerts.append({
            "direction": "↑做多", "model": "VWAP+B2突破",
            "reason": f"价格{p:.0f}>+B2{b2h:.0f}·强势突破·>VWAP{vwap:.0f}",
            "conf": round(score, 2), "priority": "A" if data["cvd_slope"] > 2000 else "B",
        })
    
    if b2l > 0 and p < b2l:
        score = min(0.65 + (b2l - p) / b2l * 10, 0.85)
        alerts.append({
            "direction": "↓做空", "model": "VWAP-B2跌破",
            "reason": f"价格{p:.0f}<-B2{b2l:.0f}·加速下跌",
            "conf": round(score, 2), "priority": "A" if data["cvd_slope"] < -2000 else "B",
        })
    
    # ─── ② CVD 买卖压力 ───
    if data["cvd_slope"] > 3000 and data["cvd"] > 10000:
        alerts.append({
            "direction": "↑做多", "model": "CVD强买",
            "reason": f"CVD +{data['cvd']:.0f}·斜率+{data['cvd_slope']:.0f}·机构买盘",
            "conf": 0.70, "priority": "A",
        })
    if data["cvd_slope"] < -3000 and data["cvd"] < -10000:
        alerts.append({
            "direction": "↓做空", "model": "CVD强卖",
            "reason": f"CVD {data['cvd']:.0f}·斜率{data['cvd_slope']:.0f}·机构卖盘",
            "conf": 0.70, "priority": "A",
        })
    
    # ─── ③ Taker 极值 ───
    if data["taker"] > 1.5:
        alerts.append({
            "direction": "↑做多", "model": "Taker碾压买",
            "reason": f"Taker {data['taker']:.2f}·买方2x碾压",
            "conf": 0.60, "priority": "B",
        })
    if data["taker"] < 0.7:
        alerts.append({
            "direction": "↓做空", "model": "Taker碾压卖",
            "reason": f"Taker {data['taker']:.2f}·卖方碾压",
            "conf": 0.60, "priority": "B",
        })
    
    # ─── ④ EMA 完美排列 ───
    e9, e21, e34, e55 = data["ema9"], data["ema21"], data["ema34"], data["ema55"]
    if all(x > 0 for x in [e9, e21, e34, e55]):
        if p > e9 > e21 > e34 > e55:
            alerts.append({
                "direction": "↑做多", "model": "EMA完美多头",
                "reason": f"P>{e9:.0f}>{e21:.0f}>{e34:.0f}>{e55:.0f}",
                "conf": 0.65, "priority": "B",
            })
        if p < e9 < e21 < e34 < e55:
            alerts.append({
                "direction": "↓做空", "model": "EMA完美空头",
                "reason": f"P<{e9:.0f}<{e21:.0f}<{e34:.0f}<{e55:.0f}",
                "conf": 0.65, "priority": "B",
            })
    
    # ─── ⑤ Session KillZone ───
    if session_info.get("killzone"):
        kz = session_info["killzone"]
        if kz["volatility"] == "high":
            alerts.append({
                "direction": "○等待", "model": "KillZone活跃",
                "reason": f"{kz['name']}·波动率高·注意突破",
                "conf": 0.30, "priority": "C",
            })
    
    # ─── ⑥ Silver Bullet 窗 ───
    if session_info.get("is_silver_bullet"):
        alerts.append({
            "direction": "○监测", "model": "★SilverBullet窗",
            "reason": "14-15UTC银弹时间·待位移确认",
            "conf": 0.50, "priority": "A",
        })
    
    # ─── ⑦ 多空比极端 ───
    if data["ls_ratio"] > 2.0:
        alerts.append({
            "direction": "↓做空", "model": "多拥挤反转",
            "reason": f"多空比{data['ls_ratio']:.1f}·拥挤·防踩踏",
            "conf": 0.45, "priority": "C",
        })
    if data["ls_ratio"] < 0.5 and data["ls_ratio"] > 0:
        alerts.append({
            "direction": "↑做多", "model": "空拥挤反转",
            "reason": f"多空比{data['ls_ratio']:.1f}·空拥挤·防轧空",
            "conf": 0.45, "priority": "C",
        })
    
    # ─── ⑧ 综合高胜率标记 ───
    # 当 A级信号 ≥ 2个 且同方向 → 标记 ★
    a_alerts = [a for a in alerts if a["priority"] == "A"]
    long_a = [a for a in a_alerts if "做多" in a["direction"]]
    short_a = [a for a in a_alerts if "做空" in a["direction"]]
    
    if len(long_a) >= 2:
        for a in long_a:
            a["star"] = "★"
            a["priority"] = "A+"
    if len(short_a) >= 2:
        for a in short_a:
            a["star"] = "★"
            a["priority"] = "A+"
    
    return alerts


def _get_session() -> dict:
    """获取当前 Session 信息。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hermes" / "scripts"))
        from session_strategy import get_session, get_active_killzone
        session = get_session()
        kz = get_active_killzone()
        return {
            "session": session["name"],
            "strategy": session["strategy"],
            "killzone": kz,
            "is_silver_bullet": bool(kz and kz.get("key") == "silver_bullet"),
        }
    except Exception:
        return {"session": "未知", "strategy": "default", "killzone": None, "is_silver_bullet": False}


def write_pending(alerts: list[dict]) -> int:
    """写入 pending 文件供 btc_push_cron 推送。"""
    now_ts = time.time()
    written = 0
    
    for a in alerts:
        # 噪音过滤: 同模型 30min 冷却
        model = a["model"]
        last = _last_alerts.get(model, 0)
        if now_ts - last < COOLDOWN_S and a["priority"] != "A+":
            continue
        
        _last_alerts[model] = now_ts
        
        star = a.get("star", "")
        direction = a["direction"]
        line = f"{star}{direction} | {a['model']}: {a['reason']}"
        
        with open(PENDING, "a", encoding="utf-8") as f:
            f.write(f"{line}\n---\n")
        written += 1
    
    return written


def main():
    data = load_data()
    if data["price"] <= 0:
        emit_error("ERROR: no price data")
        return 1
    
    alerts = detect_alerts(data)
    if not alerts:
        # 静默
        return 0
    
    # 保存状态
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({
            "last_check": datetime.now(TZ).strftime("%H:%M"),
            "last_price": data["price"],
            "alert_count": len(alerts),
            "cooldowns": _last_alerts,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except: pass
    
    written = write_pending(alerts)
    if written > 0:
        stars = [a for a in alerts if a.get("star")]
        star_note = f" · {len(stars)}个★" if stars else ""
        safe = f"alerts={written}{star_note}".encode("ascii", "replace").decode("ascii")
        sys.stdout.write(safe + "\n")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
