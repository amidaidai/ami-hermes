#!/usr/bin/env python3
"""
棠溪 · 三重障碍自动标注 v1.0
借鉴: López de Prado《Advances in Financial Machine Learning》Triple-Barrier Method
      + Springer 2025 "Meta-labeling with triple barrier"

概念:
    每个触发的 setup 设三道障碍——
      上轨 = 止盈价（take_profit）
      下轨 = 止损价（stop_loss）
      竖轨 = 时间上限（klines 长度 / max_bars）
    沿后续 K 线逐根检查，谁先被触碰决定结果：
      take_profit → was_correct=True,  result_r>0
      stop_loss   → was_correct=False, result_r<0
      timeout     → 按终盘价方向判定盈亏（部分R）

用途:
    把 trade_events.jsonl 里有 setup_id 的事件，配合后续真实 K 线
    自动标注成 trade_reviews 训练样本，回喂 meta_labeler，
    解决「68 plan : 1 review」的复盘闭环断裂。

用法:
    from triple_barrier import label_triple_barrier, derive_barriers, label_event
    r = label_triple_barrier(entry_price=100, direction="long",
                             take_profit=110, stop_loss=95, klines=bars)
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

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
TZ = timezone(timedelta(hours=8))


def derive_barriers(entry_price: float, direction: str, atr: float,
                    rr: float = 2.0, sl_atr_mult: float = 1.0) -> tuple[float, float]:
    """无显式止盈止损时，用 ATR + R:R 推导。

    止损距离 = sl_atr_mult * atr
    止盈距离 = rr * 止损距离
    返回 (take_profit, stop_loss)。
    """
    stop_dist = sl_atr_mult * float(atr)
    tp_dist = float(rr) * stop_dist
    if direction == "short":
        return entry_price - tp_dist, entry_price + stop_dist
    return entry_price + tp_dist, entry_price - stop_dist


def _bar_hl(bar) -> tuple[float, float]:
    """从 K 线行提取 (high, low)。兼容 list 和 dict。"""
    if isinstance(bar, dict):
        return float(bar.get("high")), float(bar.get("low"))
    # Binance kline: [openTime, open, high, low, close, volume, ...]
    return float(bar[2]), float(bar[3])


def _bar_close(bar) -> float:
    if isinstance(bar, dict):
        return float(bar.get("close"))
    return float(bar[4])


def label_triple_barrier(entry_price: float, direction: str,
                         take_profit: float, stop_loss: float,
                         klines: list, max_bars: int | None = None) -> dict:
    """三重障碍标注。

    Args:
        entry_price: 入场价
        direction: "long" / "short"
        take_profit: 止盈价（上轨/下轨）
        stop_loss: 止损价
        klines: 入场后的 K 线序列（含入场当根之后）
        max_bars: 竖轨（时间上限），None=用全部 klines

    Returns:
        {outcome, was_correct, result_r, exit_price, bars_held, hit_index}
        outcome ∈ {take_profit, stop_loss, timeout}
        result_r: 以止损距离为 1R 单位的盈亏倍数
    """
    entry = float(entry_price)
    tp = float(take_profit)
    sl = float(stop_loss)
    is_long = direction != "short"
    risk = abs(entry - sl) or 1e-9  # 1R = 止损距离

    bars = klines[: max_bars] if max_bars else klines

    for i, bar in enumerate(bars):
        high, low = _bar_hl(bar)
        if is_long:
            hit_tp = high >= tp
            hit_sl = low <= sl
        else:
            hit_tp = low <= tp
            hit_sl = high >= sl
        # 同根同时触及两轨：保守判止损（先触止损假设）
        if hit_sl and hit_tp:
            r = -1.0
            return {"outcome": "stop_loss", "was_correct": False,
                    "result_r": round(r, 3), "exit_price": sl,
                    "bars_held": i + 1, "hit_index": i,
                    "note": "同根双触·保守判止损"}
        if hit_tp:
            r = abs(tp - entry) / risk
            return {"outcome": "take_profit", "was_correct": True,
                    "result_r": round(r, 3), "exit_price": tp,
                    "bars_held": i + 1, "hit_index": i}
        if hit_sl:
            r = -abs(entry - sl) / risk
            return {"outcome": "stop_loss", "was_correct": False,
                    "result_r": round(r, 3), "exit_price": sl,
                    "bars_held": i + 1, "hit_index": i}

    # 竖轨：未触碰任何水平障碍 → 超时，按终盘价判盈亏
    if bars:
        exit_price = _bar_close(bars[-1])
    else:
        exit_price = entry
    pnl = (exit_price - entry) if is_long else (entry - exit_price)
    r = pnl / risk
    return {"outcome": "timeout", "was_correct": None,
            "result_r": round(r, 3), "exit_price": exit_price,
            "bars_held": len(bars), "hit_index": None}


# ═══ 管线: 事件 → 三重障碍 → trade_reviews 训练样本 ═══

def label_event(event: dict, klines: list, max_bars: int | None = None,
                atr: float | None = None, rr: float = 2.0) -> dict | None:
    """把单个有 setup_id 的触发事件标注成训练样本。

    优先用事件自带的 levels.take_profit/stop_loss；缺失则用 ATR 推导。
    direction 为 wait/None 的事件返回 None（无方向不可标注）。
    """
    direction = event.get("direction")
    if direction not in ("long", "short"):
        return None
    entry = event.get("trigger_price") or event.get("price")
    if not entry:
        return None
    entry = float(entry)

    # levels 可能是 dict（显式止盈止损）或 list（结构位清单，无显式止盈止损）
    levels = event.get("levels")
    if isinstance(levels, dict):
        tp = levels.get("take_profit") or levels.get("target1")
        sl = levels.get("stop_loss") or levels.get("stop") or event.get("invalid_price")
    else:
        # list 或缺失：无显式止盈止损，回退到事件级字段 / ATR 推导
        tp = event.get("take_profit") or event.get("target1")
        sl = event.get("stop_loss") or event.get("stop") or event.get("invalid_price")

    if tp is None or sl is None:
        if atr is None:
            return None
        tp, sl = derive_barriers(entry, direction, atr, rr=rr)

    r = label_triple_barrier(entry, direction, float(tp), float(sl), klines, max_bars)
    return {
        "schema": "trade_review_v2",
        "plan_id": event.get("plan_id"),
        "setup_id": event.get("setup_id"),
        "model_id": event.get("model_id"),
        "entry_tag": event.get("entry_tag"),
        "exit_tag": event.get("exit_tag"),
        "symbol": event.get("symbol"),
        "direction": direction,
        "entry_price": entry,
        "take_profit": float(tp),
        "stop_loss": float(sl),
        "outcome": r["outcome"],
        "was_correct": r["was_correct"],
        "result_r": r["result_r"],
        "exit_price": r["exit_price"],
        "bars_held": r["bars_held"],
        "data_grade": event.get("data_grade"),
        "auto_labeled": True,
        "labeled_at": datetime.now(TZ).isoformat(),
        "labeler": "triple_barrier_v1",
    }


def to_meta_features(review: dict) -> dict:
    """把标注好的 review 转成 meta_labeler 训练特征。"""
    return {
        "model_score": review.get("model_score", 0),
        "data_quality": review.get("data_grade", "C"),
        "cvd_direction": review.get("cvd_direction", "中性"),
        "cvd_quality": review.get("cvd_quality", "C"),
        "session": review.get("session", "off"),
        "loss_streak": review.get("loss_streak", 0),
        "rr_ratio": review.get("rr_ratio", 2.0),
        "direction": review.get("direction"),
        "was_correct": review.get("was_correct"),
    }


if __name__ == "__main__":
    # smoke test
    bars = [[0, 100, 112, 99, 108, 100]]
    print(label_triple_barrier(100, "long", 110, 95, bars))
