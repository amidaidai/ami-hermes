from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cvd_aggtrades as ca


def _trades(specs):
    """specs: [(qty, is_buyer_maker), ...] → aggTrades 风格 dict 列表。

    Binance aggTrades 字段 m=isBuyerMaker：
      m=True  → 买方是挂单方 → 主动卖出（taker sell）
      m=False → 卖方是挂单方 → 主动买入（taker buy）
    """
    out = []
    for i, (qty, m) in enumerate(specs):
        out.append({"p": "100.0", "q": str(qty), "m": m, "T": 1_700_000_000_000 + i * 1000})
    return out


def test_cvd_from_aggtrades_buy_dominant():
    # 主动买入占多 → CVD 为正，方向「买」
    trades = _trades([(10, False), (10, False), (3, True)])  # 买20 卖3
    r = ca.cvd_from_aggtrades(trades)
    assert r["cvd"] > 0
    assert r["direction"] == "买"
    assert r["quality"] == "A级"


def test_cvd_from_aggtrades_sell_dominant():
    trades = _trades([(2, False), (12, True), (10, True)])  # 买2 卖22
    r = ca.cvd_from_aggtrades(trades)
    assert r["cvd"] < 0
    assert r["direction"] == "卖"


def test_cvd_from_aggtrades_neutral():
    trades = _trades([(10, False), (10, True)])  # 买10 卖10
    r = ca.cvd_from_aggtrades(trades)
    assert r["direction"] == "中性"


def test_cvd_from_aggtrades_empty_safe():
    r = ca.cvd_from_aggtrades([])
    assert r["direction"] in ("?", "中性")
    assert r["quality"] in ("C级", "无")


def test_multi_period_consistency_aligned():
    # 三周期同向 → 一致，consistent=True
    r = ca.multi_period_consistency({"5m": "买", "15m": "买", "1h": "买"})
    assert r["consistent"] is True
    assert r["aligned_direction"] == "买"
    assert r["agree_count"] == 3


def test_multi_period_consistency_conflict():
    # 周期冲突 → 不一致，标记分歧
    r = ca.multi_period_consistency({"5m": "买", "15m": "卖", "1h": "中性"})
    assert r["consistent"] is False
    assert "分歧" in r["note"] or "冲突" in r["note"]
