from __future__ import annotations
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import watchdog as wd


def _reset_guard(tmp_path, monkeypatch):
    """把 watchdog 的 guard/state 文件重定向到 tmp，避免污染真实数据。"""
    guard = tmp_path / "watchdog_guard.json"
    state = tmp_path / "watchdog_state.json"
    monkeypatch.setattr(wd, "GUARD_FILE", guard)
    monkeypatch.setattr(wd, "WATCHDOG_STATE_FILE", state)
    monkeypatch.setattr(wd, "SYSTEM_EVENT_FILE", tmp_path / "system_events.jsonl")
    monkeypatch.setattr(wd, "LOCK_FILE", tmp_path / "monitor.lock")
    # 拦截真正的 Popen，不真启动进程
    monkeypatch.setattr(wd.subprocess, "Popen", lambda *a, **k: type("P", (), {"pid": 999})())
    return guard


def test_emergency_and_normal_buckets_are_separate(tmp_path, monkeypatch):
    guard = _reset_guard(tmp_path, monkeypatch)
    now = time.time()
    # 普通桶已用满 3 次
    guard.write_text(json.dumps({"restart_times": [now, now, now]}), encoding="utf-8")

    # 普通重启应被限速拒绝
    assert wd.start_monitor(emergency=False) is False
    # 真崩溃重启（emergency）应仍被允许 —— 独立桶未满
    assert wd.start_monitor(emergency=True) is True


def test_emergency_budget_larger_than_normal():
    assert wd.MAX_RESTARTS_EMERGENCY > wd.MAX_RESTARTS_PER_HOUR


def test_emergency_bucket_exhausts_at_its_own_limit(tmp_path, monkeypatch):
    guard = _reset_guard(tmp_path, monkeypatch)
    now = time.time()
    # 真崩溃桶已用满 MAX_RESTARTS_EMERGENCY 次
    guard.write_text(json.dumps({
        "restart_times_emergency": [now] * wd.MAX_RESTARTS_EMERGENCY
    }), encoding="utf-8")
    assert wd.start_monitor(emergency=True) is False
