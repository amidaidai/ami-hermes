#!/usr/bin/env python3
"""
棠溪 · 仓位计算引擎 v2.0
对接 risk_constitution v2.0 宪法值（社区2026共识）
输入：多模型引擎输出 + 宪法参数
输出：仓位大小建议 + 理由
集成到 multi_model_engine 输出尾部
"""

from typing import Dict, Optional
from pathlib import Path
import json

ROOT = Path("D:/Hermes agent")

# ═══════════════════ 账户参数（从宪法/实盘动态读取） ═══════════════════

def _get_account_balance() -> float:
    """从 equity_curve.json 读取实盘余额，缺失回退 67.52"""
    try:
        eq = ROOT / "data" / "equity_curve.json"
        if eq.exists():
            return float(json.loads(eq.read_text(encoding="utf-8")).get("current_balance", 67.52))
    except Exception:
        pass
    return 67.52


def _get_leverage(symbol: str = "BTCUSDT") -> int:
    """按品种返回杠杆"""
    sym = symbol.upper()
    if "XAU" in sym:
        return 1000
    if sym in ("BTCUSDT", "ETHUSDT"):
        return 100
    return 20


def _get_max_risk_usd(symbol: str = "BTCUSDT", atr_pct: float = 0) -> float:
    """从宪法获取自适应单笔风险"""
    try:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from risk_constitution import adaptive_risk_usd
        balance = _get_account_balance()
        r = adaptive_risk_usd(account_balance=balance, atr_pct=atr_pct)
        return r["risk_usd"]
    except Exception:
        return 1.0  # fallback 1U（宪法 1% × 100 本金）


def position_size(
    direction: str = "",           # "偏多" / "偏空"
    global_confidence: float = 0,  # 0-1
    long_confidence: float = 0,
    short_confidence: float = 0,
    action: str = "",              # from merge_directions
    symbol: str = "BTCUSDT",       # v2.0: 新增品种参数
    entry_price: float = 0,
    stop_loss: float = 0,
    data_grade: str = "B",
    cvd_grade: str = "C",
    event_ban: bool = False,
) -> dict:
    """
    综合计算仓位大小建议
    """
    cap = _get_account_balance()
    max_risk = _get_max_risk_usd(symbol)
    leverage = _get_leverage(symbol)
    
    # 日损检查（从 risk_state.json）
    daily_loss = 0.0
    daily_limit = cap * 0.03  # 日上限 3%（社区标准）
    try:
        rs = ROOT / "data" / "risk_state.json"
        if rs.exists():
            state = json.loads(rs.read_text(encoding="utf-8"))
            daily_loss = float(state.get("daily_realized_pnl", 0))
            daily_limit = float(state.get("max_daily_loss_usd", cap * 0.03))
    except Exception:
        pass
    
    remaining_daily = max(0, daily_limit - daily_loss)
    max_risk = min(max_risk, remaining_daily)
    
    # ── 决策树 ──
    reasons = []
    risk_usd = 0
    size_pct = 0
    tier = "禁止"
    
    if event_ban:
        reasons.append("事件禁做")
        return _result(tier, risk_usd, size_pct, reasons)
    
    if max_risk <= 0:
        reasons.append(f"日损已达上限 {daily_loss}/{daily_limit}U")
        return _result("禁止", 0, 0, reasons)
    
    if direction in ("方向不明/震荡", ""):
        reasons.append("方向不明·不做")
        return _result("等待", 0, 0, reasons)
    
    # 正常计算
    is_long = "多" in direction
    model_confidence = long_confidence if is_long else short_confidence
    
    # 数据质量降权
    quality_mult = 1.0
    if data_grade == "C":
        quality_mult *= 0.5
        reasons.append("数据C级·仓位减半")
    if cvd_grade == "C":
        quality_mult *= 0.8
        reasons.append("CVD C级·仓位打8折")
    
    # 置信→仓位映射
    if model_confidence >= 0.8 and global_confidence >= 0.7:
        risk_usd = round(max_risk * quality_mult, 1)  # 高置信用满
        tier = "常规"
    elif model_confidence >= 0.6 and global_confidence >= 0.5:
        risk_usd = round(max_risk * 0.5 * quality_mult, 1)  # 中等半仓
        tier = "半仓"
    elif model_confidence >= 0.4:
        risk_usd = round(max_risk * 0.3 * quality_mult, 1)
        tier = "轻仓"
    else:
        risk_usd = 0
        tier = "不交易"
        reasons.append(f"全局置信过低 {global_confidence:.2f}")
    
    risk_usd = min(risk_usd, remaining_daily)
    size_pct = round(risk_usd / cap * 100, 1) if cap > 0 else 0
    
    reasons.append(f"全局置信{global_confidence:.2f}·{tier}")
    
    # 止损距离检查（如果提供了入场/止损）
    position_qty = 0
    nominal = 0
    margin = 0
    actual_rr = 0
    if entry_price > 0 and stop_loss > 0 and risk_usd > 0:
        stop_dist = abs(entry_price - stop_loss)
        if stop_dist > 0:
            position_qty = round(risk_usd / stop_dist, 6)
            nominal = round(position_qty * entry_price, 2)
            margin = round(nominal / leverage, 2)
            if margin > cap:
                reasons.append(f"保证金{margin}U超本金{cap}U·降杠杆或不交易")
                risk_usd = 0
                tier = "禁止"
    
    return _result(tier, risk_usd, size_pct, reasons, position_qty, nominal, margin)


def position_advice(merged: dict, entry: float = 0, stop: float = 0,
                    data_grade: str = "B", cvd_grade: str = "C",
                    event_ban: bool = False, symbol: str = "BTCUSDT") -> dict:
    """从多模型合并结果直接计算仓位建议"""
    return position_size(
        direction=merged.get("bias", "方向不明"),
        global_confidence=merged.get("global_confidence", 0),
        long_confidence=merged.get("long_confidence", 0),
        short_confidence=merged.get("short_confidence", 0),
        action=merged.get("action", "不交易"),
        symbol=symbol,
        entry_price=entry,
        stop_loss=stop,
        data_grade=data_grade,
        cvd_grade=cvd_grade,
        event_ban=event_ban,
    )


def _result(tier, risk_usd, size_pct, reasons, qty=0, nominal=0, margin=0) -> dict:
    return {
        "tier": tier,
        "risk_usd": risk_usd,
        "size_pct_of_capital": size_pct,
        "position_qty_btc": qty,
        "nominal_usd": nominal,
        "margin_usd": margin,
        "reasons": reasons,
    }


def format_position(result: dict) -> str:
    """格式化仓位建议文本"""
    lines = []
    lines.append(f"仓位：{result['tier']} · 风险 {result['risk_usd']}U · 占比 {result['size_pct_of_capital']}%")
    if result["position_qty_btc"] > 0:
        lines.append(f"数量：{result['position_qty_btc']} BTC · 名义 {result['nominal_usd']}U · 保证金 {result['margin_usd']}U")
    if result["reasons"]:
        lines.append(f"依据：{' · '.join(result['reasons'])}")
    return "\n".join(lines)


# ═══════════════════ CLI ═══════════════════
if __name__ == "__main__":
    # Demo
    import json
    demo_merged = {
        "bias": "偏多",
        "global_confidence": 0.65,
        "long_confidence": 0.65,
        "short_confidence": 0.45,
        "action": "可交易 · 轻仓",
    }
    result = position_advice(demo_merged, entry=65200, stop=64900, event_ban=True)
    print(format_position(result))
    print()
    result2 = position_advice(demo_merged, entry=65200, stop=64900, symbol="BTCUSDT")
    print(format_position(result2))
