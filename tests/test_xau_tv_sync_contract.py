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
    stale = (now - timedelta(minutes=11)).isoformat()
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


def test_xau_pair_rejects_capture_timestamps_that_are_too_far_apart():
    base = datetime.now(TZ)
    state = _state(base.isoformat())
    live = _live((base + timedelta(seconds=121)).isoformat())
    now = base + timedelta(seconds=121)

    result = xau_tv_sync.validate_xau_outputs(state, live, now=now)

    assert result["usable"] is False
    assert result["batch"]["usable"] is False
    assert "时间偏差" in result["batch"]["reason"]
