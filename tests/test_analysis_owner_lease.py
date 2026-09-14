# -*- coding: utf-8 -*-
"""分析管线自持租约 + 自有采集放行（2026-09-14 修「租约自锁」）。

背景：租约把「分析进行中」变成后台可见的事实（防抢图，20260911），但同一个租约
会把**分析自己的**五周期采集判 `deferred` —— `keylevels_collect_diagnostic.json`
实测 `status=deferred`，auto_card 刷不进快照，超 30 分钟契约后完整档五层证据降级
为 `TV五周期 unavailable`。

修法两条：
1. auto_card 开跑时自持租约（已有别人的租约则不覆盖、不接管），收尾释放；
2. 只有「分析自己的」采集子进程带 `TANGXI_ANALYSIS_OWNER=1` 放行；外部后台
   （btc_tv_refresh / xau_tv_sync / cron）不带该变量，照旧让路。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
scrIPTS = ROOT / "scripts"
sys.path.insert(0, str(scrIPTS))

import auto_card  # noqa: E402
import keylevels_collect as klc  # noqa: E402


def _silence_diag(monkeypatch):
    seen: list = []
    monkeypatch.setattr(klc, "_diagnostic", lambda *a, **k: seen.append((a, k)))
    return seen


# ── 采集侧：让路 vs 放行 ────────────────────────────────────────────────

def test_collector_defers_for_outsiders_while_lease_active(monkeypatch):
    """外部后台（不带所有者标记）遇租约必须让路。"""
    import tv_data_bridge as bridge
    _silence_diag(monkeypatch)
    monkeypatch.delenv(klc.ANALYSIS_OWNER_ENV, raising=False)
    monkeypatch.setattr(bridge, "analysis_lease_status",
                        lambda: {"active": True, "remaining_seconds": 300, "reason": "分析进行中"})
    try:
        klc._require_no_analysis_lease()
    except bridge.AnalysisLeaseActive:
        return
    raise AssertionError("带租约且非分析所有者时必须让路")


def test_collector_proceeds_for_analysis_owner(monkeypatch):
    """分析管线自己的采集即使租约在生效也放行（并留下诊断痕迹）。"""
    import tv_data_bridge as bridge
    seen = _silence_diag(monkeypatch)
    monkeypatch.setenv(klc.ANALYSIS_OWNER_ENV, "1")
    monkeypatch.setattr(bridge, "analysis_lease_status",
                        lambda: {"active": True, "remaining_seconds": 300})
    klc._require_no_analysis_lease()  # 不抛即通过
    assert any("analysis_owner" in str(a[0]) for a, _ in seen), seen


def test_owner_flag_must_be_exactly_one(monkeypatch):
    """只有 =1 才算所有者；'0'/'yes'/空值都不放行（防误配静默越权）。"""
    import tv_data_bridge as bridge
    _silence_diag(monkeypatch)
    monkeypatch.setattr(bridge, "analysis_lease_status",
                        lambda: {"active": True, "remaining_seconds": 60, "reason": "x"})
    for value in ("0", "yes", "", "true"):
        monkeypatch.setenv(klc.ANALYSIS_OWNER_ENV, value)
        try:
            klc._require_no_analysis_lease()
        except bridge.AnalysisLeaseActive:
            continue
        raise AssertionError(f"{value!r} 不应被当成本轮分析所有者")


# ── 管线侧：租约的自持与不接管 ──────────────────────────────────────────

def test_auto_card_declares_lease_when_idle(monkeypatch):
    import tv_data_bridge as bridge
    monkeypatch.setattr(bridge, "analysis_lease_status", lambda: {"active": False})
    calls: list = []
    monkeypatch.setattr(bridge, "begin_analysis_lease",
                        lambda minutes, **kw: calls.append((minutes, kw)))
    assert auto_card._begin_analysis_lease_if_idle("BTCUSDT") is True
    assert calls and calls[0][0] == auto_card.ANALYSIS_LEASE_MINUTES
    assert calls[0][1].get("symbol") == "BTCUSDT"
    assert "auto_card" in str(calls[0][1].get("note"))


def test_auto_card_does_not_clobber_active_lease(monkeypatch):
    """交互式租约在生效时：沿用、不覆盖、不接管（谁声明谁 end）。"""
    import tv_data_bridge as bridge
    monkeypatch.setattr(bridge, "analysis_lease_status",
                        lambda: {"active": True, "remaining_seconds": 120})
    called: list = []
    monkeypatch.setattr(bridge, "begin_analysis_lease", lambda *a, **k: called.append(1))
    assert auto_card._begin_analysis_lease_if_idle("BTCUSDT") is False
    assert not called


def test_end_lease_helper_is_quiet_and_calls_bridge(monkeypatch):
    import tv_data_bridge as bridge
    calls: list = []
    monkeypatch.setattr(bridge, "end_analysis_lease", lambda: calls.append(1))
    auto_card._end_analysis_lease_quiet()
    assert calls == [1]


# ── 证据采集子进程必须带所有者标记 ──────────────────────────────────────

def test_five_tf_refresh_passes_owner_env(monkeypatch):
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured.update(kwargs)
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="stub failure")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv(auto_card.ANALYSIS_OWNER_ENV, "0")  # 环境里显式不是 1 → 必须被覆盖
    auto_card._refresh_btc_tv_five_tf_snapshot("BTCUSDT")
    assert captured["env"][auto_card.ANALYSIS_OWNER_ENV] == "1"
    assert captured["timeout"] == 420
    assert "keylevels_collect.py" in " ".join(str(x) for x in captured["cmd"])


def test_background_jobs_do_not_claim_analysis_owner():
    """后台续航脚本不得自称分析所有者——否则防抢图会让路失效。"""
    for name in ("btc_tv_refresh.py", "xau_tv_sync.py"):
        src = (scrIPTS / name).read_text(encoding="utf-8")
        assert "TANGXI_ANALYSIS_OWNER" not in src, name
