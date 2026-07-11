from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision_regime import classify_decision_regime
from model_router import select_primary_model


def _trend():
    return classify_decision_regime(
        adx=30, atr_ratio=1.0, ema_spread_atr=0.7,
        vwap_crosses_20=1, va_stay_ratio_20=0.2,
        displacement_atr=0.8, rvol=1.1,
    )


def test_router_filters_by_regime_and_returns_one_primary():
    candidates = [
        {"model_id": "value_rotation", "rr": 3.0, "quality": 95},
        {"model_id": "fvg_pullback", "rr": 2.2, "quality": 80},
        {"model_id": "vwap_pullback", "rr": 2.5, "quality": 70},
    ]
    result = select_primary_model(candidates, _trend())
    assert result is not None
    assert result["model_id"] == "fvg_pullback"
    assert result["route_rank"] == 1
    assert len([c for c in result["evaluated"] if c["selected"]]) == 1


def test_router_does_not_treat_legacy_confidence_as_probability():
    candidates = [
        {"model_id": "fvg_pullback", "rr": 2.1, "quality": 80, "confidence": 55},
        {"model_id": "ob_pullback", "rr": 2.0, "quality": 60, "confidence": 95},
    ]
    result = select_primary_model(candidates, _trend())
    assert result["model_id"] == "fvg_pullback"
    assert "confidence" not in result["score_components"]


def test_router_returns_none_when_no_model_fits_regime():
    result = select_primary_model([{"model_id": "value_rotation", "rr": 3, "quality": 90}], _trend())
    assert result is None
