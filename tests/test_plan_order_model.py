"""计划执行模型（order model）接线回归 — 2026-09-13 用户批准推进。

语义：影子信号记录的是「等触发」观察价；计划执行=触发价挂 GTC 限价单
（价格未触达则永不成交）。映射唯一权威 = shadow_calibration.PLAN_ORDER_MODEL；
未知模型保持 missing_order_model（禁止猜测订单类型）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from shadow_calibration import PLAN_ORDER_MODEL, order_model_for_plan
import shadow_outcome_labeler as sol


def test_known_plans_map_to_limit():
    for mid in ("vwap_pullback", "poc_rejection", "breakout_acceptance",
                "liquidity_sweep", "fvg_pullback", "ob_pullback"):
        assert order_model_for_plan(mid) == {"type": "limit"}, mid
    # 大小写/空白容错
    assert order_model_for_plan("  VWAP_PULLBACK ") == {"type": "limit"}


def test_unknown_plan_stays_unmapped():
    assert order_model_for_plan("some_new_model") is None
    assert order_model_for_plan(None) is None
    assert order_model_for_plan("") is None
    # 全部映射值只能是标注器允许的两种之一
    assert set(PLAN_ORDER_MODEL.values()) <= {"limit", "market_next_open"}


def test_labeler_backfills_order_model_for_known_plan():
    record = _record() | {"model_id": "vwap_pullback"}
    rows, stats = sol.label_ready_records([record], lambda *_: _bars(16), now_ms=99_000_000)
    assert stats["labeled"] == 1
    h16 = rows[0]["outcome"]["h16"]
    assert h16["status"] != "missing_order_model"
    assert h16["filled"] is True


def test_labeler_keeps_missing_for_unknown_plan():
    record = _record() | {"model_id": "brand_new_model_v9"}
    rows, stats = sol.label_ready_records([record], lambda *_: _bars(16), now_ms=99_000_000)
    assert stats["labeled"] == 1, stats
    assert rows[0]["outcome"]["h16"]["status"] == "missing_order_model"


def test_record_order_model_wins_over_backfill():
    record = _record() | {"model_id": "vwap_pullback",
                          "order_model": {"type": "market_next_open"}}
    proj = sol._signal_projection(record)
    assert proj["order_model"] == {"type": "market_next_open"}


def test_nested_main_model_id_used_for_backfill():
    record = _record() | {
        "main": {"direction": "long", "entry": 100.0, "stop": 98.0,
                 "target": 104.0, "model_id": "poc_rejection"}
    }
    proj = sol._signal_projection(record)
    assert proj["order_model"] == {"type": "limit"}


def test_auto_card_writes_order_model_into_shadow_signal():
    """防回退：新信号必须携带 order_model（auto_card 写入点）。"""
    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert '"order_model": order_model_for_plan(' in src


def _record(signal_id="BTC-OM-1", ts=1_000_000):
    return {
        "signal_id": signal_id,
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "ts": ts,
        "side": "long",
        "entry": 100.0,
        "stop": 98.0,
        "target": 104.0,
        "model_id": "vwap_pullback",
    }


def _bars(count=16):
    return [
        [i, "100", "101", "99", "100", "10", i + 899_999]
        for i in range(1_800_000, 1_800_000 + count * 900_000, 900_000)
    ]
