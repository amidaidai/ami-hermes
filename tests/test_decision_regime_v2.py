from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision_regime import classify_decision_regime


def test_expansion_has_priority_when_displacement_and_rvol_confirm():
    result = classify_decision_regime(
        adx=28, atr_ratio=1.45, ema_spread_atr=0.8,
        vwap_crosses_20=1, va_stay_ratio_20=0.2,
        displacement_atr=1.2, rvol=1.4,
    )
    assert result.code == "expansion"
    assert "fvg_pullback" in result.allowed_models
    assert "direct_chase" in result.blocked_models


def test_compression_requires_low_atr_and_tight_ema():
    result = classify_decision_regime(
        adx=15, atr_ratio=0.68, ema_spread_atr=0.18,
        vwap_crosses_20=2, va_stay_ratio_20=0.45,
        displacement_atr=0.3, rvol=0.7,
    )
    assert result.code == "compression"
    assert result.position_multiplier > 1.0
    assert result.allowed_models == ("breakout_acceptance",)


def test_trend_and_balance_use_structure_not_vix():
    trend = classify_decision_regime(
        adx=31, atr_ratio=1.0, ema_spread_atr=0.72,
        vwap_crosses_20=1, va_stay_ratio_20=0.25,
        displacement_atr=0.7, rvol=1.0,
    )
    balance = classify_decision_regime(
        adx=16, atr_ratio=1.0, ema_spread_atr=0.2,
        vwap_crosses_20=6, va_stay_ratio_20=0.75,
        displacement_atr=0.4, rvol=0.9,
    )
    assert trend.code == "trend"
    assert "vwap_pullback" in trend.allowed_models
    assert balance.code == "balance"
    assert "value_rotation" in balance.allowed_models


def test_exhaustion_is_overlay_not_a_direction():
    result = classify_decision_regime(
        adx=34, atr_ratio=1.1, ema_spread_atr=0.9,
        vwap_crosses_20=1, va_stay_ratio_20=0.1,
        displacement_atr=0.8, rvol=1.1,
        adr_remaining_ratio=0.1, vwap_distance_atr=2.8,
    )
    assert result.code == "trend"
    assert result.exhausted is True
    assert result.position_multiplier > 1.0  # 风险除数增大，仓位减小
    assert "追价" in result.reason
