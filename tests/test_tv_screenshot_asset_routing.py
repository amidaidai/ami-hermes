from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tv_screenshot


def test_screenshot_routes_asset_to_correct_tv_symbol_and_main_timeframe():
    assert tv_screenshot._sym_tf("BTCUSDT") == ("BINANCE:BTCUSDT.P", "15", "15m")
    assert tv_screenshot._sym_tf("XAUUSD") == ("OANDA:XAUUSD", "5", "5m")
    assert tv_screenshot._sym_tf("AAPL") == ("NASDAQ:AAPL", "60", "1h")
    assert tv_screenshot._sym_tf("EURUSD") == ("OANDA:EURUSD", "15", "15m")
    assert tv_screenshot._sym_tf("ES") == ("CME_MINI:ES1!", "15", "15m")
