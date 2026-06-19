#!/usr/bin/env python3
"""
棠溪 · 模型参数优化器 v1.0
借鉴 Freqtrade Hyperopt: 网格搜索最优入场/止损/置信参数
"""

import json, sys, itertools
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))
TZ = timezone(timedelta(hours=8))

from backtest_runner import run_backtest, BacktestResult


@dataclass
class ParamGrid:
    name: str
    values: list


def grid_search(
    symbol: str,
    closes: list[float],
    highs: list[float],
    lows: list[float],
    opens: list[float],
    volumes: list[float],
    timestamps: list[str],
    param_grids: list[ParamGrid],
    **kwargs,
) -> list[dict]:
    """
    网格搜索最优参数组合
    
    Args:
        param_grids: 参数网格列表
        kwargs: 传给 run_backtest 的固定参数
    """
    results = []
    param_names = [g.name for g in param_grids]
    param_values = [g.values for g in param_grids]
    
    total_combos = 1
    for v in param_values:
        total_combos *= len(v)
    
    best_result = None
    best_score = -999
    best_params = {}
    
    for combo in itertools.product(*param_values):
        params = dict(zip(param_names, combo))
        bt_kwargs = {**kwargs, **params}
        
        result = run_backtest(
            symbol=symbol,
            closes=closes, highs=highs, lows=lows, opens=opens,
            volumes=volumes, timestamps=timestamps,
            **bt_kwargs
        )
        
        # 评分: 总R + 胜率惩罚
        score = result.total_r
        if result.win_rate < 30:
            score -= 5
        if result.max_drawdown_r > 10:
            score -= result.max_drawdown_r * 0.5
        
        results.append({
            "params": params,
            "total_r": result.total_r,
            "win_rate": result.win_rate,
            "avg_r": result.avg_r,
            "trades": result.total_trades,
            "max_dd_r": result.max_drawdown_r,
            "score": score,
        })
        
        if score > best_score:
            best_score = score
            best_params = params
            best_result = result
    
    # 排序
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return results, best_params, best_result


def format_grid_results(results: list[dict], top_n: int = 10) -> str:
    lines = [
        "╔══════════════════════════════════════════╗",
        "║  棠溪 · 参数优化结果 (网格搜索)             ║",
        "╚══════════════════════════════════════════╝",
        "",
        f"  {'排名':<4} {'总R':>8} {'胜率':>8} {'均R':>8} {'交易':>6} {'回撤R':>8}  参数",
        f"  {'─'*4} {'─'*8} {'─'*8} {'─'*8} {'─'*6} {'─'*8}  {'─'*40}",
    ]
    for i, r in enumerate(results[:top_n]):
        params_str = " ".join(f"{k}={v}" for k, v in r["params"].items())
        lines.append(
            f"  {i+1:<4} {r['total_r']:>+8.2f} {r['win_rate']:>7.1f}% {r['avg_r']:>+7.2f} "
            f"{r['trades']:>5}  {r['max_dd_r']:>7.2f}  {params_str}"
        )
    
    if results:
        best = results[0]
        lines.extend([
            "",
            f"  🏆 最优参数: {' '.join(f'{k}={v}' for k,v in best['params'].items())}",
            f"  总R={best['total_r']:+.2f} · 胜率{best['win_rate']:.1f}% · 均R={best['avg_r']:+.2f}",
        ])
    
    return "\n".join(lines)


# ═══ 预设网格 ═══

DEFAULT_GRIDS = {
    "BTCUSDT": [
        ParamGrid("risk_per_trade", [3, 5, 10]),
        ParamGrid("min_rr", [1.5, 2.0, 2.5]),
        ParamGrid("warmup", [48, 100]),
    ],
    "XAUUSD": [
        ParamGrid("risk_per_trade", [2, 5, 10]),
        ParamGrid("min_rr", [1.5, 2.0, 2.5]),
        ParamGrid("warmup", [48, 100]),
    ],
}


if __name__ == "__main__":
    print("模型优化器已就绪 · grid_search() · DEFAULT_GRIDS")
