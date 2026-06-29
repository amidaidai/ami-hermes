from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


auto_card = _load_module("auto_card_p0p1", ROOT / "scripts" / "auto_card.py")
wd = _load_module("watchdog_p0p1", ROOT / "scripts" / "watchdog.py")
watch_monitor = _load_module("watch_monitor_p0p1", ROOT / "scripts" / "行情守望.py")


def _minimal_klines(price=64000.0):
    return {
        "5m": {"high": price + 80, "low": price - 80, "close": price, "atr": 100},
        "15m": {"vah": price + 500, "poc": price + 120, "val": price - 500, "atr": 100},
        "1h": {"high": price + 700, "low": price - 700, "close": price},
        "4h": {"high": price + 1000, "low": price - 1000, "close": price},
    }


def test_a_status_low_rr_is_downgraded_before_render(monkeypatch):
    price = 64000.0
    meta = {
        "status": "A做多",
        "direction": "long",
        "priority_plan": "A",
        "model_id": "VWAP反抽",
        "data_grade": "A",
        "risk_usd": 2.0,
    }
    engine_data = {
        "symbol": "BTCUSDT",
        "quality": "A",
        "prices": {"primary": price},
        "klines": _minimal_klines(price),
    }
    monkeypatch.setattr(
        auto_card,
        "_calc_stop_target_atr",
        lambda *args, **kwargs: {
            "stop": price - 100,
            "target": price + 80,
            "rr": 0.8,
            "stop_reason": "测试止损",
            "target_reason": "测试止盈",
            "atr": 100,
        },
    )

    card = auto_card.render_card_locked(
        symbol="BTCUSDT",
        merged={"bias": "偏多", "confidence_5": 5, "long_confidence": 0.7, "short_confidence": 0.2},
        results=[{"name": "VWAP反抽", "confidence": 0.7}],
        meta=meta,
        engine_data=engine_data,
        force_full=True,
    )

    assert "X禁做" in card
    assert "⚠R:R不足" in card or "R:R" in card
    assert "A做多 → 入场" not in card


def test_monitor_liquidity_gate_uses_source_snapshot_when_macro_missing(monkeypatch):
    raw = {"symbols": {"BTCUSDT": {}}}
    block = {"monitor_enabled": True, "price_at_analysis": 64000.0}
    seen = {}

    monkeypatch.setattr(watch_monitor, "DATA_DIR", Path("/tmp/nonexistent-monitor-data"))
    monkeypatch.setattr(watch_monitor, "get_price", lambda symbol, block: 64000.0)
    monkeypatch.setattr(watch_monitor, "_HAS_BRIDGE", False)
    monkeypatch.setattr(watch_monitor, "append_system_event", lambda row: None)

    def fake_has_min_liquidity(symbol, snapshot):
        seen.update(snapshot)
        return True

    monkeypatch.setitem(sys.modules, "session_filter", type("SF", (), {
        "has_min_liquidity": staticmethod(fake_has_min_liquidity),
        "should_trade": staticmethod(lambda *a, **k: (True, "ok")),
        "get_asset_class": staticmethod(lambda symbol: "crypto"),
    }))

    _, ok = watch_monitor.process_block(raw, "BTCUSDT", block, {})

    assert ok is False or ok is True
    assert seen.get("quality") == "B"
    assert seen.get("confidence") == 100
    assert seen.get("confidence_label") == "live_price_ok"


def test_watchdog_block_sends_external_alert(tmp_path, monkeypatch):
    guard = tmp_path / "watchdog_guard.json"
    state = tmp_path / "watchdog_state.json"
    events = tmp_path / "system_events.jsonl"
    monkeypatch.setattr(wd, "GUARD_FILE", guard)
    monkeypatch.setattr(wd, "WATCHDOG_STATE_FILE", state)
    monkeypatch.setattr(wd, "SYSTEM_EVENT_FILE", events)
    sent = []
    monkeypatch.setattr(wd, "send_watchdog_alert", lambda msg: sent.append(msg) or True)

    now = time.time()
    guard.write_text(json.dumps({"restart_times": [now] * wd.MAX_RESTARTS_PER_HOUR}), encoding="utf-8")

    assert wd.start_monitor(emergency=False) is False
    assert sent
    assert "重启速率限制" in sent[-1]
    state_row = json.loads(state.read_text(encoding="utf-8"))
    assert state_row["status"] == "blocked"
    assert "重启速率限制" in state_row["last_restart_reason"]

def test_auto_card_cli_ignores_pytest_quiet_flag():
    assert auto_card._parse_cli_symbol(["-q"]) == "BTCUSDT"
    assert auto_card._parse_cli_symbol(["--push", "XAUUSD"]) == "XAUUSD"
    assert auto_card._parse_cli_symbol(["BTCUSDT", "--push"]) == "BTCUSDT"

def test_crypto_b_quality_liquidity_passes_when_sources_are_consistent():
    import session_filter

    assert session_filter.has_min_liquidity(
        "BTCUSDT",
        {"quality": "B", "confidence": 75, "price_spread_pct": 0.22},
    ) is True
    assert session_filter.has_min_liquidity(
        "BTCUSDT",
        {"quality": "B", "confidence": 65, "price_spread_pct": 0.22},
    ) is False

def test_monitor_ignores_invalid_cli_like_symbols():
    rows = list(watch_monitor.iter_symbol_blocks({"symbols": {"-q": {"levels": []}, "BTCUSDT": {"levels": []}}}))
    assert [symbol for symbol, _ in rows] == ["BTCUSDT"]
    rows = list(watch_monitor.iter_symbol_blocks({"symbol": "-q", "levels": []}))
    assert rows[0][0] == "BTCUSDT"
