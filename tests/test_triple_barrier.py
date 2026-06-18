from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import triple_barrier as tb


def _klines(prices):
    """构造 [openTime, open, high, low, close, volume, ...] 形式的 K 线列表"""
    out = []
    t0 = 1_700_000_000_000
    for i, p in enumerate(prices):
        out.append([t0 + i * 60_000, p, p, p, p, 100.0])
    return out


def test_long_take_profit_hit_first():
    # 多头入场 100，止盈 110，止损 95；价格先冲到 112 → 止盈命中
    bars = _klines([100, 102, 105, 112, 108])
    r = tb.label_triple_barrier(
        entry_price=100.0, direction="long",
        take_profit=110.0, stop_loss=95.0, klines=bars,
    )
    assert r["outcome"] == "take_profit"
    assert r["was_correct"] is True
    assert r["result_r"] > 0


def test_long_stop_loss_hit_first():
    # 多头入场 100，先跌到 94 → 止损命中
    bars = _klines([100, 98, 94, 111])
    r = tb.label_triple_barrier(
        entry_price=100.0, direction="long",
        take_profit=110.0, stop_loss=95.0, klines=bars,
    )
    assert r["outcome"] == "stop_loss"
    assert r["was_correct"] is False
    assert r["result_r"] < 0


def test_short_take_profit_hit_first():
    # 空头入场 100，止盈 90，止损 105；价格跌到 88 → 止盈命中
    bars = _klines([100, 97, 92, 88])
    r = tb.label_triple_barrier(
        entry_price=100.0, direction="short",
        take_profit=90.0, stop_loss=105.0, klines=bars,
    )
    assert r["outcome"] == "take_profit"
    assert r["was_correct"] is True


def test_timeout_vertical_barrier():
    # 价格在区间内震荡到末尾未触碰任何水平障碍 → 超时
    bars = _klines([100, 101, 99, 100, 101])
    r = tb.label_triple_barrier(
        entry_price=100.0, direction="long",
        take_profit=110.0, stop_loss=95.0, klines=bars,
    )
    assert r["outcome"] == "timeout"
    # 超时按终盘价方向判定盈亏，不算严格正确也不算止损
    assert "result_r" in r


def test_derive_barriers_from_atr():
    # 无显式止盈止损时，用 ATR + R:R 推导
    bars = _klines([100, 101, 99, 100, 101])
    tp, sl = tb.derive_barriers(entry_price=100.0, direction="long", atr=2.0, rr=2.0)
    assert sl < 100.0 < tp
    # R:R = 2 → 止盈距离是止损距离的 2 倍
    assert abs((tp - 100.0) - 2 * (100.0 - sl)) < 1e-6
