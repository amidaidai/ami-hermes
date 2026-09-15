"""关键位守护看门狗的 DEGRADED 语义回归。

背景：该脚本原来在「keylevels_config 无有效批准关键位」时 `sys.exit(2)`。
实测 2026-09-01–09-12 该条件持续 12 天（每 2 分钟一跑）→ **3,745 条 cron incident**，
且错误文本自带时间戳导致签名每次都不同、Hermes 无法去重 → incident 表被一个条件刷爆、
彻底失去信号价值。修法：降级是状态不是故障 → stdout + health 文件可见，exit 0。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import btc_keylevel_guard_watchdog as klg  # noqa: E402


def test_degraded_no_levels_exits_zero_and_flags_health(monkeypatch, tmp_path):
    written = {}

    monkeypatch.setattr(klg, "_run_structure_review", lambda: {"ok": True, "stamped": False,
                                                              "stamp_reason": "test"})
    monkeypatch.setattr(klg, "auto_renew_existing_approved_levels", lambda *a, **k: {})
    monkeypatch.setattr(klg, "check_config_health", lambda: {
        "status": "degraded", "active_approved_levels": 0, "configured_levels": 0,
        "enabled_levels": 0})
    monkeypatch.setattr(klg, "write_health", lambda h: written.update(h))
    monkeypatch.setattr(klg, "log", lambda m: None)

    with pytest.raises(SystemExit) as ei:
        klg.main()
    assert ei.value.code == 0, "降级不得用非零退出码（否则每 2 分钟刷一条 incident）"
    assert written.get("degraded") is True
    assert written.get("degraded_reason") == "no_active_approved_levels"


def test_healthy_path_does_not_set_degraded(monkeypatch):
    """有批准位时必须继续往下走（别把正常路径也短路了）。"""
    monkeypatch.setattr(klg, "_run_structure_review", lambda: {"ok": True, "stamped": False,
                                                              "stamp_reason": "test"})
    monkeypatch.setattr(klg, "auto_renew_existing_approved_levels", lambda *a, **k: {})
    monkeypatch.setattr(klg, "check_config_health", lambda: {
        "status": "ok", "active_approved_levels": 8, "configured_levels": 8, "enabled_levels": 8})
    seen = {}
    monkeypatch.setattr(klg, "write_health", lambda h: seen.update(h))
    monkeypatch.setattr(klg, "log", lambda m: None)
    monkeypatch.setattr(klg, "is_guard_alive", lambda: True)
    monkeypatch.setattr(klg, "HEARTBEAT", Path("/nonexistent/hb.json"))
    try:
        klg.main()
    except SystemExit as e:      # 健康路径可能因单实例检查而退出，但不应是降级分支
        assert e.code == 0
    assert not seen.get("degraded"), "健康时不得写 degraded 标记"


def test_idle_state_never_degraded(monkeypatch):
    """用户主动把批准位全部静默（idle）是预期状态，同样不能记故障。"""
    monkeypatch.setattr(klg, "_run_structure_review", lambda: {"ok": True, "stamped": False,
                                                              "stamp_reason": "test"})
    monkeypatch.setattr(klg, "auto_renew_existing_approved_levels", lambda *a, **k: {})
    monkeypatch.setattr(klg, "check_config_health", lambda: {
        "status": "idle", "active_approved_levels": 0, "configured_levels": 3, "enabled_levels": 0})
    seen = {}
    monkeypatch.setattr(klg, "write_health", lambda h: seen.update(h))
    monkeypatch.setattr(klg, "log", lambda m: None)
    monkeypatch.setattr(klg, "is_guard_alive", lambda: True)
    monkeypatch.setattr(klg, "HEARTBEAT", Path("/nonexistent/hb.json"))
    try:
        klg.main()
    except SystemExit as e:
        assert e.code == 0
    assert not seen.get("degraded")
