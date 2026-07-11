from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINE = ROOT / "outputs" / "indicator-audit-20260710" / "SVP_production_optimized.pine"


def _source() -> str:
    return PINE.read_text(encoding="utf-8")


def test_cvd_qualified_divergence_uses_swing_and_slope_filters():
    text = _source()
    bear = next(line for line in text.splitlines() if line.startswith("bool cvdBearDivQualified ="))
    bull = next(line for line in text.splitlines() if line.startswith("bool cvdBullDivQualified ="))
    assert "cvdDivSwingOk" in bear and "cvdSlope < 0" in bear
    assert "cvdDivSwingOk" in bull and "cvdSlope > 0" in bull


def test_cvd_star_pairing_matches_distribution_and_absorption():
    text = _source()
    bear = next(line for line in text.splitlines() if line.startswith("cvdBearStars :="))
    bull = next(line for line in text.splitlines() if line.startswith("cvdBullStars :="))
    assert "cvdDistributeSellQualified" in bear
    assert "cvdAbsorbBuyQualified" not in bear
    assert "cvdAbsorbBuyQualified" in bull
    assert "cvdDistributeSellQualified" not in bull


def test_dmi_hot_only_blocks_a_grade_when_price_is_extended_in_trade_direction():
    text = _source()
    long_line = next(line for line in text.splitlines() if line.startswith("bool setupLongA ="))
    short_line = next(line for line in text.splitlines() if line.startswith("bool setupShortA ="))
    assert "not (dmiHot and vwapExtendedUp)" in long_line
    assert "not (dmiHot and vwapExtendedDn)" in short_line
    assert " and not dmiHot and " not in long_line
    assert " and not dmiHot and " not in short_line


def test_nearest_magnet_name_price_score_are_selected_as_one_object():
    text = _source()
    object_block_start = text.index("float d = math.abs(close - lvlC.price)")
    above_block_start = text.index("if lvlC.price > close", object_block_start)
    object_block = text[object_block_start:above_block_start]
    assert object_block.index("float totalScore") < object_block.index("if d < minDist")
    assert "magnetNearestName := lvlC.name" in object_block
    assert "magnetNearestPrice := lvlC.price" in object_block
    assert "magnetScore := int(math.round(math.min(totalScore, 100)))" in object_block
    assert "bestScore" not in text


def test_single_occurrence_dead_pine_variables_are_removed():
    text = _source()
    dead = {
        "tfRoleRec", "marketProfileText", "htfBiasText", "cvdBearDivRaw", "cvdBullDivRaw",
        "actionKillZoneLine", "dxyDirection", "vixText", "oiText", "smtText",
        "dmiVerifyText", "sweepSideName", "eventText", "primaryPlanSideText", "failoverText",
        "replaySideCode", "magnetTargetDist", "magnetTargetScore", "magnetAboveText",
        "magnetBelowText", "replayPlanDistance", "focusHint", "fundingHint", "overlapHint",
        "tfDutyText", "linkMapText", "actionIctText", "actionValueText", "actionVwapText",
        "actionEmaText", "volText", "kzText", "cvdSessionFull", "linkedPlanText",
    }
    for name in dead:
        assert name not in text, f"dead Pine variable remains: {name}"


def test_external_confirmation_requests_live_only_in_python_or_haldro():
    text = _source()
    assert 'request.security("TVC:DXY"' not in text
    assert 'request.security("TVC:VIX"' not in text
    assert "spotTickerForPerp" not in text
    assert 'syminfo.tickerid + "_OI"' not in text
    assert "OI_ENABLE" not in text and "OI_LOOKBACK" not in text
    assert text.count("request.security(") + text.count("request.security_lower_tf(") == 8
