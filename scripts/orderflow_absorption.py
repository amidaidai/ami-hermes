#!/usr/bin/env python3
"""
棠溪 · 订单流吸收/消耗检测 v1.0
基于 Bookmap 2026 社区共识：CVD 吸收 + 冰山水 + Stop Run 预警

检测模式:
  1. CVD 吸收 — 价格不动但 CVD 显著移动（隐藏买卖压力）
  2. 量价背离 — 价格新高但 CVD 新低（假突破预警）
  3. 成交量凝聚 — 高量区价格未突破（支撑/阻力吞噬）
  4. Stop Run 预警 — 吸收后可能的方向爆发

用法:
  from orderflow_absorption import detect_absorption
  result = detect_absorption(symbol="BTCUSDT", price=64450, cvd_data=cvd_dict)
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"


def detect_absorption(
    symbol: str,
    current_price: float,
    cvd_direction: str = "?",
    cvd_quality: str = "C",
    price_change_5m_pct: float = 0.0,
    volume_ratio: float = 1.0,  # current vol / avg vol
    key_level_proximity: float = 1.0,  # 距最近关键位的 ATR 倍数
) -> dict:
    """
    Bookmap 式检测：吸收/消耗/凝聚/假突破
    
    Returns:
        {
            "absorption_detected": bool,
            "pattern": str,           # 吸收/消耗/凝聚/正常
            "stop_run_risk": str,     # 高/中/低/无
            "direction_bias": str,    # 偏多/偏空/中性
            "confidence": int,        # 0-100
            "signals": list[str],     # 中文信号描述
        }
    """
    signals = []
    absorption = False
    pattern = "正常"
    stop_run = "低"
    bias = "中性"
    conf = 0
    
    # ═══ 模式1: CVD 吸收 ═══
    # 价格变化 < 0.3% 但 CVD 方向明确 = 隐藏买卖压力
    if abs(price_change_5m_pct) < 0.003 and cvd_direction in ("买", "卖"):
        if cvd_quality == "A":
            conf += 30
        else:
            conf += 15
        
        if cvd_direction == "买":
            signals.append(f"CVD买盘吸收·价格仅{price_change_5m_pct:+.2%}·隐藏买压在`{current_price}`附近")
            bias = "偏多"
        else:
            signals.append(f"CVD卖盘吸收·价格仅{price_change_5m_pct:+.2%}·隐藏卖压在`{current_price}`附近")
            bias = "偏空"
        
        pattern = "吸收"
        absorption = True
    
    # ═══ 模式2: 量价背离（假突破预警）═══
    # 社区共识：价格HH但CVD LH = 熊背离·假突破风险
    if abs(price_change_5m_pct) > 0.005 and cvd_direction in ("买", "卖"):
        # 价格上涨 + CVD卖出 = 熊背离
        if price_change_5m_pct > 0 and cvd_direction == "卖":
            signals.append(f"量价背离·价格{price_change_5m_pct:+.2%}但CVD卖盘·假突破风险")
            conf += 20
            if not pattern == "吸收":
                pattern = "背离"
        # 价格下跌 + CVD买入 = 牛背离
        elif price_change_5m_pct < 0 and cvd_direction == "买":
            signals.append(f"量价背离·价格{price_change_5m_pct:+.2%}但CVD买盘·假跌破可能")
            conf += 20
            if not pattern == "吸收":
                pattern = "背离"
    
    # ═══ 模式3: 成交量凝聚 = 冰山水 ═══
    # 超额成交量 + 价格未突破关键位 = 吸收/消耗
    if volume_ratio > 1.5 and key_level_proximity < 0.5:
        signals.append(f"高量凝聚·量比{volume_ratio:.1f}×·距关键位{key_level_proximity:.1f}ATR·冰山吸收可能")
        conf += 25
        pattern = "吸收" if not absorption else pattern
        absorption = True
    
    # ═══ 模式4: Stop Run 预警 ═══
    if absorption and key_level_proximity < 0.3:
        stop_run = "高"
        signals.append("⚠ 吸收+紧贴关键位·Stop Run爆发概率高")
        conf += 15
    elif absorption and key_level_proximity < 0.7:
        stop_run = "中"
    
    # ═══ 综合判定 ═══
    conf = min(100, conf)
    
    return {
        "absorption_detected": absorption,
        "pattern": pattern,
        "stop_run_risk": stop_run,
        "direction_bias": bias,
        "confidence": conf,
        "signals": signals,
        "summary": " · ".join(signals) if signals else "订单流正常·无明显吸收/背离信号",
    }


def absorption_line(symbol: str, current_price: float,
                    cvd_data: Optional[dict] = None) -> str:
    """一行式吸收检测文本（嵌入分析卡博弈段）"""
    # 获取 CVD
    if cvd_data is None:
        try:
            from cvd_aggtrades import get_cvd_aggtrades
            cvd_data = get_cvd_aggtrades(symbol, limit=500)
        except:
            cvd_data = {}
    
    cvd_dir = cvd_data.get("direction", "?")
    cvd_qual = cvd_data.get("quality", "C")
    
    # 获取价格变化（从 snapshot）
    try:
        snap = DATA / f"source_snapshot_{symbol}.json"
        if snap.exists():
            d = json.loads(snap.read_text(encoding="utf-8"))
            chg = d.get("24h_change_pct", 0) / 100  # 近似 5m
        else:
            chg = 0.0
    except:
        chg = 0.0
    
    r = detect_absorption(symbol, current_price, cvd_dir, cvd_qual, chg)
    
    if r["absorption_detected"]:
        return f"订单流吸收·{r['pattern']}·{r['direction_bias']}·StopRun{r['stop_run_risk']} | {r['summary']}"
    return f"订单流正常·无异常吸收 | {r['summary']}"


# ═══ CLI ═══
if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    px = float(sys.argv[2]) if len(sys.argv) > 2 else 64450
    
    # Demo: simulate CVD data
    demo_cvd = {"direction": "买", "quality": "A"}
    r = detect_absorption(sym, px, demo_cvd["direction"], demo_cvd["quality"],
                          price_change_5m_pct=0.001, volume_ratio=1.8,
                          key_level_proximity=0.3)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    print()
    print(absorption_line(sym, px, demo_cvd))
