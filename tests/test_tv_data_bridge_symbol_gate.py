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
    monkeypatch.setattr(bridge, "load_cache", lambda *args, **kwargs: {})

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


def test_num_parses_tradingview_compact_numbers():
    assert bridge._num("4.43\u202fK") == 4430.0
    assert bridge._num("−1.2M") == -1_200_000.0


def test_read_quote_parses_json_payload(monkeypatch):
    monkeypatch.setattr(
        bridge,
        "_tv",
        lambda *args, **kwargs: ('{"success": true, "last": 4432.75}', True),
    )
    assert bridge.read_quote("OANDA:XAUUSD") == 4432.75


def test_collect_rejects_partial_svp_payload_even_when_s_vwap_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "CACHE", tmp_path / "tv_dmi_cache.json")
    monkeypatch.setattr(bridge, "tv_available", lambda: True)
    monkeypatch.setattr(bridge, "ensure_expected_symbol", lambda _symbol: True)
    monkeypatch.setattr(bridge, "read_state_symbol", lambda: "OANDA:XAUUSD")
    monkeypatch.setattr(bridge, "read_indicators", lambda *_args: {"s_vwap": "4.43\u202fK"})
    monkeypatch.setattr(bridge, "read_dmi_table", lambda *_args: {"结论": "观望"})
    monkeypatch.setattr(bridge, "read_pine_lines", lambda *_args: [])
    monkeypatch.setattr(bridge, "read_quote", lambda *_args: 4432.75)
    assert bridge.collect_and_cache(expect_symbol="OANDA:XAUUSD") is None


def test_tv_collection_lock_is_reentrant_and_cleans_up(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "TV_LOCK", tmp_path / "tv.lock")
    with bridge.tv_collection_lock(timeout=0.2):
        assert bridge.TV_LOCK.exists()
        with bridge.tv_collection_lock(timeout=0.2):
            assert bridge.TV_LOCK.exists()
    assert not bridge.TV_LOCK.exists()


def test_tv_collection_lock_recovers_from_windows_kill_system_error(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "TV_LOCK", tmp_path / "tv.lock")
    bridge.TV_LOCK.write_text("999999\n", encoding="utf-8")

    def raise_windows_system_error(*_args):
        raise SystemError("[WinError 87] 参数错误")

    monkeypatch.setattr(bridge.os, "kill", raise_windows_system_error)
    with bridge.tv_collection_lock(timeout=0.2):
        assert bridge.TV_LOCK.exists()
    assert not bridge.TV_LOCK.exists()


def test_tv_cache_records_identity_and_read_quality(monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "CACHE", tmp_path / "tv_dmi_cache.json")
    monkeypatch.setattr(bridge, "tv_available", lambda: True)
    monkeypatch.setattr(bridge, "ensure_expected_symbol", lambda _symbol: True)
    monkeypatch.setattr(bridge, "read_state_symbol", lambda: "BINANCE:BTCUSDT.P")
    monkeypatch.setattr(bridge, "read_indicators", lambda *_args: {"poc_price": "78000"})
    monkeypatch.setattr(bridge, "read_dmi_table", lambda *_args: {"结论": "观望", "方向": "观望", "路径": "等确认", "风控": "止—"})
    monkeypatch.setattr(bridge, "read_pine_lines", lambda *_args: [])
    monkeypatch.setattr(bridge, "read_quote", lambda *_args: 78001.0)
    monkeypatch.setattr(bridge, "read_chart_state", lambda: {
        "symbol": "BINANCE:BTCUSDT.P", "resolution": "15",
        "studies": [{"name": "SVP+ICT+VWAP+CVD"}, {"name": "Volume Aggregated Spot & Futures"}],
    })
    monkeypatch.setattr(bridge, "read_pine_boxes", lambda *_args: [])
    monkeypatch.setattr(bridge, "read_pine_labels", lambda *_args: [])
    monkeypatch.setattr(bridge, "read_binance_snapshot", lambda *_a, **_k: {"status": "unavailable"})
    monkeypatch.setattr(bridge.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(bridge, "read_quote_payload", lambda *_args: {
        "symbol": "BINANCE:BTCUSDT.P", "exchange": "Binance", "type": "swap",
        "last": 78001.0, "open": 77900.0, "high": 78100.0, "low": 77800.0,
        "close": 78001.0,
    })
    cache = bridge.collect_and_cache(expect_symbol="BINANCE:BTCUSDT.P")
    assert cache["identity_valid"] is True
    assert cache["action_table_complete"] is True
    assert cache["source_quality"] == "A"


def _xau_chart_state():
    return {
        "symbol": "OANDA:XAUUSD",
        "resolution": "5",
        "studies": [
            {"name": "SVP+ICT+VWAP+CVD"},
            {"name": "Volume Aggregated Spot & Futures"},
        ],
    }


def test_xau_quote_is_accepted_without_binance_swap_identity(monkeypatch, tmp_path):
    """黄金报价不能拿 BTC swap 身份去卡死，否则 5m 行动格永远刷不出来。"""
    monkeypatch.setattr(bridge, "CACHE", tmp_path / "tv_dmi_cache.json")
    monkeypatch.setattr(bridge, "tv_available", lambda: True)
    monkeypatch.setattr(bridge, "ensure_expected_symbol", lambda _symbol: True)
    monkeypatch.setattr(bridge, "read_chart_state", _xau_chart_state)
    monkeypatch.setattr(bridge, "read_state_symbol", lambda: "OANDA:XAUUSD")
    monkeypatch.setattr(bridge, "read_indicators", lambda *_args: {
        "poc_price": "4330", "vah_price": "4360", "val_price": "4300",
        "s_vwap": "4331", "mcp_side_code": "0", "mcp_grade_code": "3",
        "mcp_setup_score": "40", "mcp_entry_price": "4330",
    })
    monkeypatch.setattr(bridge, "read_dmi_table", lambda *_args: {
        "结论": "观望", "方向": "观望", "路径": "等确认", "风控": "止—", "操作": "等待",
    })
    monkeypatch.setattr(bridge, "read_pine_lines", lambda *_args: [])
    monkeypatch.setattr(bridge, "read_pine_boxes", lambda *_args: [])
    monkeypatch.setattr(bridge, "read_pine_labels", lambda *_args: [])
    seen = {}

    def fake_quote_payload(symbol="BINANCE:BTCUSDT.P"):
        seen["symbol"] = symbol
        return {
            "symbol": "OANDA:XAUUSD", "exchange": "OANDA", "type": "cfd",
            "last": 4331.2, "open": 4320.0, "high": 4340.0, "low": 4310.0, "close": 4331.2,
        }

    monkeypatch.setattr(bridge, "read_quote_payload", fake_quote_payload)
    monkeypatch.setattr(bridge, "read_quote", lambda *_args: 4331.2)
    monkeypatch.setattr(bridge, "read_binance_snapshot", lambda *_args, **_kw: (_ for _ in ()).throw(
        AssertionError("XAU 不得拉 Binance 合约交叉")
    ))
    monkeypatch.setattr(bridge.time, "sleep", lambda *_args, **_kw: None)

    cache = bridge.collect_and_cache(expect_symbol="OANDA:XAUUSD", expected_timeframe="5")
    assert cache is not None
    assert cache.get("stale") is not True
    assert cache["fresh"] is True
    assert cache["symbol"] == "OANDA:XAUUSD"
    assert cache["last_price"] == 4331.2
    assert seen["symbol"] == "OANDA:XAUUSD"
    assert cache["binance_cross_validation"]["status"] == "skipped"


def test_btc_quote_cannot_authorize_xau_action_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "CACHE", tmp_path / "tv_dmi_cache.json")
    monkeypatch.setattr(bridge, "tv_available", lambda: True)
    monkeypatch.setattr(bridge, "ensure_expected_symbol", lambda _symbol: True)
    monkeypatch.setattr(bridge, "read_chart_state", _xau_chart_state)
    monkeypatch.setattr(bridge, "read_state_symbol", lambda: "OANDA:XAUUSD")
    monkeypatch.setattr(bridge, "read_indicators", lambda *_args: {"poc_price": "4330"})
    monkeypatch.setattr(bridge, "read_dmi_table", lambda *_args: {
        "结论": "观望", "方向": "观望", "路径": "等确认", "风控": "止—",
    })
    monkeypatch.setattr(bridge, "read_pine_lines", lambda *_args: [])
    monkeypatch.setattr(bridge, "read_quote_payload", lambda *_args, **_kw: {
        "symbol": "BINANCE:BTCUSDT.P", "exchange": "Binance", "type": "swap", "last": 77318.0,
    })
    monkeypatch.setattr(bridge, "read_quote", lambda *_args: 77318.0)
    monkeypatch.setattr(bridge.time, "sleep", lambda *_args, **_kw: None)
    cache = bridge.collect_and_cache(expect_symbol="OANDA:XAUUSD", expected_timeframe="5")
    assert cache is None or cache.get("stale") is True
    assert not (tmp_path / "tv_dmi_cache.json").exists() or (
        "XAU" not in (tmp_path / "tv_dmi_cache.json").read_text(encoding="utf-8")
        or '"stale": true' in (tmp_path / "tv_dmi_cache.json").read_text(encoding="utf-8").lower()
    )
