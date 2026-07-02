#!/usr/bin/env python3
"""Regression tests for market routing / pipeline adaptation."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "scripts" / "pipeline_router.py"


def _load_router():
    spec = importlib.util.spec_from_file_location("pipeline_router_under_test", ROUTER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_deribit_option_symbol_routes_to_option_pipeline():
    router = _load_router()
    symbol = "BTC-29MAR24-60000-C"
    assert router._asset_class(symbol) == "option"
    assert router.route_pipeline(symbol, "full") == ["tv", "options_chain", "card"]
    assert router.route_pipeline(symbol, "quick") == ["tv", "card"]


def test_core_market_pipeline_lengths_remain_stable():
    router = _load_router()
    expected = {
        "BTCUSDT": ("crypto", 10, "15m"),
        "XAUUSD": ("gold", 8, "5m"),
        "EURUSD": ("forex", 7, "15m"),
        "AAPL": ("stock", 8, "1h"),
        "ES1!": ("futures", 6, "15m"),
    }
    for symbol, (asset, full_len, main_tf) in expected.items():
        assert router._asset_class(symbol) == asset
        assert len(router.route_pipeline(symbol, "full")) == full_len
        assert router.timeframe_info(symbol)["main"] == main_tf
