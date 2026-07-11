from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tv_data_bridge as bridge


def test_expected_symbol_is_switched_and_verified(monkeypatch):
    calls = []

    def fake_tv(*args, timeout=15):
        calls.append(args)
        return "", True

    monkeypatch.setattr(bridge, "_tv", fake_tv)
    monkeypatch.setattr(bridge, "read_state_symbol", lambda: "OANDA:XAUUSD")
    assert bridge.ensure_expected_symbol("OANDA:XAUUSD")
    assert calls == [("symbol", "OANDA:XAUUSD")]


def test_collect_rejects_mismatched_chart_before_reading(monkeypatch):
    monkeypatch.setattr(bridge, "tv_available", lambda: True)
    monkeypatch.setattr(bridge, "ensure_expected_symbol", lambda symbol: False)
    monkeypatch.setattr(bridge, "load_cache", lambda: {})

    called = {"indicators": False}

    def fail_if_read(*args, **kwargs):
        called["indicators"] = True
        return {"poc_price": "4100"}

    monkeypatch.setattr(bridge, "read_indicators", fail_if_read)
    assert bridge.collect_and_cache(expect_symbol="BINANCE:BTCUSDT.P") is None
    assert not called["indicators"]


def test_tv_live_dump_accepts_explicit_symbol_argument():
    source = (ROOT / "scripts" / "tv_live_dump.py").read_text(encoding="utf-8")
    assert 'parser.add_argument("--symbol"' in source
    assert 'expected_symbol = resolve_tv_symbol(args.symbol)' in source
    assert 'expect_symbol=expected_symbol' in source
