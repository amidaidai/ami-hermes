from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from risk_constitution_v2 import evaluate_risk


def _inputs(**overrides):
    data = {
        "symbol": "BTCUSDT", "account_balance": 100.0,
        "entry_price": 100.0, "stop_price": 99.0, "target_price": 102.5,
        "atr": 1.0, "atr_pct": 0.01, "regime_multiplier": 1.0,
        "current_drawdown_pct": 0.0, "has_major_news": False,
        "volatility_24h_pct": 0.02, "current_bar": 100,
        "total_exposure_pct": 0.0, "corr_high": False,
    }
    data.update(overrides)
    return data


def test_regime_multiplier_is_risk_divisor():
    normal = evaluate_risk(_inputs(regime_multiplier=1.0))
    high_risk = evaluate_risk(_inputs(regime_multiplier=2.0))
    assert normal["allowed"] and high_risk["allowed"]
    assert high_risk["risk_usd"] == normal["risk_usd"] / 2
    assert high_risk["position_size"] == normal["position_size"] / 2


def test_zero_regime_multiplier_blocks_trade():
    result = evaluate_risk(_inputs(regime_multiplier=0.0))
    assert result["allowed"] is False
    assert result["risk_usd"] == 0.0
    assert "体制禁做" in result["violations"]


def test_invalid_stop_atr_band_blocks_trade():
    result = evaluate_risk(_inputs(stop_price=95.0, atr=1.0))
    assert result["allowed"] is False
    assert any("ATR" in item for item in result["violations"])


def test_news_and_portfolio_are_final_hard_guards():
    news = evaluate_risk(_inputs(has_major_news=True))
    exposure = evaluate_risk(_inputs(total_exposure_pct=16.0))
    corr = evaluate_risk(_inputs(corr_high=True))
    assert not news["allowed"] and any("新闻" in v for v in news["violations"])
    assert not exposure["allowed"] and any("组合" in v for v in exposure["violations"])
    assert not corr["allowed"] and any("相关" in v for v in corr["violations"])


def test_risk_output_has_single_executable_position_size():
    result = evaluate_risk(_inputs())
    assert result["allowed"] is True
    assert result["risk_usd"] > 0
    assert result["position_size"] == result["risk_usd"] / 1.0
    assert result["risk_tier"] in {"normal", "light", "half"}
