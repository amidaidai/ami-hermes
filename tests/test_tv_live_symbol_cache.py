from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tv_live_dump
import auto_card


def test_tv_live_dump_resolves_system_symbols_to_tradingview_tickers():
    assert tv_live_dump.resolve_tv_symbol("BTCUSDT") == "BINANCE:BTCUSDT.P"
    assert tv_live_dump.resolve_tv_symbol("XAUUSD") == "OANDA:XAUUSD"
    assert tv_live_dump.resolve_tv_symbol("OANDA:XAUUSD") == "OANDA:XAUUSD"


def test_auto_card_prefers_matching_symbol_specific_cache():
    assert auto_card._tv_symbol_cache_path("BTCUSDT").name == "tv_live_BTCUSDT.json"
    assert auto_card._tv_symbol_cache_path("OANDA:XAUUSD").name == "tv_live_XAUUSD.json"


def test_tv_live_dump_keeps_generic_and_symbol_specific_cache_paths():
    btc = tv_live_dump.cache_paths_for_symbol("BINANCE:BTCUSDT.P")
    xau = tv_live_dump.cache_paths_for_symbol("OANDA:XAUUSD")
    assert [p.name for p in btc] == ["tv_live.json", "tv_live_BTCUSDT.json"]
    assert [p.name for p in xau] == ["tv_live.json", "tv_live_XAUUSD.json"]
