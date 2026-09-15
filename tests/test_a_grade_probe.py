# -*- coding: utf-8 -*-
"""A 级可达性探针（scripts/a_grade_probe.py）不变量。

它存在的意义是**分辨**两件被混为一谈的事：
  · 「行情真没 A 级机会」——SVP 自己的等级/方向判断（Grade/Side/EntryValid）；
  · 「A 级被工程问题物理封死」——字段缺失、副指标 Bus 无效、合同损坏。
如果探针把前者误报成后者，用户会去查不存在的接线故障；反之则会漏掉真故障。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import a_grade_probe as probe  # noqa: E402


def _cache(**ind_over):
    ind = {
        "mcp_grade_code": 3, "mcp_entry_valid_code": 3, "mcp_side_code": 1,
        "mcp_evidence_direction": 1, "mcp_location_valid": True,
        "mcp_trigger_confirmed": True, "mcp_bar_closed": True,
        "mcp_evidence_version": 20260905,
        "mcp_trigger_pack": 1099919, "mcp_fvg_quality_score": 80.0,
        "mcp_ob_quality_score": 70.0, "mcp_notrade_reason_code": 0,
        "mcp_quality_code": 0, "mcp_regime_pack": 56999, "mcp_structpack": 120121,
        "mcp_contract_pack": 171011, "haldro_valid_code": 2, "haldro_state_pack": 1,
        "oi_agreement": 100, "oi_dispersion_ratio": 1.0,
        "cvd_quality_code": 8, "mcp_entry_price": 100.0,
        "mcp_stop_price": 98.0, "mcp_target_price": 105.0,
    }
    ind.update(ind_over)
    return {
        "indicators": ind, "timeframe": "15", "fresh": True, "stale": False,
        "identity_valid": True, "symbol": "BINANCE:BTCUSDT.P",
    }


def _run(tmp_path, canvas, capsys):
    (tmp_path / "tv_live_BTCUSDT.json").write_text(json.dumps(canvas), encoding="utf-8")
    old_data, old_argv = probe.DATA, sys.argv
    probe.DATA = tmp_path
    sys.argv = ["a_grade_probe.py", "BTCUSDT"]
    try:
        rc = probe.main()
    finally:
        probe.DATA, sys.argv = old_data, old_argv
    return rc, capsys.readouterr().out


def test_full_green_frame_reports_no_failure(tmp_path, capsys):
    _, out = _run(tmp_path, _cache(), capsys)
    assert "本帧通过 25/25 项" in out, out
    assert "不是接线故障" in out


def test_market_downgrade_is_not_reported_as_wiring_bug(tmp_path, capsys):
    """SVP 自己说 X 禁做 —— 这是行情判断，不许报成工程故障。"""
    _, out = _run(tmp_path, _cache(mcp_grade_code=-1, mcp_entry_valid_code=-3,
                                  mcp_side_code=9), capsys)
    assert "X禁做" in out
    assert "疑似工程问题" not in out, out
    assert "不是接线故障" in out


def test_wiring_failure_is_flagged(tmp_path, capsys):
    """副指标 Bus 无效 + 合同损坏 —— 这才该报工程问题。"""
    _, out = _run(tmp_path, _cache(haldro_valid_code=0, mcp_contract_pack=0), capsys)
    assert "疑似工程问题" in out, out
    assert "HALDRO Valid Code" in out


def test_missing_field_is_treated_as_wiring(tmp_path, capsys):
    canvas = _cache()
    del canvas["indicators"]["haldro_valid_code"]
    _, out = _run(tmp_path, canvas, capsys)
    assert "疑似工程问题" in out, out


def test_rr_floor_is_reported_when_three_prices_present(tmp_path, capsys):
    _, out = _run(tmp_path, _cache(mcp_target_price=101.0), capsys)
    # 1.5 < rr < 2.0 → 不是 A 级
    assert "1.50" in out or "1.5" in out
