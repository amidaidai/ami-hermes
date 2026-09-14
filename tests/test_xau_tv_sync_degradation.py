from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pytest

import xau_tv_sync


@pytest.fixture(autouse=True)
def _no_active_analysis_lease(monkeypatch, tmp_path):
    """隔离活跃分析租约：长跑分析（如 auto_card）持租约期间，
    xau_tv_sync 会走「让路」分支并跳过主逻辑，导致本文件断言在并发下假红
    （2026-09-13 实测 3 例）。测试固定为「无租约」环境；让路路径由
    xau_tv_sync 自身逻辑与运维观察覆盖。

    2026-09-14：同时把轮次取证标记隔离到 tmp_path —— main() 会在真实
    data/xau_tv_sync_runs.jsonl 追加 enter/error/published，跑测试不能污染
    生产取证文件。
    """
    monkeypatch.setattr(xau_tv_sync, "analysis_lease_defer_exit", lambda: None)
    monkeypatch.setattr(xau_tv_sync, "AUDIT_MARKER_FILE", tmp_path / "xau_tv_sync_runs.jsonl")


def test_standing_gate_is_cadence_aware_and_card_gate_stays_five():
    """2026-09-14 自检 P1-②：两层门限分家 —— 常驻 cadence-aware / 卡时 5min。

    历史沿革：10 → 13（修 15min 周期尾部误判）→ 5（用户批准的卡时效）→
    分家：常驻 17 = 节奇 15 + 余量 2；卡时 5 = auto_card 显式传入（超窗即现场刷新）。
    关系式：常驻门限必须 ≥ cron 间隔 + 边际，否则每周期尾部必然假 FAIL。
    """
    src = (ROOT / "scripts" / "xau_tv_sync.py").read_text(encoding="utf-8")
    assert "XAU_LIVE_MAX_AGE_CADENCE_MIN = 17.0" in src
    assert "live_max_age_minutes: float = XAU_LIVE_MAX_AGE_CADENCE_MIN" in src
    assert "max_age_minutes: float = XAU_LIVE_MAX_AGE_CADENCE_MIN" in src
    auto = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert "TV_LIVE_READ_MAX_AGE_MIN = 5.0" in auto


def _pair(minutes_old: float):
    from datetime import timedelta
    stamp = (datetime.now(timezone.utc) - timedelta(minutes=minutes_old)).isoformat()
    state = {
        "symbol": "OANDA:XAUUSD",
        "batch_id": "batch-1",
        "updated_at": stamp,
        "timeframes": {
            tf: {"open": 4300.0, "high": 4310.0, "low": 4290.0, "close": 4305.0}
            for tf in ("1D", "4h", "1h", "15m", "5m")
        },
    }
    live = {
        "symbol": "OANDA:XAUUSD",
        "batch_id": "batch-1",
        "timestamp": stamp,
        "fresh": True,
        "stale": False,
        "identity_valid": True,
        "action_table_complete": True,
        "decision_table": {key: "通过" for key in ("结论", "方向", "路径", "风控", "操作")},
    }
    return state, live


def test_midcycle_pair_passes_standing_gate_but_card_gate_rejects_it():
    """发布后 10 分钟（节奇中段）：常驻门限 OK；卡时 5min 拒用 → 出卡前现场刷新。"""
    state, live = _pair(10)
    assert xau_tv_sync.validate_xau_outputs(state, live)["usable"] is True
    assert xau_tv_sync.validate_xau_outputs(state, live, live_max_age_minutes=5.0)["usable"] is False
    # 超过一个节奇仍必须 FAIL（常驻门限不能变成「永不报警」）
    state2, live2 = _pair(20)
    assert xau_tv_sync.validate_xau_outputs(state2, live2)["usable"] is False


def test_main_degrades_nonzero_sync_result_to_stale_cache(monkeypatch, tmp_path):
    out = tmp_path / "xau_tv_state.json"
    monkeypatch.setattr(xau_tv_sync, "OUT", out)
    monkeypatch.setattr(xau_tv_sync.asyncio, "run", lambda coro: (coro.close(), 1)[1])

    assert xau_tv_sync.main() == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["symbol"] == "OANDA:XAUUSD"
    assert payload["stale"] is True
    assert "同步返回非零状态" in payload["error"]


def test_main_preserves_recent_cache_on_exception(monkeypatch, tmp_path):
    out = tmp_path / "xau_tv_state.json"
    live_path = tmp_path / "tv_live_XAUUSD.json"
    stamp = datetime.now(timezone.utc).isoformat()
    original = {
        "symbol": "OANDA:XAUUSD",
        "batch_id": "batch-1",
        "updated_at": stamp,
        "timeframes": {
            tf: {"open": 4300.0, "high": 4310.0, "low": 4290.0, "close": 4305.0}
            for tf in ("1D", "4h", "1h", "15m", "5m")
        },
    }
    live = {
        "symbol": "OANDA:XAUUSD",
        "batch_id": "batch-1",
        "timestamp": stamp,
        "fresh": True,
        "stale": False,
        "identity_valid": True,
        "action_table_complete": True,
        "decision_table": {key: "通过" for key in ("结论", "方向", "路径", "风控", "操作")},
    }
    out.write_text(json.dumps(original), encoding="utf-8")
    live_path.write_text(json.dumps(live), encoding="utf-8")
    monkeypatch.setattr(xau_tv_sync, "OUT", out)
    monkeypatch.setattr(xau_tv_sync, "LIVE_OUT", live_path)

    def fail(_coro):
        _coro.close()
        raise RuntimeError("cdp down")

    monkeypatch.setattr(xau_tv_sync.asyncio, "run", fail)
    assert xau_tv_sync.main() == 1
    assert json.loads(out.read_text(encoding="utf-8")) == original


def test_main_preserves_structured_state_when_live_pair_is_unavailable(monkeypatch, tmp_path):
    out = tmp_path / "xau_tv_state.json"
    structured = {
        "symbol": "OANDA:XAUUSD",
        "batch_id": "batch-old",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "timeframes": {
            tf: {"open": 4300.0, "high": 4310.0, "low": 4290.0, "close": 4305.0}
            for tf in ("1D", "4h", "1h", "15m", "5m")
        },
    }
    out.write_text(json.dumps(structured), encoding="utf-8")
    monkeypatch.setattr(xau_tv_sync, "OUT", out)
    monkeypatch.setattr(xau_tv_sync.asyncio, "run", lambda coro: (coro.close(), 1)[1])

    assert xau_tv_sync.main() == 1
    assert json.loads(out.read_text(encoding="utf-8")) == structured


def test_main_refreshes_xau_data_window_cache_after_success(monkeypatch, tmp_path):
    calls = []
    staged = tmp_path / "xau_tv_state.json.tmp"
    monkeypatch.setattr(xau_tv_sync, "STAGED_OUT", staged)
    monkeypatch.setattr(xau_tv_sync, "OUT", tmp_path / "xau_tv_state.json")

    monkeypatch.setattr(xau_tv_sync.asyncio, "run", lambda coro: (coro.close(), 0)[1])

    def refresh(batch_id=None):
        calls.append(batch_id)
        staged.write_text(json.dumps({"symbol": "OANDA:XAUUSD", "timeframes": {"5m": {"close": 4300}}}), encoding="utf-8")
        return {}

    monkeypatch.setattr(xau_tv_sync, "_refresh_tv_live_cache", refresh)
    monkeypatch.setattr(xau_tv_sync, "_prepare_xau_main_chart", lambda: True)
    monkeypatch.setattr(xau_tv_sync, "validate_xau_outputs", lambda *args, **kwargs: {"usable": True})

    assert xau_tv_sync.main() == 0
    assert len(calls) == 1
    assert calls[0]
