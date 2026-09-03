from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import xau_tv_sync


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
    monkeypatch.setattr(xau_tv_sync, "validate_xau_outputs", lambda *args, **kwargs: {"usable": True})

    assert xau_tv_sync.main() == 0
    assert len(calls) == 1
    assert calls[0]
