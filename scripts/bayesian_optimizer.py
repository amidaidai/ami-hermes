#!/usr/bin/env python3
"""
棠溪 · 贝叶斯参数优化器 v1.0
借鉴: Freqtrade Hyperopt · 贝叶斯替代网格搜索
效率: 20次迭代≈27组合网格搜索·可扩展100+参数组合
"""

from __future__ import annotations
import json, sys, math, random
from pathlib import Path
from dataclasses import dataclass, field

ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))


@dataclass
class ParamSpace:
    """参数空间定义"""
    name: str
    low: float
    high: float
    step: float = 0.0  # 0=连续, >0=离散


@dataclass
class TrialResult:
    """单次尝试结果"""
    params: dict
    metrics: dict
    score: float


class BayesianOptimizer:
    """
    简化贝叶斯优化器 (Gaussian Process surrogate)
    
    借鉴 Hyperopt 的 TPE 算法思路:
    ① 随机采样初始化 → ② 拟合代理模型 → ③ 选最大EI点 → 重复
    """
    
    def __init__(self, param_space: list[ParamSpace], n_initial: int = 5):
        self.space = param_space
        self.n_initial = n_initial
        self.history: list[TrialResult] = []
        self.best_score = -float('inf')
        self.best_params = {}
    
    def _sample_random(self) -> dict:
        """随机采样一组参数"""
        params = {}
        for p in self.space:
            if p.step > 0:
                # 离散
                n_steps = int((p.high - p.low) / p.step) + 1
                val = p.low + random.randint(0, n_steps - 1) * p.step
            else:
                # 连续
                val = p.low + random.random() * (p.high - p.low)
            params[p.name] = round(val, 4)
        return params
    
    def _expected_improvement(self, params: dict, xi: float = 0.01) -> float:
        """
        预期改进(EI) — 简化为加权平均
        EI = E[max(f(x) - f*, 0)]
        
        简化版: 用历史数据粗糙估计
        """
        if len(self.history) < 2:
            return random.random()
        
        # 找相似参数的历史结果
        scores = []
        for trial in self.history[-10:]:
            # 加权: 参数越接近权重越高
            dist = sum((trial.params.get(k, 0) - v) ** 2 for k, v in params.items())
            weight = math.exp(-dist * 10)  # 距离衰减
            scores.append((trial.score, weight))
        
        if not scores:
            return random.random()
        
        total_weight = sum(w for _, w in scores)
        if total_weight == 0:
            return random.random()
        
        weighted_score = sum(s * w for s, w in scores) / total_weight
        improvement = weighted_score - self.best_score
        return max(0, improvement)
    
    def suggest(self) -> dict:
        """建议下一组参数"""
        if len(self.history) < self.n_initial:
            return self._sample_random()
        
        # 采样20组候选，选EI最大的
        best_params = None
        best_ei = -1
        
        for _ in range(20):
            candidate = self._sample_random()
            ei = self._expected_improvement(candidate)
            if ei > best_ei:
                best_ei = ei
                best_params = candidate
        
        return best_params if best_params else self._sample_random()
    
    def update(self, params: dict, metrics: dict, score: float):
        """记录迭代结果"""
        self.history.append(TrialResult(params=params, metrics=metrics, score=score))
        if score > self.best_score:
            self.best_score = score
            self.best_params = params


def bayesian_optimize(
    symbol: str,
    closes: list[float],
    highs: list[float],
    lows: list[float],
    opens: list[float],
    volumes: list[float],
    timestamps: list[str],
    param_space: list[ParamSpace],
    n_iter: int = 20,
    cfg=None,
    **kwargs,
) -> tuple[list[TrialResult], dict, float]:
    """
    贝叶斯优化主函数
    
    Args:
        param_space: 参数空间
        n_iter: 总迭代次数(默认20)
    
    Returns: (history, best_params, best_score)
    """
    from backtest_runner import run_backtest
    
    opt = BayesianOptimizer(param_space, n_initial=5)
    
    print(f"贝叶斯优化: {n_iter}次迭代 · {len(param_space)}个参数")
    print(f"  {'迭代':>4} {'胜率':>8} {'均R':>8} {'交易':>6}  参数")
    print(f"  {'─'*4} {'─'*8} {'─'*8} {'─'*6}  {'─'*40}")
    
    for i in range(n_iter):
        params = opt.suggest()
        
        # 运行回测
        result = run_backtest(
            symbol=symbol,
            closes=closes, highs=highs, lows=lows, opens=opens,
            volumes=volumes, timestamps=timestamps,
            cfg=cfg,
            **{**kwargs, **params},
        )
        
        # 评分 (综合R+胜率)
        score = result.total_r
        if result.win_rate < 40:
            score -= 5
        if result.max_drawdown_r > 8:
            score -= result.max_drawdown_r * 0.3
        
        # 过拟合惩罚: 交易太少或太多都扣分
        if result.total_trades < 5:
            score -= 10
        if result.total_trades > n_iter * 5:
            score -= (result.total_trades - n_iter * 5) * 0.1
        
        opt.update(params, {
            "total_r": result.total_r,
            "win_rate": result.win_rate,
            "avg_r": result.avg_r,
            "trades": result.total_trades,
            "max_dd": result.max_drawdown_r,
        }, score)
        
        if i % 5 == 0 or i == n_iter - 1:
            params_str = " ".join(f"{k}={v:.3g}" for k, v in params.items())
            print(f"  {i+1:>4} {result.win_rate:>7.1f}% {result.avg_r:>+7.2f}R {result.total_trades:>5}  {params_str}")
    
    print(f"\n  🏆 最优: " + " ".join(f"{k}={v:.3g}" for k, v in opt.best_params.items()))
    print(f"  得分: {opt.best_score:.1f}")
    
    return opt.history, opt.best_params, opt.best_score


# ═══ 预设参数空间 ═══

DEFAULT_SPACE = [
    ParamSpace("min_rr", 1.5, 3.5, 0.5),
    ParamSpace("risk_per_trade", 3, 15, 1),
    ParamSpace("warmup", 48, 400, 50),
]


if __name__ == "__main__":
    print("贝叶斯优化器就绪 · BayesianOptimizer · bayesian_optimize()")
    print(f"默认参数空间: {[(p.name, p.low, p.high) for p in DEFAULT_SPACE]}")
