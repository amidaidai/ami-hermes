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
        "BTCUSDT": ("crypto", 15, "15m"),
        "XAUUSD": ("gold", 8, "5m"),
        "EURUSD": ("forex", 7, "15m"),
        "AAPL": ("stock", 8, "1h"),
        "ES1!": ("futures", 6, "15m"),
    }
    for symbol, (asset, full_len, main_tf) in expected.items():
        assert router._asset_class(symbol) == asset
        assert len(router.route_pipeline(symbol, "full")) == full_len
        assert router.timeframe_info(symbol)["main"] == main_tf


def test_crypto_full_route_is_the_canonical_fifteen_stage_pipeline():
    router = _load_router()
    assert router.route_pipeline("BTCUSDT", "full") == [
        "tv", "binance", "cg_pro", "macro", "x_sent", "cron_read",
        "cvd", "depth", "corr", "engine", "regime", "dual",
        "advanced", "risk", "card",
    ]


def test_quick_route_contains_only_live_execution_inputs():
    router = _load_router()
    assert router.route_pipeline("BTCUSDT", "quick") == ["tv", "binance", "card"]
    assert router.route_pipeline("BTCUSDT", "inherit") == ["tv", "binance", "card"]


def test_auto_card_uses_the_same_asset_taxonomy_as_router():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("auto_card_taxonomy", ROOT / "scripts" / "auto_card.py")
    assert spec is not None and spec.loader is not None
    auto_card = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auto_card)

    router = _load_router()
    for symbol in ("BTCUSDT", "XAUUSD", "XAGUSD", "EURUSD", "ES1!", "AAPL", "BTC-29MAR24-60000-C"):
        assert auto_card._asset_class(symbol) == router._asset_class(symbol)
