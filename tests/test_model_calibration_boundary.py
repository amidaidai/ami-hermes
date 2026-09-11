"""A stale reliable flag alone must not influence model selection."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from decision_regime import DecisionRegime
from model_router import select_primary_model


@pytest.mark.parametrize("override", [
    {"decisive_samples": 1, "wins": 1, "losses": 0, "calibrated_win_rate": 1.0},
    {"decisive_samples": None},
    {"reliable": "true"},
    {"calibrated_win_rate": float("nan")},
    {"calibrated_win_rate": 2.0},
    {"calibrated_win_rate": 0.9},
    {"wins": 29},
    {"min_samples": 60},
    {"decisive_samples": True},
])
def test_invalid_calibration_cannot_change_routing(override):
    cal = dict(reliable=True, decisive_samples=30, wins=18, losses=12,
               min_samples=30, calibrated_win_rate=0.6)
    cal.update(override)
    regime = DecisionRegime("trend", "趋势", ("a",), (), 1.0)
    result = select_primary_model([dict(model_id="a", quality=80, rr=2)],
                                  regime, calibration={"trend|a": cal})
    assert "calibration" not in result["score_components"]


def test_consistent_decisive_calibration_can_contribute():
    regime = DecisionRegime("trend", "趋势", ("a",), (), 1.0)
    cal = dict(reliable=True, decisive_samples=30, wins=18, losses=12,
               min_samples=30, calibrated_win_rate=0.6)
    result = select_primary_model([dict(model_id="a", quality=80, rr=2)],
                                  regime, calibration={"trend|a": cal})
    assert result["score_components"]["calibration"] == 6.0
