from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from xau_tv_sync import _parse_ohlcv


def test_xau_ohlcv_parser_uses_structured_second_last_closed_bar():
    payload = {
        "success": True,
        "last_5_bars": [
            {"time": 1, "open": 4100, "high": 4110, "low": 4090, "close": 4105, "volume": 100},
            {"time": 2, "open": 4105, "high": 4999, "low": 1001, "close": 1704, "volume": 999},
        ],
    }
    out = _parse_ohlcv(json.dumps(payload), "{}")
    assert out == {
        "open": 4100.0, "high": 4110.0, "low": 4090.0,
        "close": 4105.0, "change_pct": 0.12195121951219512,
    }


def test_xau_sync_uses_explicit_tradingview_resolutions():
    source = (ROOT / "scripts" / "xau_tv_sync.py").read_text(encoding="utf-8")
    assert '("5m", "5")' in source
    assert '("15m", "15")' in source
    assert '("1h", "60")' in source
    assert '("4h", "240")' in source
