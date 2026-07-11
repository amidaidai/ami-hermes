from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import depth_wall


def test_oi_price_regime_falls_back_to_orion(monkeypatch):
    monkeypatch.setattr(depth_wall, "_fetch_binance_oi_history", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        depth_wall,
        "_fetch_orion_ticker",
        lambda _symbol: {"tf1h": {"oiChange": 2.0, "changePercent": -1.0}},
    )
    result = depth_wall.oi_price_regime("BTCUSDT")
    assert result["ok"] is True
    assert result["regime"] == "新空进场"
    assert result["source"] == "Orion/Binance"


def test_regime_classification_is_stable():
    assert depth_wall._regime_from_deltas(-2.0, 1.0)[0] == "空头平仓"
    assert depth_wall._regime_from_deltas(-2.0, -1.0)[0] == "多头平仓"
