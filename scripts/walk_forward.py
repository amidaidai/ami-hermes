#!/usr/bin/env python3
"""
棠溪 · Walk-Forward 验证 v1.0
借鉴: Freqtrade社区黄金标准 · Reddit r/algotrading置顶共识
三段分割: 训练集(60%)→验证集(20%)→测试集(20%)
"""

from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))

TZ = timezone(timedelta(hours=8))


@dataclass
class WFSplit:
    """Walk-Forward数据分割"""
    train_start: int
    train_end: int
    val_start: int
    val_end: int
    test_start: int
    test_end: int


@dataclass
class WFResult:
    """Walk-Forward验证结果"""
    train_metrics: dict = field(default_factory=dict)
    val_metrics: dict = field(default_factory=dict)
    test_metrics: dict = field(default_factory=dict)
    overfit_score: float = 0.0  # 越高越差
    is_overfit: bool = False
    recommendation: str = ""


def split_data(n: int, train_pct: float = 0.6, val_pct: float = 0.2) -> WFSplit:
    """
    三段分割: 训练60% · 验证20% · 测试20%
    
    时序数据不可随机打乱 — 严格按时间顺序
    """
    train_end = int(n * train_pct)
    val_end = int(n * (train_pct + val_pct))
    
    return WFSplit(
        train_start=0,
        train_end=train_end,
        val_start=train_end,
        val_end=val_end,
        test_start=val_end,
        test_end=n,
    )


def walk_forward_validate(
    symbol: str,
    closes: list[float],
    highs: list[float],
    lows: list[float],
    opens: list[float],
    volumes: list[float],
    timestamps: list[str],
    cfg,
    risk_per_trade: float = 10.0,
    train_pct: float = 0.6,
    val_pct: float = 0.2,
    **kwargs,
) -> WFResult:
    """
    Walk-Forward验证 · 社区黄金标准
    
    流程:
    ① 训练集跑回测 → 调参
    ② 验证集跑回测 → 选最优参数
    ③ 测试集跑回测 → 唯一可信结果
    
    Returns: WFResult with overfit assessment
    """
    n = len(closes)
    split = split_data(n, train_pct, val_pct)
    
    from backtest_runner import run_backtest, BacktestResult
    
    # ① 训练集
    result_train = run_backtest(
        symbol=symbol,
        closes=closes[split.train_start:split.train_end],
        highs=highs[split.train_start:split.train_end],
        lows=lows[split.train_start:split.train_end],
        opens=opens[split.train_start:split.train_end],
        volumes=volumes[split.train_start:split.train_end],
        timestamps=timestamps[split.train_start:split.train_end],
        cfg=cfg, risk_per_trade=risk_per_trade,
        **kwargs,
    )
    
    # ② 验证集
    result_val = run_backtest(
        symbol=symbol,
        closes=closes[split.val_start:split.val_end],
        highs=highs[split.val_start:split.val_end],
        lows=lows[split.val_start:split.val_end],
        opens=opens[split.val_start:split.val_end],
        volumes=volumes[split.val_start:split.val_end],
        timestamps=timestamps[split.val_start:split.val_end],
        cfg=cfg, risk_per_trade=risk_per_trade,
        **kwargs,
    )
    
    # ③ 测试集 (唯一可信)
    result_test = run_backtest(
        symbol=symbol,
        closes=closes[split.test_start:split.test_end],
        highs=highs[split.test_start:split.test_end],
        lows=lows[split.test_start:split.test_end],
        opens=opens[split.test_start:split.test_end],
        volumes=volumes[split.test_start:split.test_end],
        timestamps=timestamps[split.test_start:split.test_end],
        cfg=cfg, risk_per_trade=risk_per_trade,
        **kwargs,
    )
    
    # 过拟合检测
    train_win = result_train.win_rate
    val_win = result_val.win_rate
    test_win = result_test.win_rate
    
    # 过拟合分: 训练→验证→测试胜率衰减越大=越过拟合
    decay_val = max(0, train_win - val_win)
    decay_test = max(0, val_win - test_win)
    overfit_score = decay_val * 0.6 + decay_test * 0.4
    
    is_overfit = overfit_score > 15.0  # 胜率衰减>15%=过拟合
    
    if is_overfit:
        recommendation = "❌ 严重过拟合 — 减少模型参数·加正则化·扩大训练集"
    elif overfit_score > 8.0:
        recommendation = "⚠ 轻度过拟合 — 考虑减少特征数量"
    elif test_win >= 50:
        recommendation = "✅ 策略稳健 — 样本外表现良好"
    else:
        recommendation = "⚠ 策略胜率不足 — 重新评估入场条件"
    
    return WFResult(
        train_metrics={
            "trades": result_train.total_trades,
            "win_rate": result_train.win_rate,
            "avg_r": result_train.avg_r,
            "sharpe": result_train.sharpe_approx,
        },
        val_metrics={
            "trades": result_val.total_trades,
            "win_rate": result_val.win_rate,
            "avg_r": result_val.avg_r,
            "sharpe": result_val.sharpe_approx,
        },
        test_metrics={
            "trades": result_test.total_trades,
            "win_rate": result_test.win_rate,
            "avg_r": result_test.avg_r,
            "sharpe": result_test.sharpe_approx,
        },
        overfit_score=overfit_score,
        is_overfit=is_overfit,
        recommendation=recommendation,
    )


def format_wf_result(r: WFResult) -> str:
    """格式化Walk-Forward结果"""
    lines = [
        "╔══════════════════════════════════════════╗",
        "║  Walk-Forward 验证 · 社区黄金标准          ║",
        "╚══════════════════════════════════════════╝",
        "",
        f"  {'阶段':<8} {'交易':>6} {'胜率':>8} {'均R':>8} {'夏普':>8}",
        f"  {'─'*8} {'─'*6} {'─'*8} {'─'*8} {'─'*8}",
        f"  {'训练集(60%)':<8} {r.train_metrics['trades']:>5}  {r.train_metrics['win_rate']:>7.1f}% {r.train_metrics['avg_r']:>+7.2f}R {r.train_metrics['sharpe']:>7.2f}",
        f"  {'验证集(20%)':<8} {r.val_metrics['trades']:>5}  {r.val_metrics['win_rate']:>7.1f}% {r.val_metrics['avg_r']:>+7.2f}R {r.val_metrics['sharpe']:>7.2f}",
        f"  {'测试集(20%)':<8} {r.test_metrics['trades']:>5}  {r.test_metrics['win_rate']:>7.1f}% {r.test_metrics['avg_r']:>+7.2f}R {r.test_metrics['sharpe']:>7.2f}",
        "",
        f"  过拟合分: {r.overfit_score:.1f} ({'>15%=过拟合' if r.is_overfit else '<15%=稳健'})",
        f"  判定: {r.recommendation}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print("Walk-Forward验证模块就绪 · walk_forward_validate()")
