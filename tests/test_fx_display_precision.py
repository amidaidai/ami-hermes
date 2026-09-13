# -*- coding: utf-8 -*-
"""FX 价格显示精度回归（2026-09-13）

背景：EURUSD 卡曾出现两类坏值——
  ① 周期体温行「TV现场 POC 1 ／ VAH 1」（:.0f 把 1.1638 格式化成 1）
  ② 结构位表「D·VAH `1.16`」（:.2f 只留 2 位小数）
修复：_num / _fmt_num 对 |v|∈[0.01,10) 保留 4 位小数；TV 注入描述改用 _num。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_v96 import _num, _price
from render_tv_card import _fmt_num


# ---------- render_v96._num ----------

def test_num_fx_precision_four_decimals():
    assert _num(1.16382) == "1.1638"
    assert _num(1.16) == "1.1600"
    assert _num(1.08234) == "1.0823"
    assert _num(0.9751) == "0.9751"


def test_num_mid_range_keeps_two_decimals():
    assert _num(108.523) == "108.52"
    assert _num(150.25) == "150.25"


def test_num_large_values_unchanged():
    assert _num(77252) == "77,252"
    # ≥1000 走 :,.0f（四舍五入到整数）—— 4348.6 → 4,349 为既有无损行为
    assert _num(4348.6) == "4,349"
    assert _num(4435.0) == "4,435"


def test_num_tiny_values_strip_trailing_zeros():
    assert _num(0.0000123) == "0.000012"
    assert _num(0.0005) == "0.0005"


def test_price_wrapper_uses_same_rules():
    assert _price(1.1638) == "`1.1638`"


# ---------- render_tv_card._fmt_num ----------

def test_tv_card_fmt_same_rules():
    assert _fmt_num("1.1638") == "1.1638"
    assert _fmt_num("`1.16`") == "1.1600"
    assert _fmt_num(77252) == "77,252"
    assert _fmt_num(0.0000123) == "0.000012"
    assert _fmt_num(None) == "—"


# ---------- auto_card._apply_tv_live_structure ----------

def test_apply_tv_live_structure_fx_description():
    from auto_card import _apply_tv_live_structure

    engine_data: dict = {}
    klines: dict = {"15m": {"description": "待刷新"}}
    ok = _apply_tv_live_structure(
        engine_data, klines, poc=1.1638, vah=1.166, val=1.160, direction="多"
    )
    assert ok is True
    desc = klines["D"]["description"]
    assert "1.1638" in desc
    assert "POC 1 |" not in desc  # 旧 bug：1.1638 被 :.0f 显示成 1
    assert "1.1638" in klines["15m"]["description"]


def test_apply_tv_live_structure_btc_unchanged():
    from auto_card import _apply_tv_live_structure

    engine_data: dict = {}
    klines: dict = {}
    ok = _apply_tv_live_structure(
        engine_data, klines, poc=77252, vah=77500, val=76800, direction="空"
    )
    assert ok is True
    desc = klines["D"]["description"]
    assert "77,252" in desc
    assert "77,500" in desc
