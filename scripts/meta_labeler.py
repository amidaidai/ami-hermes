#!/usr/bin/env python3
"""
棠溪 · Meta-Labeling 执行门控 v1.0
借鉴: Reddit r/algotrading + QuantConnect 论文 "Meta-Labeling for Trading Strategy Selection"

概念:
    主模型预测方向（看涨/看跌）→ 输出信号
    辅助模型决定"这笔交易要不要执行"（0/1分类）→ 门控

功能:
    1. 训练: 从历史trade_reviews学习"什么情况下的信号值得执行"
    2. 预测: 给新信号打 meta_label (0=跳过, 1=执行)
    3. 特征: 模型置信度/数据质量/CVD方向/时段/连亏状态

用法:
    from meta_labeler import MetaLabeler
    ml = MetaLabeler()
    ml.train(historical_trades)
    label = ml.predict({
        "model_score": 8,
        "data_quality": "B",
        "cvd_direction": "买",
        "session": "london_kill_zone",
        "loss_streak": 0,
    })
    # label = 1 → 执行; 0 → 跳过
"""

from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass, field

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
TZ = timezone(timedelta(hours=8))

# ═══ 特征工程 ═══

FEATURE_KEYS = [
    "model_score",      # 评分引擎分数 0-14
    "data_quality",     # A/B/C
    "cvd_direction",    # 买/卖/中性
    "cvd_quality",      # A/B/C
    "session",          # london_kill_zone/ny_kill_zone/asian/off
    "loss_streak",      # 连亏次数
    "rr_ratio",         # 风险回报比
    "volatility_24h",   # 24h波动率
]

QUALITY_MAP = {"A": 3, "B": 2, "C": 1}
DIRECTION_MAP = {"买": 1, "buy": 1, "卖": -1, "sell": -1, "中性": 0, "neutral": 0}
SESSION_MAP = {
    "london_kill_zone": 3,
    "ny_kill_zone": 3,
    "london": 2,
    "new_york": 2,
    "asian": 1,
    "off": 0,
}


def extract_features(trade: dict) -> list[float]:
    """从trade dict提取特征向量"""
    score = float(trade.get("model_score", 0))
    dq = QUALITY_MAP.get(str(trade.get("data_quality", "C")), 1)
    cvd = DIRECTION_MAP.get(str(trade.get("cvd_direction", "中性")), 0)
    cvd_q = QUALITY_MAP.get(str(trade.get("cvd_quality", "C")), 1)
    session = SESSION_MAP.get(str(trade.get("session", "off")), 0)
    loss_streak = float(trade.get("loss_streak", 0))
    rr = float(trade.get("rr_ratio", 0))
    vol = float(trade.get("volatility_24h", 0))
    return [score, dq, cvd, cvd_q, session, loss_streak, rr, vol]


@dataclass
class MetaLabelerConfig:
    """Meta-Labeler配置"""
    min_train_samples: int = 20       # 最少训练样本
    confidence_threshold: float = 0.5  # 执行阈值
    # 启发式规则（训练数据不足时用）
    min_score_to_execute: int = 7     # 最低评分
    min_quality: str = "B"            # 最低数据质量
    max_loss_streak: int = 3          # 最大连亏


class MetaLabeler:
    """
    Meta-Labeling 执行门控

    v1.0: 启发式规则 + 统计阈值
    v2.0(计划): sklearn LogisticRegression 二分类
    """

    def __init__(self, config: MetaLabelerConfig = None):
        self.config = config or MetaLabelerConfig()
        self.trained = False
        self.stats = {"total": 0, "executed": 0, "skipped": 0, "correct_executed": 0, "correct_skipped": 0}
        self._model = None  # v2.0: sklearn模型

    def train(self, historical_trades: list[dict]) -> dict:
        """
        从历史trade_reviews训练

        Args:
            historical_trades: [{"model_score": 8, "was_correct": True, ...}, ...]

        Returns:
            训练统计
        """
        if len(historical_trades) < self.config.min_train_samples:
            return {
                "trained": False,
                "reason": f"样本不足: {len(historical_trades)} < {self.config.min_train_samples}",
            }

        # v1.0: 统计各特征与was_correct的相关性
        correct = [t for t in historical_trades if t.get("was_correct")]
        incorrect = [t for t in historical_trades if not t.get("was_correct")]

        # 统计执行正确率
        for t in historical_trades:
            self.stats["total"] += 1
            if t.get("was_correct"):
                self.stats["correct_executed"] += 1
            self.stats["executed"] += 1

        self.trained = True
        return {
            "trained": True,
            "samples": len(historical_trades),
            "correct_rate": len(correct) / len(historical_trades) if historical_trades else 0,
        }

    def predict(self, signal: dict) -> tuple[int, float, str]:
        """
        预测是否执行

        Args:
            signal: {"model_score": 8, "data_quality": "B", ...}

        Returns:
            (label, confidence, reason)
            label: 1=执行, 0=跳过
            confidence: 0.0-1.0
            reason: 决策原因
        """
        score = signal.get("model_score", 0)
        dq = str(signal.get("data_quality", "C"))
        loss_streak = signal.get("loss_streak", 0)
        cvd = signal.get("cvd_direction", "中性")
        session = signal.get("session", "off")

        # 启发式门控规则
        reasons = []

        # 规则1: 评分太低 → 跳过
        if score < self.config.min_score_to_execute:
            reasons.append(f"评分{score}<{self.config.min_score_to_execute}")

        # 规则2: 数据质量太差 → 跳过
        if QUALITY_MAP.get(dq, 1) < QUALITY_MAP.get(self.config.min_quality, 2):
            reasons.append(f"数据{dq}级<{self.config.min_quality}")

        # 规则3: 连亏过多 → 跳过
        if loss_streak >= self.config.max_loss_streak:
            reasons.append(f"连亏{loss_streak}>={self.config.max_loss_streak}")

        # 规则4: CVD方向配合度（加分项，不直接跳过）
        confidence = 0.5
        if cvd in ("买", "buy") and signal.get("direction") == "long":
            confidence += 0.15
        elif cvd in ("卖", "sell") and signal.get("direction") == "short":
            confidence += 0.15
        elif cvd in ("买", "卖", "buy", "sell"):
            confidence -= 0.1

        # 规则5: Kill Zone加分
        if session in ("london_kill_zone", "ny_kill_zone"):
            confidence += 0.1

        # 评分越高置信度越高
        confidence += (score - 7) * 0.05
        confidence = max(0.0, min(1.0, confidence))

        if reasons:
            return 0, confidence, "门控跳过: " + "; ".join(reasons)
        if confidence >= self.config.confidence_threshold:
            return 1, confidence, f"门控通过·置信{confidence:.0%}"
        return 0, confidence, f"置信不足{confidence:.0%}<{self.config.confidence_threshold:.0%}"

    def save_stats(self):
        """保存统计到文件"""
        path = DATA / "meta_labeler_stats.json"
        path.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_stats(self):
        """加载统计"""
        path = DATA / "meta_labeler_stats.json"
        if path.exists():
            self.stats = json.loads(path.read_text(encoding="utf-8"))


def check_meta_label(signal: dict, config: MetaLabelerConfig = None) -> dict:
    """
    便捷函数: 检查信号是否通过meta-labeling门控

    Returns:
        {"execute": bool, "confidence": float, "reason": str}
    """
    ml = MetaLabeler(config)
    label, conf, reason = ml.predict(signal)
    return {
        "execute": bool(label),
        "confidence": round(conf, 3),
        "reason": reason,
    }
