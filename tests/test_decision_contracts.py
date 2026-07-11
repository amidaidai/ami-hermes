from __future__ import annotations

import pytest

from contracts import validate_market_snapshot


def test_market_snapshot_contract_rejects_missing_or_extra_fields():
    valid = {
        "symbol": "BTCUSDT", "ts": 1, "price": 100.0,
        "ohlcv": {}, "tv_indicators": {}, "derivatives": {},
        "macro": {}, "news": None,
    }
    assert validate_market_snapshot(valid) == valid
    with pytest.raises(ValueError, match="missing"):
        validate_market_snapshot({k: v for k, v in valid.items() if k != "symbol"})
    with pytest.raises(ValueError, match="extra"):
        validate_market_snapshot(valid | {"demo": True})
