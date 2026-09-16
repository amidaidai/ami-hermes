#!/usr/bin/env python3
"""测试不得写生产 data/ —— 隔离守卫与既有污染的回归。

背景（2026-09-16 实锤）：全量测试跑完后，真实 `data/xau_tv_sync_status.json`
被写成 `status=ok / last_success_at=now`，而 XAU 现场产物其实停更了 19.6h。
`audit_preflight` 与 `data_freshness_watchdog` 都按这个文件判「同步器是否在跑」，
于是「假成功」把停摆糊成绿色。同类的还有 `data/watchdog.log` 被测试追加
「重启速率限制」行，破坏事后取证。

守卫规则：测试环境（PYTEST_CURRENT_TEST 生效）只拦目标落在本仓库 `data/` 下的写入；
tmp_path 等隔离路径照常可写，正常用例不受影响。
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_preflight as audit  # noqa: E402
import watchdog as wd  # noqa: E402
import xau_tv_sync  # noqa: E402


def test_xau_status_write_is_blocked_for_live_data_path(monkeypatch, tmp_path):
    live = xau_tv_sync.STATUS_OUT
    assert live == ROOT / "data" / "xau_tv_sync_status.json"
    # 测试环境：生产路径被拦，隔离路径放行
    assert xau_tv_sync._blocked_live_write(live) is True
    assert xau_tv_sync._blocked_live_write(tmp_path / "xau_tv_sync_status.json") is False
    # 非测试环境：一律放行（生产运行不能被守卫挡住）
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert xau_tv_sync._blocked_live_write(live) is False


def test_write_sync_status_refuses_live_path_but_keeps_return_contract():
    """被拦时不落盘，但返回值仍是该写的 payload（调用方契约不变）。"""
    live = xau_tv_sync.STATUS_OUT
    before = live.stat().st_mtime_ns
    payload = xau_tv_sync._write_sync_status(True)
    assert payload["status"] == "ok" and payload["consecutive_failures"] == 0
    assert live.stat().st_mtime_ns == before


def test_watchdog_log_is_blocked_for_live_path(monkeypatch, tmp_path):
    assert wd._blocked_live_log(wd.LOG_FILE) is True
    assert wd._blocked_live_log(tmp_path / "watchdog.log") is False
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert wd._blocked_live_log(wd.LOG_FILE) is False


def test_isolated_tests_keep_isolating_their_live_paths():
    """三个曾漏隔离的用例必须继续把生产路径 monkeypatch 到 tmp。

    这是「忘了隔离」这一类回归的护栏：漏哪一条，这条断言就红。
    """
    degrad = (ROOT / "tests" / "test_xau_tv_sync_degradation.py").read_text(encoding="utf-8")
    assert 'monkeypatch.setattr(xau_tv_sync, "STATUS_OUT"' in degrad
    assert 'monkeypatch.setattr(xau_tv_sync, "AUDIT_MARKER_FILE"' in degrad
    for name in ("test_watchdog_ratelimit.py", "test_p0_p1_audit_regressions.py"):
        src = (ROOT / "tests" / name).read_text(encoding="utf-8")
        assert 'monkeypatch.setattr(wd, "LOG_FILE"' in src, name


def test_preflight_does_not_report_ok_for_stale_sync_record():
    """status=ok 但记录很旧 → 必须说 STALE，不能打印 OK（假成功防线）。"""
    stale = {
        "schema": "xau_tv_sync_status_v1", "status": "ok", "consecutive_failures": 0,
        "last_error": None, "kept": "",
        "last_success_at": "2026-09-15T14:43:19+08:00",
        "checked_at": "2026-09-15T14:43:19+08:00",
    }
    ok_flag, line = audit.xau_sync_status_line(stale)
    assert ok_flag is True          # 未更新 ≠ 结构性降级，不判 red
    assert "STALE" in line and "OK" not in line

    fresh_now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fresh = {**stale, "checked_at": fresh_now, "last_success_at": fresh_now}
    ok_flag, line = audit.xau_sync_status_line(fresh)
    assert ok_flag is True and line.startswith("XAU同步: OK checked=")

    degraded = {**stale, "status": "degraded", "consecutive_failures": 2}
    ok_flag, line = audit.xau_sync_status_line(degraded)
    assert ok_flag is False and "DEGRADED" in line

    # 未知/缺失状态（旧行为）：措辞不变、不判 red
    ok_flag, line = audit.xau_sync_status_line({"jobs": []})
    assert ok_flag is True and "WARN(单次失败)" in line
