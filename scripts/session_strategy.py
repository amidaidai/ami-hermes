#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
棠溪 · KillZone Session 策略引擎 v1.0
时段感知：不同时段用不同策略模型组合，动态权重调整

社区对标：ICT KillZone 策略体系
- 亚洲 (00:00-07:00 UTC / 08:00-15:00 北京时间)：范围交易 → VWAP/VAH/VAL回收
- 伦敦 (07:00-12:00 UTC / 15:00-20:00 北京时间)：突破接受 → 扫流动性 + 位移确认
- 纽约 (12:00-21:00 UTC / 20:00-05:00 北京时间)：Silver Bullet → 高波动追击
"""

from datetime import datetime, timezone, timedelta
from typing import Literal

TZ = timezone(timedelta(hours=8))  # Asia/Shanghai

# ═══════════════════════════════════════
# Session 定义
# ═══════════════════════════════════════

SESSION_ZONES = {
    "asia": {
        "name": "亚洲",
        "name_en": "Asia",
        "utc_start": 0, "utc_end": 7,
        "strategy": "range_reclaim",
        "priority_models": ["VWAP反抽", "VAL回收", "VAH回收", "POC拒绝"],
        "avoid_models": ["突破接受", "扫流动性回收"],
        "confidence_bonus": 0.05,  # 亚洲范围交易更可靠（低波动）
        "description": "区间交易·VWAP/VAH/VAL回收·防假突破",
    },
    "london": {
        "name": "伦敦",
        "name_en": "London",
        "utc_start": 7, "utc_end": 12,
        "strategy": "breakout_sweep",
        "priority_models": ["突破接受", "扫流动性回收", "M_VWAP磁吸"],
        "avoid_models": ["VAL回收"],  # 伦敦不回收区间，只做突破
        "confidence_bonus": 0.0,
        "description": "突破导向·扫流动性·位移确认",
    },
    "newyork": {
        "name": "纽约",
        "name_en": "New York",
        "utc_start": 12, "utc_end": 21,
        "strategy": "silver_bullet",
        "priority_models": ["银弹窗口", "突破接受", "Taker背离", "扫流动性回收"],
        "avoid_models": ["POC拒绝", "VAL回收"],
        "confidence_bonus": -0.05,  # 纽约波动大，需更保守
        "description": "高波动·Silver Bullet·方向突破",
    },
    "dead": {
        "name": "低波动",
        "name_en": "Dead Zone",
        "utc_start": 21, "utc_end": 24,
        "strategy": "wait",
        "priority_models": [],
        "avoid_models": ["ALL"],
        "confidence_bonus": 0.0,
        "description": "低流动性·等待·不交易",
    },
}

# KillZone 子时段
KILL_ZONES = {
    "london_open": {"utc_start": 7, "utc_end": 9, "name": "伦敦开盘", "volatility": "high"},
    "ny_open": {"utc_start": 12, "utc_end": 14, "name": "纽约开盘", "volatility": "high"},
    "london_close": {"utc_start": 15, "utc_end": 16, "name": "伦敦收盘", "volatility": "medium"},
    "asia_close": {"utc_start": 7, "utc_end": 8, "name": "亚洲收盘", "volatility": "medium"},
    "silver_bullet": {"utc_start": 14, "utc_end": 15, "name": "Silver Bullet窗", "volatility": "high"},
}


def get_current_utc_hour() -> int:
    return datetime.now(timezone.utc).hour


def get_session() -> dict:
    """返回当前时段的策略配置。"""
    hour = get_current_utc_hour()
    for key, zone in SESSION_ZONES.items():
        if zone["utc_start"] <= hour < zone["utc_end"]:
            return {**zone, "key": key}
    return {**SESSION_ZONES["dead"], "key": "dead"}


def get_active_killzone() -> dict | None:
    """返回当前活跃的 KillZone 子时段（如果处于其中）。"""
    hour = get_current_utc_hour()
    minute = datetime.now(timezone.utc).minute
    for key, kz in KILL_ZONES.items():
        if kz["utc_start"] <= hour < kz["utc_end"]:
            return {**kz, "key": key}
    return None


def model_priority_filter(model_name: str, session: dict) -> tuple[bool, float]:
    """
    检查模型在当前时段是否应激活，返回 (激活, 权重乘数)。
    
    Returns:
        (是否激活, 权重乘数: 1.0=正常, 1.1=优先, 0.0=禁用)
    """
    priority = session.get("priority_models", [])
    avoid = session.get("avoid_models", [])
    
    if "ALL" in avoid:
        return False, 0.0
    if model_name in avoid:
        return False, 0.0
    if model_name in priority:
        return True, 1.1  # 优先模型+10%权重
    return True, 1.0


def get_session_summary() -> str:
    """人类可读的当前时段摘要。"""
    session = get_session()
    kz = get_active_killzone()
    lines = [
        f"Session: {session['name']}({session['name_en']})",
        f"Strategy: {session['strategy']}",
        f"Priority: {', '.join(session['priority_models'][:3]) or '等待'}",
    ]
    if kz:
        lines.append(f"KillZone: {kz['name']} ⚡{kz['volatility']}")
    lines.append(session["description"])
    return " | ".join(lines)


# ═══════════════════════════════════════
# 噪音过滤器
# ═══════════════════════════════════════

class NoiseFilter:
    """信号噪音控制：波动率门槛 + 冷却期 + 去重"""
    
    def __init__(self):
        self._cooldowns: dict[str, float] = {}  # model_name → last_fired_ts
        self._recent_signals: set = set()  # (model, direction) dedup
    
    def should_pass(
        self,
        model_name: str,
        direction: str,
        confidence: float,
        atr_pct: float,
        session: dict,
        now_ts: float | None = None,
    ) -> tuple[bool, str]:
        """
        检查信号是否应通过噪音过滤。
        
        Returns:
            (通过, 原因)
        """
        import time
        now = now_ts or time.time()
        
        # ① 波动率门槛：0.3% ATR 以下不推送（除非 KillZone）
        kz = get_active_killzone()
        if atr_pct < 0.3 and not kz:
            return False, "低波动·ATR%<0.3%"
        
        # ② 冷却期：同模型同方向 2 小时内不重复
        signal_key = f"{model_name}:{direction}"
        last = self._cooldowns.get(signal_key, 0)
        cooldown = 3600 if confidence < 0.6 else 1800  # 弱信号冷却 1h，强信号 30min
        if now - last < cooldown:
            mins_ago = int((now - last) / 60)
            return False, f"冷却中·{mins_ago}min前已推送"
        
        # ③ 非 KillZone 时仅推送 A 级信号（conf ≥ 0.6）
        if not kz and confidence < 0.6 and session["key"] != "newyork":
            return False, "非KillZone·B级信号抑制"
        
        # 通过 → 记录
        self._cooldowns[signal_key] = now
        return True, "通过"


# 单例
_noise_filter = NoiseFilter()

def noise_check(model_name: str, direction: str, confidence: float, 
                atr_pct: float, session: dict) -> tuple[bool, str]:
    return _noise_filter.should_pass(model_name, direction, confidence, atr_pct, session)


# ═══════════════════════════════════════
# CLI 自测
# ═══════════════════════════════════════
if __name__ == "__main__":
    now = datetime.now(TZ)
    print(f"北京时间: {now.strftime('%H:%M')}")
    print(f"UTC: {get_current_utc_hour()}:00")
    print(get_session_summary())
    print()
    
    session = get_session()
    kz = get_active_killzone()
    print(f"KillZone活跃: {kz['name'] if kz else '否'}")
    print()
    for model in ["VWAP反抽", "突破接受", "银弹窗口", "POC拒绝"]:
        active, weight = model_priority_filter(model, session)
        status = "✅ 激活" if active else "❌ 禁用"
        print(f"  {model}: {status} (x{weight})")
