#!/usr/bin/env python3
"""
棠溪 · 多资产相关性矩阵 v1.0
社区2026共识：多策略/多资产同向 = 组合级风险失控

功能:
  1. BTC vs XAU 滚动相关性（7d/30d）
  2. 当前相关性体制判决（正相关/负相关/独立）
  3. 多资产头寸风险调整倍数

用法:
  python scripts/correlation_matrix.py          # 打印当前状态
  python scripts/correlation_matrix.py --json   # JSON输出
"""

import json, sys, os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
CORR_FILE = DATA / "correlation_state.json"


def load_price_series(symbol: str, lookback_days: int = 30) -> list[float]:
    """从 snapshot 或 klines 加载价格序列"""
    prices = []
    
    # 优先从 source_snapshot 目录读历史
    snap_dir = DATA / "source_snapshots"
    if snap_dir.exists():
        today = datetime.now(TZ).strftime("%Y-%m-%d")
        today_dir = snap_dir / today
        if today_dir.exists():
            files = sorted(today_dir.glob(f"{symbol}-*.json"))
            for f in files[-200:]:
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    px = d.get("prices", {}).get("primary") or d.get("price")
                    if px and float(px) > 0:
                        prices.append(float(px))
                except:
                    continue
    
    # 回退：用实时价格做最小序列
    if not prices:
        snap = DATA / f"source_snapshot_{symbol}.json"
        if snap.exists():
            try:
                d = json.loads(snap.read_text(encoding="utf-8"))
                px = d.get("prices", {}).get("primary") or d.get("price")
                if px and float(px) > 0:
                    # 从24h高低估算简单序列
                    hi = d.get("high") or (float(px) * 1.02)
                    lo = d.get("low") or (float(px) * 0.98)
                    prices = [float(lo), float(px), float(hi)]
            except:
                pass
    
    return prices


def pearson_r(x: list[float], y: list[float]) -> float:
    """Pearson 相关系数"""
    n = min(len(x), len(y))
    if n < 3:
        return 0.0
    
    x = x[-n:]
    y = y[-n:]
    
    mx = sum(x) / n
    my = sum(y) / n
    
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    dx = sum((xi - mx) ** 2 for xi in x)
    dy = sum((yi - my) ** 2 for yi in y)
    
    den = (dx * dy) ** 0.5
    return num / den if den > 0 else 0.0


def compute_correlation() -> dict:
    """计算 BTC vs XAU 相关性"""
    btc_prices = load_price_series("BTCUSDT", 30)
    xau_prices = load_price_series("XAUUSD", 30)
    
    if len(btc_prices) < 3 or len(xau_prices) < 3:
        return {
            "status": "data_insufficient",
            "btc_samples": len(btc_prices),
            "xau_samples": len(xau_prices),
            "correlation": 0.0,
            "regime": "未知",
            "diversification_benefit": 0.0,
        }
    
    # 全量相关
    corr_full = pearson_r(btc_prices, xau_prices)
    
    # 短期相关（后1/3样本）
    n_short = max(3, min(len(btc_prices), len(xau_prices)) // 3)
    corr_short = pearson_r(btc_prices[-n_short:], xau_prices[-n_short:])
    
    # 体制判决
    if corr_full > 0.5:
        regime = "强正相关"
        diversification = 0.1  # 几乎不分散
    elif corr_full > 0.2:
        regime = "弱正相关"
        diversification = 0.3
    elif corr_full > -0.2:
        regime = "独立/弱相关"
        diversification = 0.6
    elif corr_full > -0.5:
        regime = "弱负相关"
        diversification = 0.4  # 负相关有分散但注意方向
    else:
        regime = "强负相关"
        diversification = 0.3  # 强负相关=对冲好但要防方向反转
    
    # 体制变化检测
    trend = "稳定"
    if abs(corr_short - corr_full) > 0.3:
        trend = "转正" if corr_short > corr_full else "转负"
    
    return {
        "status": "ok",
        "time": datetime.now(TZ).isoformat(timespec="seconds"),
        "btc_samples": len(btc_prices),
        "xau_samples": len(xau_prices),
        "correlation_full": round(corr_full, 3),
        "correlation_short": round(corr_short, 3),
        "regime": regime,
        "trend": trend,
        "diversification_benefit": round(diversification, 2),
        "advice": _correlation_advice(corr_full, trend, regime),
    }


def _correlation_advice(corr: float, trend: str, regime: str) -> str:
    """根据相关性给出建议"""
    if abs(corr) < 0.2:
        return "BTC+XAU独立运行·可同时持仓·各走各的风险预算"
    if corr > 0.5:
        return f"BTC+XAU强正相关{corr=:.2f}·同时持仓视为组合风险叠加·建议减总仓30%"
    if corr < -0.5:
        return "BTC+XAU强负相关·天然对冲·一方盈利可cover另一方·但注意方向反转风险"
    if trend == "转正":
        return "相关性正在转正·注意组合风险收敛·减仓观望"
    return f"相关性{corr=:.2f}·{regime}·分散效果一般"


def multi_asset_risk_multiplier(positions: dict[str, float]) -> float:
    """
    多资产风险调整倍数
    
    Args:
        positions: {"BTCUSDT": risk_usd, "XAUUSD": risk_usd}
    
    Returns: 乘数（≤1.0），乘到每笔 risk_usd 上
    """
    if len(positions) < 2:
        return 1.0
    
    corr_state = compute_correlation()
    if corr_state["status"] != "ok":
        return 1.0
    
    corr = corr_state["correlation_full"]
    
    # 强正相关 = 组合风险加倍 → 各减30%
    if corr > 0.5:
        return 0.7
    # 弱正相关 → 各减15%
    elif corr > 0.2:
        return 0.85
    # 强负相关 = 好的分散 → 不减
    elif corr < -0.3:
        return 1.0
    # 其他 → 标准
    return 1.0


def save_correlation_state():
    """保存当前相关性状态"""
    state = compute_correlation()
    CORR_FILE.parent.mkdir(parents=True, exist_ok=True)
    CORR_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    return state


def load_correlation_state() -> dict:
    """读取缓存的相关性状态"""
    if CORR_FILE.exists():
        try:
            return json.loads(CORR_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return compute_correlation()


# ═══ CLI ═══
if __name__ == "__main__":
    if "--json" in sys.argv or "-j" in sys.argv:
        state = compute_correlation()
        print(json.dumps(state, indent=2, ensure_ascii=False))
    elif "--save" in sys.argv:
        state = save_correlation_state()
        print(f"已保存: corr={state['correlation_full']} regime={state['regime']}")
    elif "--multiplier" in sys.argv:
        bal = 67.52
        btc_risk = 0.68
        xau_risk = 0.68
        mult = multi_asset_risk_multiplier({"BTCUSDT": btc_risk, "XAUUSD": xau_risk})
        print(f"多资产风险乘数: {mult:.2f}")
        print(f"BTC调整后: {btc_risk * mult:.2f}U")
        print(f"XAU调整后: {xau_risk * mult:.2f}U")
    else:
        state = compute_correlation()
        print(f"BTC vs XAU 相关性矩阵")
        print(f"  全量相关: {state['correlation_full']}")
        print(f"  短期相关: {state['correlation_short']}")
        print(f"  体制: {state['regime']} 趋势: {state['trend']}")
        print(f"  分散效益: {state['diversification_benefit']}")
        print(f"  建议: {state['advice']}")
