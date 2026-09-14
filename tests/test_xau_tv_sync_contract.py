from __future__ import annotations

from datetime import datetime, timezone, timedelta

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import xau_tv_sync


TZ = timezone(timedelta(hours=8))


def _state(ts: str):
    return {
        "symbol": "OANDA:XAUUSD",
        "batch_id": "batch-1",
        "updated_at": ts,
        "timeframes": {
            tf: {"open": 4300.0, "high": 4310.0, "low": 4290.0, "close": 4305.0}
            for tf in ("1D", "4h", "1h", "15m", "5m")
        },
    }


def _live(ts: str):
    return {
        "symbol": "OANDA:XAUUSD",
        "batch_id": "batch-1",
        "timestamp": ts,
        "fresh": True,
        "stale": False,
        "identity_valid": True,
        "action_table_complete": True,
        "decision_table": {"结论": "等待", "方向": "观望", "路径": "等确认", "风控": "止损待定", "操作": "只观察"},
        "poc": 4300.0,
        "vah": 4310.0,
        "val": 4290.0,
    }


def test_xau_state_and_main_action_cache_must_be_fresh_and_symbol_scoped():
    now = datetime.now(TZ)
    result = xau_tv_sync.validate_xau_outputs(
        _state(now.isoformat()),
        _live(now.isoformat()),
        now=now,
    )

    assert result["usable"] is True
    assert result["state"]["coverage"] == 5
    assert result["live"]["usable"] is True


def test_xau_five_tf_success_cannot_hide_stale_main_action_cache():
    now = datetime.now(TZ)
    # 2026-09-13：live 阈值 10→13 分钟（对齐 btc_tv_refresh 18/20 模式，
    # 阈值 < 15min cron 间隔）。构造值随之外移到 14 分钟，保持「超阈值=陈旧」语义。
    # 2026-09-14：门限分家（常驻 cadence-aware 17min / 卡时 5min，见
    # test_xau_tv_sync_degradation），本用例改引用常驻门限常量 + 3 分钟，
    # 语义不变：超常驻门限的主周期缓存，五周期再新也不能把它抬成可用。
    stale = (now - timedelta(minutes=xau_tv_sync.XAU_LIVE_MAX_AGE_CADENCE_MIN + 3)).isoformat()
    result = xau_tv_sync.validate_xau_outputs(
        _state(now.isoformat()),
        _live(stale),
        now=now,
    )

    assert result["usable"] is False
    assert result["state"]["usable"] is True
    assert result["live"]["usable"] is False
    assert "主周期" in result["reason"]


def test_xau_wrong_symbol_cannot_be_promoted_by_fresh_timestamps():
    now = datetime.now(TZ)
    live = _live(now.isoformat())
    live["symbol"] = "BINANCE:BTCUSDT.P"
    result = xau_tv_sync.validate_xau_outputs(_state(now.isoformat()), live, now=now)

    assert result["usable"] is False
    assert result["live"]["identity_valid"] is False


def test_xau_state_and_action_cache_must_belong_to_the_same_capture_batch():
    now = datetime.now(TZ)
    live = _live(now.isoformat())
    live["batch_id"] = "batch-2"

    result = xau_tv_sync.validate_xau_outputs(
        _state(now.isoformat()), live, now=now,
    )

    assert result["usable"] is False
    assert result["batch"]["usable"] is False
    assert "批次" in result["reason"]


def test_xau_pair_rejects_missing_capture_batch_ids():
    now = datetime.now(TZ)
    state = _state(now.isoformat())
    live = _live(now.isoformat())
    state.pop("batch_id")
    live.pop("batch_id")

    result = xau_tv_sync.validate_xau_outputs(state, live, now=now)

    assert result["usable"] is False
    assert result["batch"]["usable"] is False


def test_xau_main_action_cache_does_not_require_subindicator_操作_row():
    """主指标行动格没有「操作」行（那是副指标）。周末 X·等开市 也必须能配对发布。"""
    now = datetime.now(TZ)
    live = _live(now.isoformat())
    live["decision_table"] = {
        "位置": "价在VA内",
        "结论": "X 低流动 · 等开市",
        "方向": "观望 · 走弱·收缩",
        "路径": "失效×→低流动性",
        "风控": "禁做·不出价",
    }
    result = xau_tv_sync.validate_xau_outputs(_state(now.isoformat()), live, now=now)
    assert result["live"]["action_table_complete"] is True
    assert result["usable"] is True


def test_xau_main_action_cache_rejects_missing_core_rows():
    now = datetime.now(TZ)
    live = _live(now.isoformat())
    live["decision_table"] = {"结论": "观望", "方向": "观望"}
    result = xau_tv_sync.validate_xau_outputs(_state(now.isoformat()), live, now=now)
    assert result["live"]["action_table_complete"] is False
    assert result["usable"] is False


def test_xau_pair_rejects_capture_timestamps_that_are_too_far_apart():
    base = datetime.now(TZ)
    state = _state(base.isoformat())
    live = _live((base + timedelta(seconds=121)).isoformat())
    now = base + timedelta(seconds=121)

    result = xau_tv_sync.validate_xau_outputs(state, live, now=now)

    assert result["usable"] is False
    assert result["batch"]["usable"] is False
    assert "时间偏差" in result["batch"]["reason"]
