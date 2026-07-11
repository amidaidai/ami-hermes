from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from feature_builder import build_regime_features, ohlcv_from_binance_klines


def _series(n=80, trend=True):
    closes = [100 + i * 0.5 for i in range(n)] if trend else [100 + (1 if i % 2 else -1) for i in range(n)]
    return {
        "opens": [c - 0.2 for c in closes],
        "highs": [c + 0.6 for c in closes],
        "lows": [c - 0.6 for c in closes],
        "closes": closes,
        "volumes": [100 + (i % 5) * 10 for i in range(n)],
    }


def test_feature_builder_uses_closed_ohlcv_and_tv_value_area():
    out = build_regime_features(_series(), {"vah": 150, "val": 90, "vwap": 138})
    assert out is not None
    assert out["adx"] >= 20
    assert out["atr_ratio"] > 0
    assert out["ema_spread_atr"] > 0
    assert 0 <= out["va_stay_ratio_20"] <= 1
    assert out["rvol"] > 0
    assert out["vwap_distance_atr"] is not None


def test_feature_builder_returns_none_when_history_is_insufficient():
    short = {k: v[:10] for k, v in _series().items()}
    assert build_regime_features(short, {}) is None


def test_binance_raw_klines_drop_current_open_bar():
    rows = []
    for i in range(61):
        rows.append([i, str(100 + i), str(101 + i), str(99 + i), str(100.5 + i), str(1000 + i)])
    out = ohlcv_from_binance_klines(rows, drop_open_bar=True)
    assert len(out["closes"]) == 60
    assert out["closes"][-1] == 159.5
    assert out["volumes"][-1] == 1059.0


def test_feature_builder_handles_range_as_frequent_vwap_crosses():
    out = build_regime_features(_series(trend=False), {"vah": 102, "val": 98, "vwap": 100})
    assert out is not None
    assert out["vwap_crosses_20"] >= 10
    assert out["va_stay_ratio_20"] >= 0.9
