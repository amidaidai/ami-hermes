from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auto_card


def _ohlcv(n=80):
    closes = [100 + i * 0.2 for i in range(n)]
    return {
        "opens": [c - 0.1 for c in closes], "highs": [c + 0.5 for c in closes],
        "lows": [c - 0.5 for c in closes], "closes": closes,
        "volumes": [100 + i % 4 for i in range(n)],
    }


def test_card_final_verdict_uses_real_features_and_hard_conflict():
    engine = {"futures_klines": {"15m": _ohlcv()}, "account_balance": 100.0}
    main = {
        "grade": "A多", "direction_text": "偏多", "entry": 115.8,
        "stop": 114.8, "target": 118.3, "mcp_fvg_quality_score": 80,
        "vwap": 114.0, "vah": 120.0, "val": 105.0,
    }
    dual = {"asset_is_crypto": True, "valid_code": 2, "conflict": True, "hard_conflict": True}
    final = auto_card._resolve_card_final_verdict(
        "BTCUSDT", {"status": "A多", "direction": "long"}, engine,
        main, dual, {"stop": 114.8, "target": 118.3, "rr": 2.5, "atr": 1.0}, "FVG回踩",
    )
    assert final["state"] == "NO-GO"
    assert final["entry"] is None
    assert engine["_decision_regime"]["code"] in {"trend", "expansion"}
    assert engine["_final_verdict"]["state"] == "NO-GO"


def test_card_final_verdict_routes_one_primary_model_by_regime():
    engine = {
        "futures_klines": {"15m": _ohlcv()}, "account_balance": 100.0,
        "_candidate_plans": [
            {"model_id": "value_rotation", "entry": 115.8, "stop": 114.8, "target": 119.0, "rr": 3.2, "quality": 95},
            {"model_id": "fvg_pullback", "entry": 115.8, "stop": 114.8, "target": 118.3, "rr": 2.5, "quality": 80},
        ],
    }
    main = {"grade": "A多", "direction_text": "偏多", "entry": 115.8, "stop": 114.8,
            "target": 118.3, "mcp_fvg_quality_score": 80, "vwap": 114, "vah": 120, "val": 105}
    dual = {"asset_is_crypto": True, "valid_code": 2, "conflict": False, "aligned": True}
    final = auto_card._resolve_card_final_verdict(
        "BTCUSDT", {"status": "A多", "direction": "long"}, engine,
        main, dual, {"stop": 114.8, "target": 118.3, "rr": 2.5, "atr": 1.0}, "无",
    )
    assert final["model_id"] == "fvg_pullback"
    assert engine["_model_route"]["model_id"] == "fvg_pullback"


def test_card_final_verdict_builds_regime_from_closed_binance_rows():
    rows = []
    for i in range(81):
        close = 100 + i * 0.2
        rows.append([i, close - 0.1, close + 0.5, close - 0.5, close, 100 + i % 4])
    engine = {"_raw_klines_multi": {"15m": rows}, "account_balance": 100.0}
    main = {
        "grade": "A多", "direction_text": "偏多", "entry": 115.8,
        "stop": 114.8, "target": 118.3, "mcp_fvg_quality_score": 80,
        "vwap": 114.0, "vah": 120.0, "val": 105.0,
    }
    final = auto_card._resolve_card_final_verdict(
        "BTCUSDT", {"status": "A多", "direction": "long"}, engine,
        main, {"asset_is_crypto": True, "valid_code": 2, "conflict": False},
        {"stop": 114.8, "target": 118.3, "rr": 2.5, "atr": 1.0}, "FVG回踩",
    )
    assert final["state"] in {"GO-A", "GO-B", "WAIT", "NO-GO"}
    assert engine["_decision_ohlcv_source"] == "binance:15m:closed"
    assert engine["_decision_regime"]["code"] in {"trend", "expansion", "balance", "compression"}


def test_shadow_record_contains_replayable_decision_contract(tmp_path):
    rows = []
    for i in range(81):
        close = 100 + i * 0.2
        rows.append([i, close - 0.1, close + 0.5, close - 0.5, close, 100 + i % 4])
    path = tmp_path / "signals.jsonl"
    engine = {
        "_raw_klines_multi": {"15m": rows}, "account_balance": 100.0,
        "_shadow_enabled": True, "_shadow_path": path,
    }
    main = {
        "grade": "A多", "direction_text": "偏多", "entry": 115.8,
        "stop": 114.8, "target": 118.3, "mcp_fvg_quality_score": 80,
        "vwap": 114.0, "vah": 120.0, "val": 105.0,
    }
    final = auto_card._resolve_card_final_verdict(
        "BTCUSDT", {"status": "A多", "direction": "long"}, engine,
        main, {"asset_is_crypto": True, "valid_code": 2, "conflict": False},
        {"stop": 114.8, "target": 118.3, "rr": 2.5, "atr": 1.0}, "FVG回踩",
    )
    import json
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert isinstance(row["main"], dict)
    assert isinstance(row["dual"], dict)
    assert isinstance(row["risk"], dict)
    assert isinstance(row["regime"], dict)
    assert row["regime"]["code"] in {"trend", "expansion", "balance", "compression"}
    from backtest_runner_v2 import replay_shadow_records  # type: ignore[import-not-found]
    replay = replay_shadow_records([row], {row["signal_id"]: []})
    assert replay["total"] == 1
    assert replay["state_stats"] == {final["state"]: 1}


def test_card_final_verdict_textual_wait_entry_does_not_crash(tmp_path):
    engine = {
        "account_balance": 100.0, "_shadow_enabled": True,
        "_shadow_path": tmp_path / "decision_signals.jsonl",
    }
    main = {
        "grade": "C等待", "direction_text": "观望", "entry": "等触发",
        "stop": "—", "target": "待确认", "mcp_fvg_quality_score": 0,
    }
    dual = {"asset_is_crypto": True, "valid_code": 0, "conflict": False}
    final = auto_card._resolve_card_final_verdict(
        "BTCUSDT", {"status": "C等待", "direction": "neutral"}, engine,
        main, dual, {"stop": "—", "target": "待确认", "rr": 0, "atr": "—"}, "无",
    )
    assert final["state"] in {"WAIT", "NO-GO"}
    assert final["entry"] is None
    assert not final["executable"]


def test_textual_tv_plan_uses_numeric_strategy_fallback_for_shadow(tmp_path):
    path = tmp_path / "signals.jsonl"
    engine = {
        "account_balance": 100.0,
        "prices": {"primary": 100.0},
        "_shadow_enabled": True,
        "_shadow_path": path,
    }
    main = {"grade": "C等待", "direction_text": "偏空", "entry": "等触发", "stop": "—", "target": "待确认"}
    dual = {"asset_is_crypto": True, "valid_code": 2, "risk_code": 0, "conflict": False}
    auto_card._resolve_card_final_verdict(
        "BTCUSDT", {"status": "C等待", "direction": "short"}, engine,
        main, dual, {"stop": 102.0, "target": 96.0, "rr": 2.0, "atr": 1.0}, "vwap_pullback",
    )
    import json
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["entry"] == 100.0
    assert row["stop"] == 102.0
    assert row["target"] == 96.0
    assert row["dual"]["valid_code"] == 2


def test_card_projection_uses_final_not_raw_grade():
    projected = auto_card._project_final_verdict(
        {"grade": "A多", "entry": 100, "stop": 98, "target": 105},
        {"state": "WAIT", "executable": False, "side": "neutral", "grade": "C等待", "reason": "R:R不足"},
    )
    assert projected["grade"] == "C等待"
    assert "entry" not in projected
    assert projected["execution"].startswith("不执行")


def test_render_path_consumes_final_verdict_projection():
    source = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert source.count("_resolve_card_final_verdict(") >= 2
    render_slice = source[source.index("dual_indicator = _dual_indicator_verdict"):source.index("# v9.6: 标准出卡统一使用表格驾驶舱")]
    assert "final_verdict = _resolve_card_final_verdict(" in render_slice
    assert "tv_main = _project_final_verdict(tv_main, final_verdict)" in render_slice


def test_tv_live_cache_projects_haldro_valid_code_into_final_decision():
    engine = {}
    cache = {
        "grade": "?", "treatment": "等待",
        "decision_table": {"结论": "等待", "方向": "观望", "信号": "偏多"},
        "indicators": {
            "mcp_side_code": 0, "mcp_grade_code": 0,
            "poc_price": 63954.1, "vah_price": 64348.9, "val_price": 63788.5,
            "haldro_valid_code": 2, "haldro_risk_code": 0,
            "composite": 31, "confirm_score": 4, "coverage_exchanges": 5,
        },
    }
    assert auto_card._tv_live_levels(cache) == (63954.1, 64348.9, 63788.5)
    auto_card._inject_tv_live_pine(engine, cache)
    pine = engine["_tv_pine"]
    dmi = auto_card._parse_tv_dmi_table(pine["tables"])
    vals = auto_card._parse_tv_study_values(pine["studies"])
    engine["_tv_main"] = auto_card._build_tv_main_data(dmi, vals)
    dual = auto_card._dual_indicator_verdict("BTCUSDT", {"status": "C等待"}, engine)
    assert dual["valid_code"] == 2
    assert dual["usable"] is True


def test_xau_fallback_klines_cannot_overwrite_tv_mcp_structure():
    engine = {"klines": {"5m": {"description": "TV MCP", "poc": 4102}}}
    auto_card._merge_collected_klines(
        engine, {"5m": {"description": "Binance XAUUSDT", "poc": 4000}},
        preserve_existing=True,
    )
    assert engine["klines"]["5m"]["description"] == "TV MCP"
    assert engine["klines"]["5m"]["poc"] == 4102


def test_xau_real_tv_state_does_not_disable_live_cache_injection():
    source = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert 'if engine_data.get("_xau_placeholder"):' in source
    assert 'if engine_data.get("_xau_tv_limitation"):' not in source


def test_auto_card_has_no_hardcoded_market_regime_demo_values():
    source = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert "vix=18.5" not in source
    assert "btc_volatility_20d_pct=3.8" not in source
    assert "from regime_classifier import classify_regime" not in source
    assert "from decision_regime import classify_decision_regime" in source


def test_orion_derivatives_fallback_only_fills_missing_fields(monkeypatch):
    import binance_public

    monkeypatch.setattr(
        binance_public,
        "orion_derivatives_snapshot",
        lambda _symbol: {
            "ok": True, "quality": "B", "source": "Orion/Binance Futures",
            "funding": 0.0001, "open_interest": 12345, "oi_change_1h_pct": 1.5,
        },
    )
    engine = {"funding": {"rate": 9.9, "quality": "A"}}
    auto_card._inject_orion_derivatives_fallback(engine, "BTCUSDT")
    assert engine["funding"]["rate"] == 9.9
    assert engine["oi"]["value"] == 12345
    assert engine["oi"]["quality"] == "B"


def test_decision_float_parses_tradingview_unicode_spacing_and_suffixes():
    assert auto_card._decision_float("4,108.636") == 4108.636
    assert auto_card._decision_float("6.6\u202fK") == 6600.0
    assert auto_card._decision_float("−41.73\u202fM") == -41_730_000.0


def test_tv_vwap_ema_fallback_consumes_symbol_specific_data_window(monkeypatch, tmp_path):
    import json

    cache = tmp_path / "tv_live_XAUUSD.json"
    cache.write_text(json.dumps({
        "symbol": "OANDA:XAUUSD", "last_price": "4112.0",
        "indicators": {"s_vwap": "4,108.6", "ema_9": "4,110.3", "ema_55": "4,107.1", "mcp_cvd_value": "4.66\u202fK"},
    }), encoding="utf-8")
    monkeypatch.setattr(auto_card, "_tv_symbol_cache_path", lambda _symbol: cache)
    monkeypatch.setattr(auto_card, "_tv_cache_status", lambda *_args, **_kwargs: {"usable": True})
    result = auto_card._tv_vwap_ema_fallback("XAUUSD")
    assert result["source"] == "TV MCP Data Window"
    assert result["ema"]["9"] == 4110.3
    assert result["ema"]["55"] == 4107.1
    assert result["vwap"]["price_above"] is True
