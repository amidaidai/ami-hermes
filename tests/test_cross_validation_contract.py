from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cross_validation import build_source_matrix, evaluate_cross_validation  # type: ignore[import-not-found]


def test_core_sources_are_explicitly_marked_as_final_verdict_inputs():
    engine = {
        "_tv_five_tf_required": True,
        "_tv_five_tf_status": {"usable": True, "scope": "direct_cache", "coverage": 5},
        "_tv_live_status": {"usable": True, "age_minutes": 2},
        "_binance_data_collected": True,
        "prices": {"primary": 100.0, "futures": 100.0},
        "funding": {"rate_pct": "0.01%"},
        "oi": {"value": 1000},
        "_tv_sub": {"composite": 10},
        "x_sentiment": {"_source_status": "not_run"},
    }
    dual = {"asset_is_crypto": True, "valid_code": 2, "conflict": False}

    # 2026-09-14：cg_pro 退役后，这里用 macro 充当「非授权上下文源」样本。
    rows = build_source_matrix("BTCUSDT", engine, dual, pipeline_steps=["tv", "binance", "macro", "x_sent"])
    by_id = {row["id"]: row for row in rows}

    assert by_id["tv_five_tf"]["status"] == "live"
    assert by_id["tv_five_tf"]["entered_final_verdict"] is True
    assert by_id["haldro"]["entered_final_verdict"] is True
    assert by_id["macro"]["entered_final_verdict"] is False
    assert by_id["x_sentiment"]["entered_final_verdict"] is False
    assert "cg_pro" not in by_id, "退役的 cg_pro 不得再出现在来源矩阵里"


def test_optional_source_failure_degrades_without_blocking_core_verdict():
    engine = {
        "_tv_five_tf_required": True,
        "_tv_five_tf_status": {"usable": True, "scope": "direct_cache", "coverage": 5},
        "_tv_live_status": {"usable": True},
        "_binance_data_collected": True,
        "prices": {"primary": 100.0, "futures": 100.0},
        "_tv_sub": {"composite": 10},
    }
    dual = {"asset_is_crypto": True, "valid_code": 2, "conflict": False}
    evaluation = evaluate_cross_validation(
        build_source_matrix("BTCUSDT", engine, dual, pipeline_steps=["tv", "binance", "macro"])
    )

    assert evaluation["state"] == "degraded"
    assert evaluation["hard_blockers"] == []
    assert "macro" in evaluation["warnings"]


def test_missing_required_tv_snapshot_blocks_full_verdict():
    engine = {
        "_tv_five_tf_required": True,
        "_tv_five_tf_status": {"usable": False, "coverage": 4, "missing": ["5m"]},
        "_tv_live_status": {"usable": True},
        "_binance_data_collected": True,
        "prices": {"primary": 100.0, "futures": 100.0},
        "_tv_sub": {"composite": 10},
    }
    dual = {"asset_is_crypto": True, "valid_code": 2, "conflict": False}
    evaluation = evaluate_cross_validation(
        build_source_matrix("BTCUSDT", engine, dual, pipeline_steps=["tv", "binance"])
    )

    assert evaluation["state"] == "blocked"
    assert evaluation["hard_blockers"] == ["tv_five_tf"]


def test_unusable_core_status_is_not_misread_as_live():
    engine = {
        "_tv_live_status": {"usable": False, "reason": "缓存过期"},
        "_binance_data_collected": True,
        "prices": {"primary": 100.0, "futures": 100.0},
    }
    rows = build_source_matrix("BTCUSDT", engine, {"asset_is_crypto": True}, pipeline_steps=["tv", "binance"])
    evaluation = evaluate_cross_validation(rows)

    assert "tv_main" in evaluation["hard_blockers"]


def test_x_sentiment_can_never_become_a_hard_blocker():
    engine = {
        "x_sentiment": {"_source_status": "stale_cache"},
    }
    rows = build_source_matrix("BTCUSDT", engine, {"asset_is_crypto": True}, pipeline_steps=["x_sent"])
    evaluation = evaluate_cross_validation(rows)

    assert "x_sentiment" not in evaluation["hard_blockers"]


def test_generic_tv_preflight_does_not_override_an_unusable_live_cache():
    rows = build_source_matrix(
        "XAUUSD",
        {
            "_tv_preflight_ok": True,
            "_tv_live_status": {"usable": False, "reason": "缓存过期"},
        },
        {"asset_is_crypto": False},
        pipeline_steps=["tv"],
    )
    tv = next(row for row in rows if row["id"] == "tv_main")

    assert tv["status"] == "unavailable"


def test_gold_full_exposes_five_timeframe_contract_as_a_hard_gate():
    rows = build_source_matrix(
        "XAUUSD",
        {
            "_tv_five_tf_required": True,
            "_tv_five_tf_status": {"usable": False, "coverage": 4, "missing": ["5m"]},
            "_tv_live_status": {"usable": True},
        },
        {"asset_is_crypto": False},
        pipeline_steps=["tv"],
    )
    by_id = {row["id"]: row for row in rows}

    assert by_id["tv_five_tf"]["status"] == "unavailable"
    assert by_id["tv_five_tf"]["role"] == "hard_gate"
    assert by_id["tv_five_tf"]["entered_final_verdict"] is True
    assert "tv_five_tf" in evaluate_cross_validation(rows)["hard_blockers"]


def test_gold_pair_contract_exposes_5m_action_failure_as_a_hard_gate():
    rows = build_source_matrix(
        "XAUUSD",
        {
            "asset_class": "gold",
            "_tv_five_tf_required": True,
            "_tv_five_tf_status": {"usable": True, "coverage": 5},
            "_xau_tv_contract": {
                "usable": False,
                "reason": "XAU主周期行动格过期",
                "state": {"usable": True},
                "live": {"usable": False, "reason": "行动格过期"},
            },
            "_tv_live_status": {"usable": True},
        },
        {"asset_is_crypto": False},
        pipeline_steps=["tv"],
    )
    by_id = {row["id"]: row for row in rows}
    evaluation = evaluate_cross_validation(rows)

    assert by_id["tv_action_5m"]["status"] == "unavailable"
    assert by_id["tv_action_5m"]["role"] == "hard_gate"
    assert "tv_action_5m" in evaluation["hard_blockers"]
