from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_preflight
import data_freshness_watchdog as freshness
import telegram_reliable
from atomic_json import atomic_write_json
from go_nogo_gate import check_gate


TZ = timezone(timedelta(hours=8))


def _final(state: str = "GO-A", executable: bool = True) -> dict:
    return {
        "state": state,
        "executable": executable,
        "reason": "测试裁决",
        "entry": 100.0 if executable else None,
        "stop": 98.0 if executable else None,
        "target": 105.0 if executable else None,
    }


def _engine(final: dict | None = None) -> dict:
    return {
        "_snapshot_age_h": 0.1,
        "_tv_main": {"grade": "A多"},
        "_tv_cache_status": {"usable": True, "reason": "测试现场已验证"},
        "_final_verdict": final if final is not None else _final(),
        "_banned_live": False,
        "_reviews_count": 20,
        "_wfo_efficiency": 0.72,
        "_total_exposure_pct": 0,
    }


def _meta() -> dict:
    return {"data_grade": "A", "rr_a": 2.5, "rr_b": 1.8, "protections_status": "通过", "status": "A多"}


def test_check_gate_uses_final_verdict_as_only_execution_authority():
    engine = _engine()
    engine["_dual_indicator_verdict"] = {
        "asset_is_crypto": True,
        "usable": True,
        "valid_code": 2,
        "conflict": True,
        "hard_conflict": True,
    }

    result = check_gate("BTCUSDT", engine, _meta())

    assert result["go"] is True
    assert result["execution_authorized"] is True
    assert "dual_indicator" in result["diagnostic_red_gates"]


def test_check_gate_rejects_unknown_final_state_even_if_executable_flag_is_true():
    result = check_gate("BTCUSDT", _engine(_final("BROKEN", True)), _meta())

    assert result["go"] is False
    assert result["execution_authorized"] is False
    assert result["final_state"] == "NO-GO"
    assert "final_verdict" in result["red_gates"]


def test_atomic_json_write_replaces_complete_payload_without_staging_file(tmp_path):
    path = tmp_path / "state.json"

    atomic_write_json(path, {"state": "running", "value": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"state": "running", "value": 1}

    atomic_write_json(path, {"state": "complete", "value": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"state": "complete", "value": 2}
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_preflight_does_not_treat_file_mtime_as_market_timestamp(tmp_path, monkeypatch):
    path = tmp_path / "cache.json"
    path.write_text(json.dumps({"symbol": "BTCUSDT", "value": 1}), encoding="utf-8")

    result = audit_preflight.cache_report("cache.json", 1, expected_symbol="BTCUSDT", data_dir=tmp_path)

    assert result["fresh"] is False
    assert result["timestamp"] is None
    assert "时间戳" in result["reason"]


def test_freshness_watchdog_marks_unstamped_payload_as_degraded(tmp_path):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps({"symbol": "BTCUSDT", "value": 1}), encoding="utf-8")

    result = freshness._payload_health(path, threshold_hours=1)

    assert result["fresh"] is False
    assert result["status"] == "unavailable"
    assert "时间戳" in result["reason"]


def test_freshness_watchdog_accepts_explicit_recent_timestamp(tmp_path):
    path = tmp_path / "payload.json"
    stamp = datetime.now(TZ).isoformat()
    path.write_text(json.dumps({"symbol": "BTCUSDT", "updated_at": stamp, "value": 1}), encoding="utf-8")

    result = freshness._payload_health(path, threshold_hours=1)

    assert result["fresh"] is True
    assert result["timestamp"] is not None


def test_freshness_watchdog_does_not_promote_fresh_unusable_payload(tmp_path):
    path = tmp_path / "payload.json"
    stamp = datetime.now(TZ).isoformat()
    path.write_text(json.dumps({"symbol": "BTCUSDT", "updated_at": stamp, "usable": False}), encoding="utf-8")

    result = freshness._payload_health(path, threshold_hours=1)

    assert result["fresh"] is False
    assert result["status"] == "stale_cache"


def test_automated_delivery_requires_an_explicit_target(monkeypatch):
    monkeypatch.setenv("TANGXI_ENABLE_AUTOMATED_TG", "1")
    monkeypatch.delenv("TANGXI_AUTOMATED_TG_TARGET", raising=False)

    ok, reason = telegram_reliable.push_tg_rich("telegram:-1003733144325:846", "test")

    assert ok is False
    assert reason == "automated_delivery_target_missing"


def test_automated_delivery_uses_configured_target_not_legacy_argument(monkeypatch):
    calls = []
    monkeypatch.setenv("TANGXI_ENABLE_AUTOMATED_TG", "1")
    monkeypatch.setenv("TANGXI_AUTOMATED_TG_TARGET", "telegram:-1003733144325:386")

    class _Daytime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 2, 12, 0, tzinfo=tz)

    monkeypatch.setattr(telegram_reliable, "datetime", _Daytime)
    monkeypatch.setattr(
        telegram_reliable,
        "send_telegram_reliable",
        lambda target, text, **kwargs: calls.append((target, text, kwargs)) or (True, "sent"),
    )

    ok, reason = telegram_reliable.push_tg_rich("telegram:-1003733144325:846", "test")

    assert ok is True
    assert reason == "sent"
    assert calls[0][0] == "telegram:-1003733144325:386"


def test_preflight_flags_stale_direct_push_instructions_on_enabled_no_agent_jobs():
    jobs = [{
        "name": "legacy",
        "enabled": True,
        "no_agent": True,
        "prompt": "必须推送 386，并调用 send_telegram_reliable",
    }]

    issues = audit_preflight.cron_policy_issues(jobs)

    assert issues == ["legacy:过期直接推送指令"]


def test_preflight_accepts_local_only_event_prompt():
    jobs = [{
        "name": "local",
        "enabled": True,
        "no_agent": True,
        "prompt": "仅运行本地 Quick 分析，默认不推送 Telegram、不下单。",
    }]

    assert audit_preflight.cron_policy_issues(jobs) == []


def test_preflight_flags_enabled_cron_runtime_failure():
    jobs = [{"name": "guard", "enabled": True, "state": "scheduled", "last_status": "error"}]

    assert audit_preflight.cron_runtime_issues(jobs) == ["guard:最近运行失败(error)"]


def test_preflight_ignores_disabled_cron_runtime_failure():
    jobs = [{"name": "old", "enabled": False, "state": "disabled", "last_status": "error"}]

    assert audit_preflight.cron_runtime_issues(jobs) == []
