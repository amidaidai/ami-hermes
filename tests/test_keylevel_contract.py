import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_expired_or_disabled_levels_are_not_active():
    guard = load("keylevel_guard.py")
    assert guard.level_is_active({"price": 1, "enabled": False}, 100) is False
    assert guard.level_is_active({"price": 1, "valid_until": 99}, 100) is False
    assert guard.level_is_active({"price": 1, "valid_until": 101}, 100) is True


def test_trigger_is_price_event_not_trade_signal(tmp_path, monkeypatch):
    guard = load("keylevel_guard.py")
    monkeypatch.setattr(guard, "DATA", tmp_path)
    level = {"name": "测试位", "price": 100, "source": "keylevels_config"}
    guard.split_trigger("BTCUSDT", level, 101, "up", revision="abc123")
    data = json.loads((tmp_path / "trigger_BTCUSDT.json").read_text(encoding="utf-8"))
    assert data["event_type"] == "keylevel_cross"
    assert data["event_class"] == "price_cross_only"
    assert data["analysis_required"] is True
    assert data["analysis_status"] == "pending"
    assert data["config_revision"] == "abc123"


def test_dispatcher_always_uses_quick_without_direction():
    dispatcher = load("keylevel_analysis_dispatcher.py")
    command = dispatcher.dispatch_command("BTCUSDT")
    assert command[-1] == "--quick"
    assert "--push" not in command


def test_reader_ignores_already_processed_trigger():
    source = (ROOT / "scripts" / "keylevel_read_trigger.py").read_text(encoding="utf-8")
    assert 'status == "analyzed"' in source
    assert '"--push"' in source
    assert "retry_count" in source


def test_keylevel_collection_waits_for_svp_recalculation_after_each_switch():
    source = (ROOT / "scripts" / "keylevels_collect.py").read_text(encoding="utf-8")
    assert "INDICATOR_RECALC_SECONDS = 20" in source
    assert "await asyncio.sleep(INDICATOR_RECALC_SECONDS)" in source


def test_keylevel_collection_preserves_closed_bar_ohlcv_and_canonical_tv_wrapper():
    source = (ROOT / "scripts" / "keylevels_collect.py").read_text(encoding="utf-8")
    assert 'wrapper_path = ROOT / "scripts" / "fetch_tv_mcp.py"' in source
    assert "last_closed = bars[-2]" in source
    assert '"open": opening' in source
    assert '"high": high' in source
    assert '"low": low' in source
    assert '"close": close' in source


def test_xau_sync_loads_canonical_tv_wrapper_instead_of_root_shadow():
    source = (ROOT / "scripts" / "xau_tv_sync.py").read_text(encoding="utf-8")
    assert 'wrapper_path = ROOT / "scripts" / "fetch_tv_mcp.py"' in source
    assert 'spec_from_file_location("fetch_tv_mcp", wrapper_path)' in source


def test_keylevel_collector_unwraps_mcp_result_payload():
    collector = load("keylevels_collect.py")
    wrapped = {"success": True, "result": '{"success": true, "studies": [{"name": "SVP"}]}' }
    parsed = collector._j(wrapped)
    assert parsed["studies"][0]["name"] == "SVP"


def test_empty_candidate_pool_is_not_written_as_a_successful_refresh():
    collector = load("keylevels_collect.py")
    # A failed/stale chart read must fail closed instead of replacing a prior
    # candidate pool with an apparently successful empty file.
    source = (ROOT / "scripts" / "keylevels_collect.py").read_text(encoding="utf-8")
    assert "if not cands:" in source
    assert "raise RuntimeError(\"empty candidate pool\")" in source


def test_keylevel_payload_persists_the_actual_five_timeframe_records():
    collector = load("keylevels_collect.py")
    data_by_tf = {tf: {"tf": tf, "price": 100.0} for tf in collector.TFS}

    payload = collector.build_snapshot_payload(
        data_by_tf,
        price=100.0,
        timestamp="2026-09-02T08:00:00+08:00",
        candidates=[{"price": 100.0}],
    )

    assert payload["timeframes_complete"] is True
    assert list(payload["timeframes"]) == list(collector.TFS)
    assert payload["timeframes"]["15"]["price"] == 100.0


def test_xau_sync_validates_all_timeframes_before_writing_snapshot():
    source = (ROOT / "scripts" / "xau_tv_sync.py").read_text(encoding="utf-8")
    assert source.index("missing =") < source.index("atomic_write_json(OUT, payload)")


def test_btc_collector_does_not_overwrite_candidate_file_with_partial_tf_data():
    source = (ROOT / "scripts" / "keylevels_collect.py").read_text(encoding="utf-8")
    assert source.index("missing_timeframes =") < source.index("atomic_write_json(OUT, payload)")