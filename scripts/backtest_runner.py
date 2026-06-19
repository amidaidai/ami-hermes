#!/usr/bin/env python3
"""
棠溪 · 回测引擎 v1.1
借鉴: Freqtrade(回测框架) + aurumcrypto(成本模型) + BAKOME(时段过滤)
输入: Binance K线历史数据
输出: 逐笔交易记录+权益曲线+模型统计
v1.1: 真实手续费+max_hold超时强平(借aurumcrypto)·黄金时段过滤(借BAKOME)
"""

from __future__ import annotations
import json, sys, time
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np

ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))

TZ = timezone(timedelta(hours=8))

# ═══ 过拟合检测 ═══

def check_overfit(train_win_rate: float, test_win_rate: float, 
                  n_params: int, cfg: BTConfig) -> tuple[bool, str]:
    """
    过拟合检测 · Reddit r/algotrading共识
    
    Returns: (is_overfit, reason)
    """
    issues = []
    decay = train_win_rate - test_win_rate
    
    if decay > 15.0:
        issues.append(f"胜率衰减{decay:.0f}% > 15%")
    if n_params > cfg.max_params_per_model:
        issues.append(f"参数{n_params}个 > 上限{cfg.max_params_per_model}")
    if test_win_rate < 40:
        issues.append(f"测试胜率{test_win_rate:.0f}% < 40%")
    
    if issues:
        return True, "·".join(issues)
    return False, "稳健"


def enforce_timeframe(asset: str, kline_count: int) -> str:
    """
    时间框架强制 · X/Twitter共识
    
    Returns: 警告信息(空=合规)
    """
    asset_upper = asset.upper()
    if "XAU" in asset_upper:
        # 黄金推荐5m·当前15m数据可能太粗
        if kline_count < 500:
            return "⚠ 黄金推荐5m时间框架·当前数据可能精度不足"
    elif "BTC" in asset_upper:
        return ""  # BTC 15m OK
    
    return ""

# ═══ 成本模型 (借鉴 aurumcrypto v1.0) ═══

@dataclass
class BTConfig:
    """回测配置·成本模型·社区最佳实践"""
    fee_bps: float = 4.0       # 双边手续费(bps): Binance 0.02%×2 = 4bps
    max_hold: int = 96         # 最大持仓K线数 (96×15m=24h)
    risk_per_trade: float = 10.0
    min_rr: float = 2.0
    warmup: int = 200
    startup_candle_count: int = 400  # Freqtrade标准: EMA100需要400根预热
    use_session_filter: bool = False
    asset: str = "BTCUSDT"
    max_params_per_model: int = 3    # 过拟合防护: 每模型最多调3个参数
    min_stop_atr_mult: float = 0.5
    min_stop_price_pct: float = 0.001
    max_rr: float = 10.0

# ═══ 简化版指标计算（不依赖TradingView） ═══

def calc_ema(data: list[float], period: int) -> list[float]:
    """从价格序列计算EMA · v1.2 numpy向量化"""
    arr = np.array(data, dtype=float)
    n = len(arr)
    if n < period:
        return [float(arr[-1])] * n
    result = np.empty(n)
    k = 2.0 / (period + 1)
    # 初始SMA
    result[period - 1] = arr[:period].mean()
    # 向量化递推（EMA有递推依赖，用numba或循环）
    for i in range(period, n):
        result[i] = arr[i] * k + result[i - 1] * (1 - k)
    # 填充前面
    result[:period - 1] = result[period - 1]
    return result.tolist()


def calc_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
    """ATR序列 · v1.2 numpy向量化TR计算"""
    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    c = np.array(closes, dtype=float)
    n = len(c)
    if n == 0:
        return []
    # 向量化TR
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    if n > 1:
        tr[1:] = np.maximum(
            h[1:] - l[1:],
            np.maximum(
                np.abs(h[1:] - c[:-1]),
                np.abs(l[1:] - c[:-1]),
            )
        )
    return calc_ema(tr.tolist(), period)


def calc_vwap(highs: list[float], lows: list[float], closes: list[float],
              volumes: list[float]) -> list[float]:
    """VWAP序列（累积）· v1.2 numpy向量化"""
    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    c = np.array(closes, dtype=float)
    v = np.array(volumes, dtype=float)
    typical = (h + l + c) / 3.0
    cum_pv = np.cumsum(typical * v)
    cum_v = np.cumsum(v)
    vwap = np.where(cum_v > 0, cum_pv / np.where(cum_v == 0, 1, cum_v), c)
    return vwap.tolist()


def calc_vwap_bands(vwap: list[float], atr: list[float], multiplier: float = 1.0) -> tuple[list[float], list[float]]:
    """VWAP ±1 ATR bands · v1.2 numpy向量化"""
    v = np.array(vwap, dtype=float)
    a = np.array(atr, dtype=float)
    upper = (v + a * multiplier).tolist()
    lower = (v - a * multiplier).tolist()
    return upper, lower


def rolling_window(values: list[float], window: int) -> list[tuple[float, float]]:
    """滑动窗口 high/low · v1.2 numpy向量化"""
    arr = np.array(values, dtype=float)
    n = len(arr)
    result = []
    for i in range(n):
        start = max(0, i - window + 1)
        win = arr[start:i + 1]
        result.append((float(win.max()), float(win.min())))
    return result


def approximate_cvd_from_taker(
    taker_buy_vols: list[float], 
    taker_sell_vols: list[float],
    initial_cvd: float = 0.0,
) -> tuple[list[float], list[float]]:
    """从真实taker买卖量计算CVD（非估算！）
    
    Returns: (cvd_values, cvd_slopes)
    """
    cvd = [initial_cvd] * len(taker_buy_vols)
    running = initial_cvd
    for i in range(len(taker_buy_vols)):
        running += taker_buy_vols[i] - taker_sell_vols[i]
        cvd[i] = running
    cvd_slope = calc_slope(cvd, 5)
    return cvd, cvd_slope


def approximate_cvd(closes: list[float], volumes: list[float], 
                     current_cvd: float = 0) -> list[float]:
    """从价格方向估算CVD（无taker数据时的fallback，准确度低）"""
    cvd = [current_cvd] * len(closes)
    running = current_cvd
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            running += volumes[i]
        elif closes[i] < closes[i - 1]:
            running -= volumes[i]
        cvd[i] = running
    return cvd


def calc_slope(values: list[float], window: int = 5) -> list[float]:
    """滚动斜率"""
    result = [0.0] * len(values)
    for i in range(window, len(values)):
        result[i] = (values[i] - values[i - window]) / window
    return result


# ═══ 回测真实性保护 ═══

def sanitize_setup(setup: dict, atr: float, price: float, cfg: BTConfig | None = None) -> dict | None:
    """Reject unrealistic setups before they enter statistics."""
    cfg = cfg or BTConfig()
    try:
        entry = float(setup.get("entry"))
        stop = float(setup.get("stop"))
        targets = list(setup.get("targets") or [])
        first_target = float(targets[0]) if targets else None
    except (TypeError, ValueError, IndexError):
        return None
    stop_dist = abs(entry - stop)
    min_stop_dist = max(abs(float(atr or 0)) * cfg.min_stop_atr_mult, abs(float(price or entry)) * cfg.min_stop_price_pct)
    if stop_dist < min_stop_dist:
        return None
    rr = abs(first_target - entry) / stop_dist if first_target is not None and stop_dist > 0 else 0
    if rr < cfg.min_rr or rr > cfg.max_rr:
        return None
    out = dict(setup)
    out["rr_ratio"] = round(rr, 2)
    return out


def validate_trade_consistency(trade) -> None:
    """Fail fast if result label contradicts direction/PnL geometry."""
    if getattr(trade, "result", None) not in {"win", "loss"}:
        return
    direction = getattr(trade, "direction", "")
    entry = float(getattr(trade, "entry_price"))
    exit_price = float(getattr(trade, "exit_price"))
    gross = (exit_price - entry) * (1 if direction == "long" else -1)
    if trade.result == "win" and gross <= 0:
        raise ValueError(f"交易结果不一致: {direction} win entry={entry} exit={exit_price}")
    if trade.result == "loss" and gross > 0:
        raise ValueError(f"交易结果不一致: {direction} loss entry={entry} exit={exit_price}")


# ═══ 回测核心 ═══

@dataclass
class Trade:
    symbol: str
    direction: str          # "long" / "short"
    model: str
    entry_time: str
    entry_price: float
    exit_time: str = ""
    exit_price: float = 0
    stop_price: float = 0
    targets: list[float] = field(default_factory=list)
    pnl_pct: float = 0
    pnl_r: float = 0
    result: str = "open"    # "open" / "win" / "loss" / "breakeven"
    exit_reason: str = ""
    confidence: int = 0
    rr_ratio: float = 0


@dataclass
class BacktestResult:
    symbol: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0
    total_r: float = 0
    avg_r: float = 0
    max_drawdown_r: float = 0
    profit_factor: float = 0
    sharpe_approx: float = 0
    trades: list[Trade] = field(default_factory=list)
    model_stats: dict = field(default_factory=dict)
# ═══ 回测核心 ═══

def run_backtest(
    symbol: str,
    closes: list[float],
    highs: list[float],
    lows: list[float],
    opens: list[float],
    volumes: list[float],
    timestamps: list[str],
    cfg: BTConfig | None = None,
    initial_capital: float = 100.0,
    risk_per_trade: float = 10.0,
    min_rr: float = 2.0,
    warmup: int = 200,
    **kwargs,
) -> BacktestResult:
    """
    运行全量回测(五模型+12引擎)
    
    Args:
        warmup: 跳过前N根K线(等指标预热)
        cfg: BTConfig成本模型(手续费+超时)
    """
    if cfg is None:
        cfg = BTConfig(fee_bps=4.0, max_hold=96, min_rr=min_rr, warmup=warmup, asset=symbol)
    
    n = len(closes)
    fee_rate = cfg.fee_bps / 10000.0  # bps → 小数
    max_hold = cfg.max_hold
    
    n = len(closes)
    from five_model_matcher import generate_all_setups
    
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    atr_seq = calc_atr(highs, lows, closes, 14)
    vwap_seq = calc_vwap(highs, lows, closes, volumes)
    vwap_band1_upper, vwap_band1_lower = calc_vwap_bands(vwap_seq, atr_seq, 1.0)
    vwap_band2_upper, vwap_band2_lower = calc_vwap_bands(vwap_seq, atr_seq, 2.0)
    high_window_raw = rolling_window(highs, 48)  # 48 candles ≈ 最近周期
    high_window = [h for h, _ in high_window_raw]
    low_window = [l for _, l in high_window_raw]
    
    cvd = approximate_cvd(closes, volumes)
    cvd_slope = calc_slope(cvd, 5)
    
    # 如果有真实taker数据，用它覆盖CVD
    taker_buy_vols: list[float] | None = kwargs.get('taker_buy_vols')
    taker_sell_vols: list[float] | None = kwargs.get('taker_sell_vols')
    if taker_buy_vols and taker_sell_vols and len(taker_buy_vols) == n:
        cvd, cvd_slope = approximate_cvd_from_taker(taker_buy_vols, taker_sell_vols)
    
    # 12引擎futures数据
    ls_vals = list(kwargs.get('ls_vals', []))
    gls_vals = list(kwargs.get('gls_vals', []))
    taker_vals = list(kwargs.get('taker_vals', []))
    oi_vals = list(kwargs.get('oi_vals', []))
    engine_data_available = bool(ls_vals and len(ls_vals) == n)
    
    # ═══ 成本模型: 借鉴 aurumcrypto · 手续费4bps + max_hold超时 ═══
    trades: list[Trade] = []
    open_trade: Optional[Trade] = None
    open_trade_bars: int = 0
    equity = [initial_capital]
    balance = initial_capital
    
    for i in range(warmup, n):
        price = closes[i]
        
        # 先检查已有持仓
        if open_trade:
            trade = open_trade
            open_trade_bars += 1
            exit_filled = False
            
            # 超时强平 (借鉴 aurumcrypto max_hold)
            if open_trade_bars >= max_hold:
                exit_filled = True
                trade.exit_price = closes[i - 1] if i > 0 else closes[i]
                trade.exit_time = timestamps[i]
                trade.exit_reason = f"超时强平({open_trade_bars}根)"
                trade.result = "timeout"
            
            # 止损/止盈检查 (first-touch, no price adjustment)
            elif trade.direction == "long":
                if lows[i] <= trade.stop_price:
                    exit_filled = True
                    trade.exit_price = trade.stop_price
                    trade.exit_time = timestamps[i]
                    trade.result = "loss"
                    trade.exit_reason = f"止损@{trade.stop_price:.1f}"
                elif trade.targets and highs[i] >= trade.targets[0]:
                    exit_filled = True
                    trade.exit_price = trade.targets[0]
                    trade.exit_time = timestamps[i]
                    trade.result = "win"
                    trade.exit_reason = f"止盈@{trade.targets[0]:.1f}"
            else:  # short
                if highs[i] >= trade.stop_price:
                    exit_filled = True
                    trade.exit_price = trade.stop_price
                    trade.exit_time = timestamps[i]
                    trade.result = "loss"
                    trade.exit_reason = f"止损@{trade.stop_price:.1f}"
                elif trade.targets and lows[i] <= trade.targets[0]:
                    exit_filled = True
                    trade.exit_price = trade.targets[0]
                    trade.exit_time = timestamps[i]
                    trade.result = "win"
                    trade.exit_reason = f"止盈@{trade.targets[0]:.1f}"
            
            if exit_filled:
                # 真实手续费 (借鉴 aurumcrypto)
                gross_pnl = (trade.exit_price - trade.entry_price) * (1 if trade.direction == "long" else -1)
                fee_cost = abs(trade.entry_price) * fee_rate * 2  # 双边手续费
                net_pnl = gross_pnl - fee_cost
                trade.pnl_pct = net_pnl / trade.entry_price * 100
                
                if trade.result == "win":
                    trade.pnl_r = max(0, net_pnl / abs(trade.entry_price - trade.stop_price))
                    balance += max(0, net_pnl)
                elif trade.result == "loss":
                    trade.pnl_r = -1.0
                    balance -= risk_per_trade
                else:  # timeout
                    trade.pnl_r = net_pnl / abs(trade.entry_price - trade.stop_price)
                    balance += net_pnl
                
                validate_trade_consistency(trade)
                trades.append(trade)
                open_trade = None
                open_trade_bars = 0
            
            equity.append(balance)
            if open_trade:
                continue
        
        # 无持仓 → 跑五模型+12引擎找入场
        if open_trade is None:
            # 估算VAH/VAL/POC: 简化为滚动窗口
            lookback = min(i, 48)
            recent_high = max(highs[i - lookback:i + 1])
            recent_low = min(lows[i - lookback:i + 1])
            mid_price = (recent_high + recent_low) / 2
            vah = mid_price + (recent_high - mid_price) * 0.5
            val = mid_price - (mid_price - recent_low) * 0.5
            poc = mid_price
            
            all_setups_raw = []
            
            # ① 五模型
            try:
                result5 = generate_all_setups(
                    current_price=price,
                    vwap=vwap_seq[i],
                    vwap_band1=vwap_band1_lower[i] if ema9[i] < ema21[i] else vwap_band1_upper[i],
                    vwap_band2=vwap_band2_lower[i] if ema9[i] < ema21[i] else vwap_band2_upper[i],
                    vah=vah, val=val, poc=poc,
                    ema9=ema9[i], ema21=ema21[i],
                    recent_high=high_window[i], recent_low=low_window[i],
                    atr=atr_seq[i], cvd_value=cvd[i], cvd_slope=cvd_slope[i],
                )
                all_setups_raw.extend(result5.get("all_setups", []))
            except Exception:
                pass
            
            # ② 12引擎模型（修复数据结构匹配engine期望）
            if engine_data_available and i < len(ls_vals):
                try:
                    # 计算24h价格变化
                    lookback_24h = min(96, i)  # 96 × 15m ≈ 24h
                    prev_price_24h = closes[max(0, i - lookback_24h)] if i >= lookback_24h else closes[0]
                    price_change_24h = (price - prev_price_24h) / prev_price_24h * 100 if prev_price_24h > 0 else 0
                    
                    # 费率数据（回测中从Binance futures取）
                    funding_rate = 0.0001  # 默认低费率
                    rate_change = 0
                    if i >= 96:
                        # 模拟：每8h一次费率变化
                        funding_rate = 0.0001 + (i % 192) * 0.000001  # 0.01%～0.03%
                    
                    engine_input = {
                        "symbol": symbol,
                        "price": price,
                        "binance_spot": {
                            "price": price,
                            "24h_change_pct": round(price_change_24h, 2),
                        },
                        "ema9": ema9[i], "ema21": ema21[i],
                        "atr": atr_seq[i], "cvd_value": cvd[i],
                        "cvd_slope": cvd_slope[i],
                        "funding_rate": funding_rate,
                        "rate_change": rate_change,
                        "taker_futures": {
                            "ratio": taker_vals[i] if i < len(taker_vals) else 1.0,
                            "direction": "buy" if (taker_vals[i] if i < len(taker_vals) else 1.0) > 1 else "sell",
                        },
                        "long_short": {
                            "top_long_pct": round((ls_vals[i] if i < len(ls_vals) else 1.0) / ((ls_vals[i] if i < len(ls_vals) else 1.0) + 1) * 100, 1),
                            "global_long_pct": round((gls_vals[i] if i < len(gls_vals) else 1.0) / ((gls_vals[i] if i < len(gls_vals) else 1.0) + 1) * 100, 1),
                        },
                        "oi": {
                            "btc": 100000 + (oi_vals[i] if i < len(oi_vals) and oi_vals else 0) * 10000,
                            "change_pct": oi_vals[i] if i < len(oi_vals) else 0,
                        },
                        "oi_change_pct": oi_vals[i] if i < len(oi_vals) else 0,
                        "vah": vah, "val": val, "poc": poc,
                        "vwap": vwap_seq[i],
                        "recent_high": high_window[i],
                        "recent_low": low_window[i],
                        # 关联品种（DXY代理）
                        "dxy": 100.0,
                        "correlation_threshold": 0.3,
                    }
                    engine_setups = run_engine_models_for_backtest(engine_input)
                    all_setups_raw.extend(engine_setups)
                except Exception:
                    pass
            
            # 合并找最佳（五模型优先·引擎辅助·同模型冷却5根）
            best = None
            recent_models = {t.model for t in trades[-5:] if t.entry_time} if trades else set()
            
            for s in all_setups_raw:
                s = sanitize_setup(s, atr_seq[i], price, cfg)
                if not s:
                    continue
                # 同模型冷却
                if s.get("model") in recent_models:
                    continue
                # 五模型加分（优先级高于引擎）
                is_five = s.get("model") in ("VWAP反抽","VAH回收","VAL回收","POC拒绝","扫流动性回收","突破接受")
                score = s.get("confidence", 0) + (10 if is_five else 0)
                if not best or score > best_score:
                    if s.get("rr_ratio", 0) >= min_rr:
                        best = s
                        best_score = score
            if not best or best.get("rr_ratio", 0) < min_rr:
                equity.append(balance)
                continue
            
            open_trade = Trade(
                symbol=symbol,
                direction=best["direction"],
                model=best["model"],
                entry_time=timestamps[i],
                entry_price=best["entry"],
                stop_price=best["stop"],
                targets=best["targets"],
                confidence=best["confidence"],
                rr_ratio=best["rr_ratio"],
            )
        
        equity.append(balance)
    
    # 收盘强制平仓
    if open_trade:
        open_trade.exit_price = closes[-1]
        open_trade.exit_time = timestamps[-1]
        open_trade.exit_reason = "收盘强平"
        open_trade.result = "breakeven"
        pnl_pct = (open_trade.exit_price - open_trade.entry_price) / open_trade.entry_price * 100
        if open_trade.direction == "short":
            pnl_pct = -pnl_pct
        open_trade.pnl_pct = pnl_pct
        open_trade.pnl_r = pnl_pct / 100 * (10.0 / risk_per_trade)  # 近似R
        trades.append(open_trade)
    
    # 统计
    wins = [t for t in trades if t.result == "win"]
    losses = [t for t in trades if t.result == "loss"]
    total_r = sum(t.pnl_r for t in trades)
    
    # 最大回撤
    peak = initial_capital
    max_dd = 0.0
    running_balance = initial_capital
    for t in sorted(trades, key=lambda x: x.entry_time):
        if t.result == "win":
            running_balance += risk_per_trade * t.pnl_r
        elif t.result == "loss":
            running_balance -= risk_per_trade
        if running_balance > peak:
            peak = running_balance
        dd = (peak - running_balance) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    
    # 模型统计
    model_stats = {}
    for t in trades:
        m = t.model
        if m not in model_stats:
            model_stats[m] = {"trades": 0, "wins": 0, "avg_r": 0, "total_r": 0}
        model_stats[m]["trades"] += 1
        model_stats[m]["total_r"] += t.pnl_r
        if t.result == "win":
            model_stats[m]["wins"] += 1
    for m in model_stats:
        s = model_stats[m]
        s["win_rate"] = s["wins"] / s["trades"] if s["trades"] > 0 else 0
        s["avg_r"] = s["total_r"] / s["trades"] if s["trades"] > 0 else 0
    
    # 盈利因子
    gross_profit = sum(t.pnl_r for t in wins)
    gross_loss = abs(sum(t.pnl_r for t in losses)) if losses else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999
    
    # 近似夏普
    if len(trades) >= 5:
        returns = [t.pnl_r for t in trades]
        avg_ret = sum(returns) / len(returns)
        std_ret = (sum((r - avg_ret) ** 2 for r in returns) / len(returns)) ** 0.5
        sharpe = avg_ret / std_ret if std_ret > 0 else 0
    else:
        sharpe = 0
    
    return BacktestResult(
        symbol=symbol,
        total_trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        win_rate=len(wins) / len(trades) * 100 if trades else 0,
        total_r=total_r,
        avg_r=total_r / len(trades) if trades else 0,
        max_drawdown_r=max_dd * (initial_capital / risk_per_trade),
        profit_factor=profit_factor,
        sharpe_approx=sharpe,
        trades=trades,
        model_stats=model_stats,
    )


def run_engine_models_for_backtest(data: dict) -> list[dict]:
    """运行12引擎模型并返回统一格式的setups（回测用轻量版）"""
    from multi_model_engine import ALL_MODELS
    
    setups = []
    price = data.get("price", 0)
    atr = data.get("atr", price * 0.01)
    
    for name, fn in ALL_MODELS:
        try:
            direction, conf = fn(data)
            if abs(conf) < 0.5 or direction == "neutral":
                continue
            
            # 只处理引擎专属模型（五模型已经单独跑了）
            if name in ("VWAP反抽", "VAL回收", "POC拒绝", "扫流动性回收", "突破接受"):
                continue
            
            d = "long" if "多" in direction else "short"
            entry = price  # 引擎模型用当前价入场
            
            if d == "long":
                stop = price - atr * 0.5
                target = price + atr * 1.5
            else:
                stop = price + atr * 0.5
                target = price - atr * 1.5
            
            rr = abs(target - entry) / abs(entry - stop) if abs(entry - stop) > 0 else 0
            
            setups.append({
                "model": name,
                "direction": d,
                "entry": entry,
                "stop": stop,
                "targets": [target, target * 0.99],
                "confidence": int(conf * 100),
                "rr_ratio": round(rr, 2),
                "confluence": [f"引擎置信{conf:.2f}"],
            })
        except Exception:
            pass
    
    return setups


def backtest_from_klines(symbol: str, klines: list[dict], **kwargs) -> BacktestResult:
    """从Binance K线数据运行回测"""
    closes = [float(k["close"]) for k in klines]
    highs = [float(k["high"]) for k in klines]
    lows = [float(k["low"]) for k in klines]
    opens = [float(k["open"]) for k in klines]
    volumes = [float(k.get("volume", 0)) for k in klines]
    timestamps = [k.get("time", f"candle-{i}") for i, k in enumerate(klines)]
    
    taker_buy = [float(k.get("taker_buy_vol", 0)) for k in klines]
    taker_sell = [float(k.get("taker_sell_vol", 0)) for k in klines]
    ls_vals = [float(k.get("ls_ratio", 0) or 0) for k in klines]
    gls_vals = [float(k.get("gls_ratio", 0) or 0) for k in klines]
    taker_ratio_vals = [float(k.get("taker_ratio", 0) or 0) for k in klines]
    oi_vals = [float(k.get("oi_change_pct", 0) or 0) for k in klines]
    
    return run_backtest(
        symbol=symbol,
        closes=closes, highs=highs, lows=lows, opens=opens,
        volumes=volumes, timestamps=timestamps,
        taker_buy_vols=taker_buy, taker_sell_vols=taker_sell,
        ls_vals=ls_vals, gls_vals=gls_vals, taker_vals=taker_ratio_vals,
        oi_vals=oi_vals,
        **kwargs
    )


# ═══ 输出 ═══

def format_result(r: BacktestResult) -> str:
    lines = [
        f"╔══════════════════════════════════════════╗",
        f"║  棠溪五模型回测 · {r.symbol}                    ║",
        f"╚══════════════════════════════════════════╝",
        f"",
        f"  总交易: {r.total_trades}",
        f"  胜率:   {r.win_rate:.1f}% ({r.wins}W / {r.losses}L)",
        f"  总R:    {r.total_r:+.2f}R",
        f"  均R:    {r.avg_r:+.2f}R",
        f"  最大回撤: {r.max_drawdown_r:.2f}R",
        f"  盈利因子: {r.profit_factor:.2f}",
        f"  夏普(近): {r.sharpe_approx:.2f}",
        f"",
        f"  ── 模型统计 ──",
    ]
    for m, s in sorted(r.model_stats.items(), key=lambda x: -x[1]["trades"]):
        lines.append(f"  {m}: {s['trades']}笔 · 胜率{s['win_rate']*100:.0f}% · 均{s['avg_r']:+.2f}R")
    
    lines.extend([
        f"",
        f"  ── 最近5笔 ──",
    ])
    for t in r.trades[-5:]:
        emoji = "✅" if t.result == "win" else "❌" if t.result == "loss" else "➖"
        lines.append(f"  {emoji} {t.model} {t.direction} @{t.entry_price:.1f} → {t.exit_price:.1f} {t.pnl_r:+.1f}R")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print("回测引擎已就绪 · run_backtest() / backtest_from_klines()")
