"""Tests for the quick/inherit/full analysis contract."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "scripts" / "pipeline_router.py"
sys.path.insert(0, str(ROOT / "scripts"))


def router():
    spec = importlib.util.spec_from_file_location("router_modes", ROUTER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mode_resolution():
    r = router()
    assert r.resolve_analysis_mode("看一下BTC") == "quick"
    assert r.resolve_analysis_mode("现在呢", has_context=True) == "standard"
    assert r.resolve_analysis_mode("现在呢", has_context=False) == "standard"
    assert r.resolve_analysis_mode("继续", has_context=False) == "standard"
    assert r.resolve_analysis_mode("全面分析BTC") == "full"
    assert r.resolve_analysis_mode("全周期") == "full"


def test_quick_and_inherit_are_lightweight():
    r = router()
    assert r.route_pipeline("BTCUSDT", "quick") == ["tv", "binance", "card"]
    assert r.route_pipeline("BTCUSDT", "inherit") == ["tv", "binance", "card"]
    assert r.route_pipeline("BTCUSDT", "standard") == ["tv", "binance", "card"]
    assert "macro" not in r.route_pipeline("BTCUSDT", "quick")
    assert "x_sent" not in r.route_pipeline("BTCUSDT", "inherit")


def test_context_path_is_symbol_scoped():
    r = router()
    assert r.context_file("BTCUSDT").name == "analysis_context_BTCUSDT.json"
    assert r.context_file("BINANCE:BTCUSDT.P").name == "analysis_context_BINANCE_BTCUSDT.P.json"


def test_context_loader_rejects_wrong_symbol(tmp_path, monkeypatch):
    r = router()
    monkeypatch.setattr(r, "context_file", lambda symbol: tmp_path / "ctx.json")
    (tmp_path / "ctx.json").write_text('{"symbol":"ETHUSDT","updated_epoch":9999999999}', encoding="utf-8")
    assert r.load_analysis_context("BTCUSDT") is None


def test_context_save_persists_compact_five_timeframe_evidence(tmp_path, monkeypatch):
    r = router()
    monkeypatch.setattr(r, "context_file", lambda symbol: tmp_path / "ctx.json")
    timeframes = {
        tf: {
            "close": 100.0,
            "high": 101.0,
            "low": 99.0,
            "poc": 100.0,
            "tv_action_grid": {"方向": f"{tf}方向"},
            "tv_lines": [1, 2],
        }
        for tf in ("D", "4h", "1h", "15m", "5m")
    }

    r.save_analysis_context(
        "BTCUSDT", mode="full", price=100.0, timeframes=timeframes,
        macro={"dxy": 100.5, "vix": 18.0},
        final_verdict={
            "state": "WAIT", "executable": False, "side": "neutral",
            "reason": "等待触发", "blockers": ["trigger"],
        },
        primary_action={"state": "WAIT", "execution": "不执行·WAIT", "watch_entry": 100.0},
        source_matrix=[{"id": "tv_five_tf", "status": "live", "role": "hard_gate", "entered_final_verdict": True,
                        "timestamp": "2026-09-02T11:59:00+00:00", "source_error": None, "payload_present": True}],
    )
    saved = __import__("json").loads((tmp_path / "ctx.json").read_text(encoding="utf-8"))

    assert list(saved["timeframes"]) == ["D", "4h", "1h", "15m", "5m"]
    assert saved["timeframes"]["15m"]["tv_action_grid"]["方向"] == "15m方向"
    assert "tv_lines" not in saved["timeframes"]["15m"]
    assert saved["macro"] == {"dxy": 100.5, "vix": 18.0}
    assert saved["context_schema_version"] == 2
    assert saved["final_verdict"]["state"] == "WAIT"
    assert saved["primary_action"]["execution"] == "不执行·WAIT"
    assert saved["source_matrix"][0]["id"] == "tv_five_tf"
    assert saved["source_matrix"][0]["timestamp"] == "2026-09-02T11:59:00+00:00"
    assert saved["source_matrix"][0]["payload_present"] is True
    assert saved["keylevels_revision"]


def test_monitor_contract_does_not_use_legacy_levels_as_source():
    source = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert 'analysis_setup_{symbol.replace' in source
    assert 'DATA / "monitor_levels.json"' not in source


def test_every_supported_asset_has_cross_validation_profile():
    r = router()
    for symbol in ("BTCUSDT", "XAUUSD", "EURUSD", "AAPL", "ES", "BTC-29MAR24-60000-C"):
        profile = r.asset_analysis_profile(symbol)
        assert profile["asset_class"] in {"crypto", "gold", "forex", "stock", "futures", "option"}
        assert profile["primary_timeframe"] in profile["timeframes"]
        assert profile["cross_validation_sources"]
        assert profile["x_model_role"] == "sentiment_catalyst_only"
        assert "final_verdict" in profile["forbidden_overrides"]


def test_mode_specs_distinguish_snapshot_update_and_full_analysis():
    r = router()
    assert r.analysis_mode_spec("quick")["refresh_scope"] == "execution_only"
    assert r.analysis_mode_spec("inherit")["refresh_scope"] == "execution_plus_context"
    assert r.analysis_mode_spec("standard")["refresh_scope"] == "execution_plus_context"
    assert r.analysis_mode_spec("full")["refresh_scope"] == "all_sources"
    assert r.analysis_mode_spec("full")["requires_new_screenshot"] is True


def test_auto_card_honors_route_boundaries_for_full_only_sources():
    source = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    grok_block = source[source.index("# ═══ Step 3: Grok催化剂验证"):source.index("# ═══ Step 4: 市场热点搜索")]
    options_block = source[source.index("# ═══ 期权链"):source.index("# ═══ X情绪上下文读取")]
    x_block = source[source.index("# ═══ X情绪上下文读取"):source.index("# ═══ Step 6: 市场体制")]
    macro_block = source[source.index("# v2.1: 实时事件禁做"):source.index("# v2.0: 合并TV数据")]

    assert 'effective_mode == "full"' in grok_block
    assert '"options_chain" in pipeline_steps' in options_block
    assert '"x_sent" in pipeline_steps' in x_block
    assert '"macro" in pipeline_steps' in macro_block
    assert 'pipeline_steps = ["tv","binance","card"] if effective_mode != "full"' in source


def test_model_engine_exposes_a_reduced_execution_scope_for_quick_modes():
    import multi_model_engine as engine

    quick_models = engine.model_scope("quick")
    full_models = engine.model_scope("full")

    assert "VWAP反抽" in quick_models
    assert "POC拒绝" in quick_models
    assert "关联套利" not in quick_models
    assert "费率极端反转" not in quick_models
    assert len(quick_models) < len(full_models)


def test_quick_modes_skip_full_advanced_orderflow_pass():
    source = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    block = source[source.index("# v4.4: 高级订单流确认"):source.index("# v6.9.14: TV DMI")]
    assert 'if effective_mode == "full"' in block
    assert 'adv = {"section": "当前档位跳过高级订单流"' in block


def test_monitor_route_is_event_only_and_never_renders_analysis_card():
    r = router()
    for symbol in ("BTCUSDT", "XAUUSD", "EURUSD", "AAPL", "ES"):
        assert "card" not in r.route_pipeline(symbol, "monitor")


def test_x_model_cannot_become_execution_authority():
    r = router()
    assert r.x_model_can_override_final_verdict() is False


def test_grok_validation_is_observational_and_cannot_change_engine_confidence():
    source = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    grok_block = source[source.index("# ═══ Step 3: Grok催化剂验证"):source.index("# ═══ Step 4: 市场热点搜索")]
    assert 'merged["global_confidence"] = round(merged["global_confidence"] + 0.05, 3)' not in grok_block
    assert 'merged["action"] = "⚠Grok分歧→B等待"' not in grok_block


def test_data_envelope_rejects_invalid_identity_and_preserves_source():
    from contracts import DataEnvelope, validate_data_envelope
    good = DataEnvelope(source="binance", symbol="BTCUSDT", timeframe="15m", timestamp=1, value=100.0, quality="A")
    assert validate_data_envelope(good)["source"] == "binance"
    try:
        validate_data_envelope({**good, "value": 0})
    except ValueError as exc:
        assert "value" in str(exc)
    else:
        raise AssertionError("invalid envelope accepted")


def test_free_api_quota_failure_is_visible_and_does_not_abort_pipeline(tmp_path, monkeypatch):
    import multi_source_collector as collector  # type: ignore[import-not-found]
    monkeypatch.setattr(collector, "CACHE", tmp_path / "api_cache.json")
    monkeypatch.setattr(collector, "SOURCE_STATE", tmp_path / "source_circuit_state.json")
    result = collector._cached("cg_quota", lambda: (_ for _ in ()).throw(RuntimeError("HTTP 429 rate limit")))
    assert result["_source_status"] == "unavailable"
    assert result["_source_error"] == "quota_or_rate_limited"
    assert result["_source_cached"] is False


def test_free_api_failure_uses_stale_cache_with_explicit_status(tmp_path, monkeypatch):
    import json
    import time
    import multi_source_collector as collector  # type: ignore[import-not-found]
    monkeypatch.setattr(collector, "CACHE", tmp_path / "api_cache.json")
    collector.CACHE.write_text(json.dumps({"cg": {"ts": time.time() - 9999, "data": {"rotation": "同步"}}}), encoding="utf-8")
    result = collector._cached("cg", lambda: (_ for _ in ()).throw(RuntimeError("HTTP 403 forbidden")), ttl=1)
    assert result["rotation"] == "同步"
    assert result["_source_status"] == "stale_cache"
    assert result["_source_error"] == "credential_or_plan_blocked"


def test_quota_circuit_breaker_prevents_repeated_calls(tmp_path, monkeypatch):
    import multi_source_collector as collector  # type: ignore[import-not-found]
    monkeypatch.setattr(collector, "CACHE", tmp_path / "api_cache.json")
    monkeypatch.setattr(collector, "SOURCE_STATE", tmp_path / "source_circuit_state.json")
    calls = []
    failing = lambda: calls.append(1) or (_ for _ in ()).throw(RuntimeError("429 too many requests"))
    first = collector._cached("cg_breaker", failing)
    second = collector._cached("cg_breaker", failing)
    assert first["_source_status"] == "unavailable"
    assert second["_source_status"] == "quota_cooldown"
    assert len(calls) == 1
