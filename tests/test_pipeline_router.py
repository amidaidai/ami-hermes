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
    """期权跟随底层（用户规则）：Deribit BTC 期权 → 加密步骤集 + 期权链。

    旧断言（full=["tv","options_chain","card"]）是「option 只跑自己」的旧行为，
    会让 BTC 期权拿不到 Binance OI/费率/CVD 这些驱动它价格的证据。
    """
    router = _load_router()
    symbol = "BTC-29MAR24-60000-C"
    assert router._asset_class(symbol) == "option"
    identity = router.parse_asset_identity(symbol)
    assert identity["underlying"] == "BTC" and identity["underlying_class"] == "crypto"
    assert router.timeframe_info(symbol)["main"] == "15m"          # 跟随底层主周期
    full = router.route_pipeline(symbol, "full")
    assert full == [*router.CRYPTO_FULL_PIPELINE[:-1], "options_chain", "card"]
    assert router.route_pipeline(symbol, "quick") == ["tv", "binance", "options_chain", "card"]
    assert router.route_pipeline(symbol, "monitor") == ["binance"]  # 事件档位不加期权链


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


def test_full_route_is_never_empty_for_any_recognised_class():
    """full 档返回空 = 静默「不分析」：这是最危险的失败模式，必须结构性杜绝。

    历史缺陷：SPX500 / FOOBAR / 标准期权代码都会落到 asset_class='other'，
    而没有任何步骤声明支持 'other'，于是 full 返回 [] —— 调用方拿到空列表
    后既不报错也不分析。
    """
    router = _load_router()
    for symbol in ("BTCUSDT.P", "OANDA:XAUUSD", "EURUSD", "AAPL", "ES1!", "SPX500",
                   "AAPL240119C150", "SPX 240119C5000", "BTC-29MAR24-60000-C", "FOOBAR"):
        for mode in ("quick", "inherit", "standard", "full"):
            steps = router.route_pipeline(symbol, mode)
            assert steps, f"{symbol} 在 {mode} 档返回了空管线"
            assert all(s in router.STEPS for s in steps)
        # 未知档位必须拒绝，不能静默改成 quick 或 full。
        with __import__("pytest").raises(ValueError, match="Unknown analysis mode"):
            router.route_pipeline(symbol, "Fuuull")


def test_unknown_analysis_mode_is_reported_not_silently_downgraded():
    router = _load_router()
    with __import__("pytest").raises(ValueError, match="Unknown analysis mode"):
        router.analysis_mode_spec("Fuuull")
    # 档位名大小写不敏感
    assert router.analysis_mode_spec("Quick")["mode"] == "quick"
    assert router.analysis_mode_spec("FULL")["card"] == "full"


def test_option_symbols_are_recognised_and_follow_the_underlying():
    router = _load_router()
    cases = {
        "AAPL240119C150": ("AAPL", "stock", "1h"),       # OSI 无空格
        "AAPL  240119C00150000": ("AAPL", "stock", "1h"),  # OCC 空格补齐
        "SPX 240119C5000": ("SPX", "index", "15m"),      # 指数期权
        "BTC-29MAR24-60000-C": ("BTC", "crypto", "15m"),  # Deribit
    }
    for symbol, (underlying, base, main_tf) in cases.items():
        identity = router.parse_asset_identity(symbol)
        assert identity["asset_class"] == "option", symbol
        assert identity["underlying"] == underlying, symbol
        assert identity["underlying_class"] == base, symbol
        assert router.timeframe_info(symbol)["main"] == main_tf, symbol
        assert "options_chain" in router.route_pipeline(symbol, "full"), symbol


def test_index_tickers_do_not_fall_through_to_other():
    router = _load_router()
    for symbol in ("SPX500", "NAS100", "US30", "DAX", "VIX", "DXY"):
        assert router._asset_class(symbol) == "index", symbol
        assert router.route_pipeline(symbol, "full") == ["tv", "macro", "x_sent", "cron_read", "corr", "card"]


def test_monitor_mode_stays_event_only_even_for_options():
    router = _load_router()
    assert router.route_pipeline("AAPL240119C150", "monitor") == []
    assert router.route_pipeline("BTC-29MAR24-60000-C", "monitor") == ["binance"]
