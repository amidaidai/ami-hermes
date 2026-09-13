import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))
import tv_data_bridge as _bridge  # noqa: E402


@pytest.fixture(autouse=True)
def _no_active_analysis_lease(monkeypatch):
    """续航测试不该被真实的交互式分析租约影响。

    btc_tv_refresh.main() 在租约活跃时会「让路」提前 return 0，
    于是「只跑 stale 的那条契约」用例的 called 断言会假红（实测踩到）。
    """
    monkeypatch.setattr(_bridge, "analysis_lease_status",
                        lambda *args, **kwargs: {"active": False})


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


def test_config_health_rejects_levels_after_structure_review_deadline():
    guard = load("keylevel_guard.py")
    reviewed = datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc)
    now = reviewed + timedelta(hours=25)
    config = {
        "auto_approval_policy": {
            "max_structure_age_hours": 24,
            "structure_reviewed_at": reviewed.isoformat(),
        },
        "symbols": {"BTCUSDT": {"levels": [
            {"price": 80000, "enabled": True, "valid_until": (now + timedelta(hours=5)).isoformat()},
        ]}},
    }
    assert guard.config_health(config, now.timestamp())["active_approved_levels"] == 0
    assert guard.config_health(config, now.timestamp())["status"] == "degraded"


def test_silenced_levels_are_idle_not_degraded():
    """用户主动 enabled=false 不是监控崩溃，看门狗不应每两分钟记 error。"""
    guard = load("keylevel_guard.py")
    now = datetime.now(timezone.utc)
    config = {
        "auto_approval_policy": {
            "max_structure_age_hours": 24,
            "structure_reviewed_at": now.isoformat(),
        },
        "symbols": {"BTCUSDT": {"levels": [
            {"name": "VAH", "price": 77310, "enabled": False,
             "valid_until": (now + timedelta(hours=5)).isoformat()},
            {"name": "VAL", "price": 76450, "enabled": False,
             "valid_until": (now + timedelta(hours=5)).isoformat()},
        ]}},
    }
    health = guard.config_health(config, now.timestamp())
    assert health["status"] == "idle"
    assert health["active_approved_levels"] == 0
    assert health["configured_levels"] == 2
    assert health["enabled_levels"] == 0
    assert health["disabled_levels"] == 2


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


def test_collector_supervisor_rejects_false_zero_exit_without_new_publication(tmp_path, monkeypatch):
    collector = load("keylevels_collect.py")
    out = tmp_path / "keylevels_candidates.json"
    out.write_text(
        '{"ts":"old","timeframes_complete":true,"timeframes":{"D":{},"240":{},"60":{},"15":{},"5":{}},"candidates":[1]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(collector, "OUT", out)

    class Child:
        returncode = 0
        stdout = ""
        stderr = ""

    calls = []
    monkeypatch.setattr(collector.subprocess, "run", lambda *args, **kwargs: calls.append(args) or Child())
    assert collector._run_cli() == 1
    assert len(calls) == 2


def test_watchdog_persisted_policy_renews_only_existing_approved_levels(monkeypatch, tmp_path):
    watchdog = load("btc_keylevel_guard_watchdog.py")
    tz = timezone(timedelta(hours=8))
    now = datetime(2026, 9, 4, 20, 0, tzinfo=tz)
    config_path = tmp_path / "keylevels_config.json"
    config_path.write_text(json.dumps({
        "auto_approval_policy": {
            "enabled": True,
            "scope": "existing_levels_only",
            "ttl_hours": 6,
            "renew_before_minutes": 30,
        },
        "symbols": {"BTCUSDT": {"levels": [
            {"name": "approved", "price": 80000, "enabled": True, "valid_until": (now + timedelta(minutes=10)).isoformat()},
            {"name": "disabled", "price": 90000, "enabled": False, "valid_until": (now + timedelta(minutes=10)).isoformat()},
        ]}},
    }), encoding="utf-8")
    monkeypatch.setattr(watchdog, "CONFIG", config_path)

    result = watchdog.auto_renew_existing_approved_levels(now)
    written = json.loads(config_path.read_text(encoding="utf-8"))

    assert result["changed"] is True
    assert result["renewed_count"] == 1
    assert written["symbols"]["BTCUSDT"]["levels"][0]["valid_until"] == (now + timedelta(hours=6)).isoformat()
    assert written["symbols"]["BTCUSDT"]["levels"][1]["valid_until"] == (now + timedelta(minutes=10)).isoformat()
    assert written["approval_renewal"]["source"] == "用户持久授权自动续期(现有批准位)"


def test_watchdog_auto_renew_never_accepts_candidate_promotion_scope(monkeypatch, tmp_path):
    watchdog = load("btc_keylevel_guard_watchdog.py")
    config_path = tmp_path / "keylevels_config.json"
    original = {"auto_approval_policy": {"enabled": True, "scope": "candidate_pool"}, "symbols": {}}
    config_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(watchdog, "CONFIG", config_path)

    result = watchdog.auto_renew_existing_approved_levels()

    assert result == {"changed": False, "error": "unsupported_scope"}
    assert json.loads(config_path.read_text(encoding="utf-8")) == original


def test_watchdog_stops_renewing_when_structure_review_is_too_old(monkeypatch, tmp_path):
    watchdog = load("btc_keylevel_guard_watchdog.py")
    tz = timezone(timedelta(hours=8))
    now = datetime(2026, 9, 5, 18, 0, tzinfo=tz)
    config_path = tmp_path / "keylevels_config.json"
    original = {
        "auto_approval_policy": {
            "enabled": True,
            "scope": "existing_levels_only",
            "ttl_hours": 6,
            "renew_before_minutes": 30,
            "max_structure_age_hours": 24,
            "structure_reviewed_at": (now - timedelta(hours=25)).isoformat(),
        },
        "symbols": {"BTCUSDT": {"levels": [
            {"name": "old", "price": 80000, "enabled": True,
             "valid_until": (now + timedelta(minutes=10)).isoformat()},
        ]}},
    }
    config_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(watchdog, "CONFIG", config_path)

    result = watchdog.auto_renew_existing_approved_levels(now)

    assert result["changed"] is False
    assert result["error"] == "structure_review_required"
    assert json.loads(config_path.read_text(encoding="utf-8")) == original


def test_watchdog_caps_level_expiry_at_structure_review_deadline(monkeypatch, tmp_path):
    watchdog = load("btc_keylevel_guard_watchdog.py")
    tz = timezone(timedelta(hours=8))
    reviewed = datetime(2026, 9, 4, 16, 0, tzinfo=tz)
    now = reviewed + timedelta(hours=22)
    config_path = tmp_path / "keylevels_config.json"
    config_path.write_text(json.dumps({
        "auto_approval_policy": {
            "enabled": True, "scope": "existing_levels_only",
            "ttl_hours": 6, "renew_before_minutes": 30,
            "max_structure_age_hours": 24,
            "structure_reviewed_at": reviewed.isoformat(),
        },
        "symbols": {"BTCUSDT": {"levels": [
            {"price": 80000, "enabled": True, "valid_until": (now + timedelta(minutes=10)).isoformat()},
        ]}},
    }), encoding="utf-8")
    monkeypatch.setattr(watchdog, "CONFIG", config_path)

    result = watchdog.auto_renew_existing_approved_levels(now)
    written = json.loads(config_path.read_text(encoding="utf-8"))

    assert result["changed"] is True
    assert written["symbols"]["BTCUSDT"]["levels"][0]["valid_until"] == (reviewed + timedelta(hours=24)).isoformat()


def test_btc_refresh_skips_when_both_contracts_are_fresh(monkeypatch):
    refresh = load("btc_tv_refresh.py")
    monkeypatch.setattr(refresh, "btc_five_tf_status", lambda: {"usable": True})
    monkeypatch.setattr(refresh, "source_snapshot_status", lambda: {"fresh": True})
    called = []
    monkeypatch.setattr(refresh, "run_collector", lambda: called.append("collector") or 0)
    monkeypatch.setattr(refresh, "refresh_source_snapshot", lambda: called.append("snapshot") or True)

    assert refresh.main() == 0
    assert called == []


def test_btc_refresh_runs_only_the_stale_contract(monkeypatch):
    refresh = load("btc_tv_refresh.py")
    monkeypatch.setattr(refresh, "btc_five_tf_status", lambda: {"usable": False})
    monkeypatch.setattr(refresh, "source_snapshot_status", lambda: {"fresh": True})
    called = []
    monkeypatch.setattr(refresh, "run_collector", lambda: called.append("collector") or 0)
    monkeypatch.setattr(refresh, "refresh_source_snapshot", lambda: called.append("snapshot") or True)

    assert refresh.main() == 0
    assert called == ["collector"]


def test_btc_collector_restores_and_verifies_previous_chart(monkeypatch):
    collector = load("keylevels_collect.py")
    calls = []

    def fake_cli(*args, **kwargs):
        calls.append(args)
        if args == ("state",):
            return json.dumps({"symbol": "OANDA:XAUUSD", "resolution": "5"})
        return "{}"

    monkeypatch.setattr(collector, "_cli", fake_cli)
    monkeypatch.setattr(collector.time, "sleep", lambda _seconds: None)

    assert collector._restore_chart_state({"symbol": "OANDA:XAUUSD", "resolution": "5"}) is True
    assert calls[:2] == [("symbol", "OANDA:XAUUSD"), ("timeframe", "5")]
    assert calls[-1] == ("state",)