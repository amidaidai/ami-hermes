#!/usr/bin/env python3
"""Regression test for the v4.3 行动格 v2 decode bridge.

Context: the production SVP indicator removed its Data Window export to free
TradingView's 64-plot quota. As a result the old decode path (which looked for
Data Window study titles like 'CVD Value' and table rows '等级'/'处理') silently
returned null on every run. fetch_tv_data.cjs now reads the action-panel cells
from the CDP `dwgtablecells` collection and writes tv_grade/tv_conclusion/
tv_entry/tv_stop/tv_target into the JSON; auto_card.py reassembles those into the
legacy 等级|处理 rows that _parse_tv_dmi_table / _apply_tv_dmi_override consume.

These tests lock the Python half of that chain so the break cannot regress.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUTO_CARD = ROOT / "hermes" / "scripts" / "auto_card.py"


@pytest.fixture(scope="module")
def ac():
    spec = importlib.util.spec_from_file_location("auto_card_under_test", AUTO_CARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _synth_rows(tv_raw: dict) -> list[str]:
    """Mirror the row synthesis in auto_card.py's TV-merge block (v4.3)."""
    return [
        f"等级 | {tv_raw['tv_grade']}",
        f"处理 | {tv_raw.get('tv_treatment') or tv_raw.get('tv_conclusion') or '?'}",
        f"背景 | {tv_raw.get('tv_direction') or '?'}",
        f"位置 | {tv_raw.get('tv_entry') or '?'}",
        f"执行 | 进:{tv_raw.get('tv_entry')} 损:{tv_raw.get('tv_stop')} 标:{tv_raw.get('tv_target')}",
    ]


@pytest.mark.parametrize(
    "grade,exp_status,exp_dir,exp_plan",
    [
        ("A多", "A做多", "long", "A"),
        ("A空", "A做空", "short", "A"),
        ("B多", "B等待", "long", "B"),
        ("B空", "B等待", "short", "B"),
        ("C反多", "C反转", "long", "C"),
        ("C反空", "C反转", "short", "C"),
        ("X", "X禁做", "wait", "无"),
        ("C等待", "C等待", "wait", "无"),
    ],
)
def test_grade_override_maps_to_status(ac, grade, exp_status, exp_dir, exp_plan):
    tv_raw = {
        "tv_grade": grade, "tv_treatment": "回踩", "tv_conclusion": f"{grade} 回踩",
        "tv_direction": "偏多", "tv_entry": "62,480", "tv_stop": "61,950", "tv_target": "63,820",
    }
    rows = ac._parse_tv_dmi_table([{"name": "SVP+ICT+VWAP+EMA+CVD", "tables": [{"rows": _synth_rows(tv_raw)}]}])
    assert rows["等级"] == grade
    meta: dict = {}
    changes = ac._apply_tv_dmi_override(meta, {}, "BTCUSDT", rows, {})
    assert changes["tv_active"] is True
    assert changes["tv_grade"] == grade
    assert meta["status"] == exp_status
    assert meta["direction"] == exp_dir
    assert meta["priority_plan"] == exp_plan


def test_parse_handles_real_panel_values(ac):
    """Entry/stop/target with commas, ATR suffix and R:R survive the round trip."""
    tv_raw = {
        "tv_grade": "A多", "tv_treatment": "回踩", "tv_conclusion": "A多 回踩",
        "tv_direction": "偏多 DMI✓ 折价 ⚡纽 扫1/2",
        "tv_entry": "扫低收回 62,480", "tv_stop": "61,950 (1.8ATR)",
        "tv_target": "POC 63,820 R:R 1:2.5",
    }
    rows = ac._parse_tv_dmi_table([{"name": "SVP+ICT+VWAP+EMA+CVD", "tables": [{"rows": _synth_rows(tv_raw)}]}])
    assert rows["处理"] == "回踩"
    assert rows["位置"] == "扫低收回 62,480"
    assert "标:POC 63,820 R:R 1:2.5" in rows["执行"]


def test_empty_tables_returns_inactive(ac):
    assert ac._parse_tv_dmi_table(None) == {}
    assert ac._apply_tv_dmi_override({}, {}, "BTCUSDT", {}, {}) == {"tv_active": False}
