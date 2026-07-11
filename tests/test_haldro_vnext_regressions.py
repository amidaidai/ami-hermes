from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINE = ROOT / "outputs" / "indicator-audit-20260710" / "HALDRO_AggVol_optimized.pine"


def _source():
    return PINE.read_text(encoding="utf-8")


def test_lsr_crowding_direction_and_confirm_penalty_are_consistent():
    text = _source()
    lsr_line = next(line for line in text.splitlines() if "string lsrTxtA" in line)
    score_line = next(line for line in text.splitlines() if "int confirmScoreA" in line)
    assert "lsrA > 1.3 ? ' · 多头拥挤'" in lsr_line
    assert "lsrA < 0.8 ? ' · 空头拥挤'" in lsr_line
    effective_line = next(line for line in text.splitlines() if "int effectiveConfirmsA" in line)
    assert "- (lsrCrowdingRiskA ? 1 : 0)" in effective_line
    assert "effectiveConfirmsA" in score_line


def test_haldro_exports_valid_and_risk_codes_for_python_authority():
    text = _source()
    assert 'plot(haldroValidCodeA, "HALDRO Valid Code"' in text
    assert 'plot(haldroRiskCodeA, "HALDRO Risk Code"' in text
    assert 'plot(1, "CVD Method Code"' in text
