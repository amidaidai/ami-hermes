#!/usr/bin/env python3
"""多因子汇聚评分引擎 v2 — 3+信号量化汇聚，过滤噪音"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json, os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DIR = os.path.expanduser("~/AppData/Local/hermes/data")
SIGNALS_FILE = os.path.join(DIR, "btc_signals.json")
LATEST_FILE = os.path.join(DIR, "btc_latest.json")
TV_DATA = os.path.join(DIR, "btc_tv_data.json")

# ===== 评分因子权重 =====
FACTORS = {
    "cvd_divergence": {"weight": 2, "name": "CVD背离"},
    "vwap_test": {"weight": 2, "name": "VWAP测试"},
    "liquidity_sweep": {"weight": 2, "name": "流动性扫荡"},
    "fvg_exists": {"weight": 1, "name": "FVG缺口"},
    "silver_bullet": {"weight": 1, "name": "银弹窗口"},
    "killzone_active": {"weight": 1, "name": "KillZone时段"},
    "premium_discount": {"weight": 1, "name": "折溢价区匹配"},
    "ls_extreme": {"weight": 1, "name": "多空比极端"},
    "taker_flip": {"weight": 2, "name": "Taker翻转"},
    "cvd_absorption": {"weight": 2, "name": "CVD吸收"},
    "volume_surge": {"weight": 1, "name": "量能爆发"},
    "ob_near": {"weight": 1, "name": "OB支撑/阻力"},
    "three_source_align": {"weight": 2, "name": "三源一致"},
    "ema_cross": {"weight": 1, "name": "EMA交叉"},
}


def _read_json(fp):
    try:
        with open(fp) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _safe_dict(data, key):
    """安全获取嵌套dict，防止bool/None。"""
    v = data.get(key, {})
    return v if isinstance(v, dict) else {}


def score_all(data=None):
    """全因子评分。返回 {total, level, signals: list, convergence: list}"""
    if data is None:
        data = _read_json(SIGNALS_FILE)
    latest = _read_json(LATEST_FILE)
    tv = _read_json(TV_DATA)
    
    signals = []
    
    # 1. CVD背离
    cvd_div = _safe_dict(data, "cvd_divergence")
    cvd_score = 0
    if cvd_div.get("active"):
        cvd_score = 2
    signals.append({
        "name": "CVD背离",
        "score": cvd_score,
        "max": 2,
        "detail": cvd_div.get("detail", "无"),
    })
    
    # 2. VWAP测试
    price = latest.get("price", tv.get("price", 0))
    vwap = tv.get("vwap", tv.get("VWAP", 0))
    vwap_score = 0
    vwap_dist = abs(price - vwap) if vwap else 999
    if vwap_dist < 60:
        vwap_score = 1
        if vwap_dist < 20:
            vwap_score = 2
    signals.append({
        "name": "VWAP测试",
        "score": vwap_score,
        "max": 2,
        "detail": f"距VWAP ${vwap_dist:.0f}",
    })
    
    # 3. 流动性扫荡
    sweep = _safe_dict(data, "liquidity_sweep")
    sweep_score = 2 if sweep.get("active") else 0
    signals.append({
        "name": "流动性扫荡",
        "score": sweep_score,
        "max": 2,
        "detail": sweep.get("detail", "无"),
    })
    
    # 4. FVG缺口
    fvg = data.get("fvg", {})
    fvg_score = 1 if fvg.get("exists") else 0
    signals.append({
        "name": "FVG缺口",
        "score": fvg_score,
        "max": 1,
    })
    
    # 5. 银弹窗口
    sb = _safe_dict(data, "silver_bullet")
    sb_score = 1 if sb.get("active") else 0
    signals.append({
        "name": "银弹窗口",
        "score": sb_score,
        "max": 1,
    })
    
    # 6. KillZone
    kz = _safe_dict(data, "killzone")
    kz_score = 1 if kz.get("active") else 0
    signals.append({
        "name": "KillZone时段",
        "score": kz_score,
        "max": 1,
        "detail": kz.get("zone", ""),
    })
    
    # 7. 折溢价区匹配
    pd = _safe_dict(data, "premium_discount")
    pd_score = 1 if pd.get("matched") else 0
    signals.append({
        "name": "折溢价区匹配",
        "score": pd_score,
        "max": 1,
        "detail": pd.get("zone", ""),
    })
    
    # 8. 多空比极端
    ls = latest.get("long_short_ratio", 1)
    ls_score = 0
    if ls > 1.8 or ls < 0.55:
        ls_score = 1
        if (ls > 2.0 and latest.get("price_change_pct", 0) > -1) or \
           (ls < 0.45 and latest.get("price_change_pct", 0) < 1):
            ls_score = 2
    signals.append({
        "name": "多空比极端",
        "score": ls_score,
        "max": 2,
        "detail": f"LS {ls:.2f}",
    })
    
    # 9. Taker翻转
    taker = latest.get("taker_buy_sell_ratio", latest.get("taker_volume", {}).get("buy_sell_ratio", 0.5))
    taker_score = 0
    if taker < 0.6 or taker > 1.4:
        taker_score = 1  # 偏向
        if (taker < 0.5 and price < vwap) or (taker > 1.5 and price > vwap):
            taker_score = 2  # 确认偏
    signals.append({
        "name": "Taker翻转",
        "score": taker_score,
        "max": 2,
        "detail": f"Taker {taker:.2f}",
    })
    
    # 10. CVD吸收
    absorption = _safe_dict(data, "cvd_absorption")
    abs_score = 2 if absorption.get("active") else 0
    signals.append({
        "name": "CVD吸收",
        "score": abs_score,
        "max": 2,
        "detail": absorption.get("detail", "无"),
    })
    
    # 11. 量能爆发
    vol = latest.get("volume_change_pct", 0)
    vol_score = 0
    if abs(vol) > 50:
        vol_score = 1
        if abs(vol) > 100:
            vol_score = 2
    signals.append({
        "name": "量能爆发",
        "score": vol_score,
        "max": 2,
        "detail": f"量变 {vol:+.0f}%",
    })
    
    # 12. OB支撑/阻力
    ob = _safe_dict(data, "order_block")
    ob_score = 1 if ob.get("near") else 0
    signals.append({
        "name": "OB支撑/阻力",
        "score": ob_score,
        "max": 1,
        "detail": ob.get("detail", ""),
    })
    
    # 13. EMA交叉
    ema = _safe_dict(data, "ema_cross")
    ema_score = 1 if ema.get("cross") else 0
    signals.append({
        "name": "EMA交叉",
        "score": ema_score,
        "max": 1,
        "detail": ema.get("type", ""),
    })
    
    # 14. 三源一致
    tsa = _safe_dict(data, "three_source_align")
    tsa_score = 2 if tsa.get("aligned") else 0
    signals.append({
        "name": "三源一致",
        "score": tsa_score,
        "max": 2,
        "detail": tsa.get("detail", ""),
    })
    
    total = sum(s["score"] for s in signals)
    max_possible = sum(s["max"] for s in signals)
    
    # 汇聚判定
    active_signals = [s for s in signals if s["score"] >= s["max"] * 0.75]  # 活跃信号(75%权重以上)
    converging = [s["name"] for s in active_signals if s["score"] >= 1]
    
    # 等级
    if total >= max_possible * 0.7:
        level = "极高"
    elif total >= max_possible * 0.45:
        level = "高"
    elif total >= max_possible * 0.25:
        level = "中"
    else:
        level = "低"
    
    high_prob = total >= 8 and len(converging) >= 3
    
    return {
        "total": total,
        "max_possible": max_possible,
        "level": level,
        "high_probability": high_prob,
        "signals": signals,
        "converging_signals": converging,
        "signal_count": len(converging),
        "score_ratio": round(total / max_possible, 2) if max_possible > 0 else 0,
        "timestamp": datetime.now(TZ).strftime("%H:%M:%S"),
    }


def interpret(score_result):
    """评分结果可读化。"""
    lines = [f"汇聚评分 {score_result['total']}/{score_result['max_possible']} · {score_result['level']}"]
    if score_result["high_probability"]:
        lines.append(f"⭐ 高概率 — {score_result['signal_count']}信号汇聚")
    for s in score_result["signals"]:
        if s["score"] > 0:
            lines.append(f"  {s['name']} +{s['score']} {s.get('detail', '')}")
    return "\n".join(lines)


if __name__ == "__main__":
    result = score_all()
    print(interpret(result))
    print(json.dumps(result, indent=2, ensure_ascii=False))
