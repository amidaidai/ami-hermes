from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import xau_tv_sync


def test_main_degrades_nonzero_sync_result_to_stale_cache(monkeypatch, tmp_path):
    out = tmp_path / "xau_tv_state.json"
    monkeypatch.setattr(xau_tv_sync, "OUT", out)
    monkeypatch.setattr(xau_tv_sync.asyncio, "run", lambda coro: (coro.close(), 1)[1])

    assert xau_tv_sync.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["symbol"] == "OANDA:XAUUSD"
    assert payload["stale"] is True
    assert "同步返回非零状态" in payload["error"]


def test_main_preserves_recent_cache_on_exception(monkeypatch, tmp_path):
    out = tmp_path / "xau_tv_state.json"
    original = {"symbol": "OANDA:XAUUSD", "timeframes": {"5m": {"close": 4100}}}
    out.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(xau_tv_sync, "OUT", out)

    def fail(_coro):
        _coro.close()
        raise RuntimeError("cdp down")

    monkeypatch.setattr(xau_tv_sync.asyncio, "run", fail)
    assert xau_tv_sync.main() == 0
    assert json.loads(out.read_text(encoding="utf-8")) == original


def test_main_refreshes_xau_data_window_cache_after_success(monkeypatch):
    calls = []
    monkeypatch.setattr(xau_tv_sync.asyncio, "run", lambda coro: (coro.close(), 0)[1])
    monkeypatch.setattr(xau_tv_sync, "_refresh_tv_live_cache", lambda: calls.append("xau"))

    assert xau_tv_sync.main() == 0
    assert calls == ["xau"]
