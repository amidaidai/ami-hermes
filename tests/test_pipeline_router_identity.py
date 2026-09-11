"""A08: identity parsing is local syntax evidence, never venue verification."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pipeline_router as router


def test_prefixed_stock_keeps_raw_separate_from_normalized_identity():
    identity = router.parse_asset_identity("nasdaq:aapl")
    assert identity["raw_symbol"] == "nasdaq:aapl"
    assert identity["normalized_symbol"] == "NASDAQ:AAPL"
    assert identity["ticker"] == "AAPL"
    assert identity["exchange"] == "NASDAQ"
    assert identity["asset_class"] == "stock"
    assert identity["supported"] is True
    assert identity["exchange_verified"] is False
    assert identity["tick_size"] is None
    assert router.route_pipeline("NASDAQ:AAPL") == router.route_pipeline("AAPL")


@pytest.mark.parametrize("symbol,asset,product,underlying", [
    ("BINANCE:BNBUSDT.P", "crypto", "perpetual", "BNB"),
    ("CME_MINI:ES1!", "futures", "continuous_future", "ES"),
    ("COMEX:GC2!", "futures", "continuous_future", "GC"),
    ("NYMEX:CL1!", "futures", "continuous_future", "CL"),
])
def test_derivative_product_identity(symbol, asset, product, underlying):
    identity = router.parse_asset_identity(symbol)
    assert identity["asset_class"] == asset
    assert identity["product_type"] == product
    assert identity["underlying"] == underlying
    assert identity["raw_symbol"] == symbol
    assert identity["normalized_symbol"] == symbol
    assert identity["exchange_verified"] is False
    assert router.route_pipeline(symbol)