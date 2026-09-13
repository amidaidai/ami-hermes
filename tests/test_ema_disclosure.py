# -*- coding: utf-8 -*-
"""VWAP/EMA 环境行接入回归（2026-09-13）

缺口：EMA 引擎（vwap_ema_cvd_engine）算了 9/21/34/55 + EMA云，
但只在终端打印、渲染层 0 引用——用户指标盘点发现的「算了没上卡」。
修复：render_v96._ema_disclosure_line 接入【做法】表后（仅 available 时显示）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_v96 import _ema_disclosure_line


def test_ema_line_full_data_xau():
    line = _ema_disclosure_line({
        "available": True,
        "vwap": {"vwap": 4347.4, "price_vs_vwap": "上", "in_band": "1σ内"},
        "ema": {"9": 4349.2, "55": 4342.1},
        "ema_cloud": {"trend_strength": "强趋势·多头排列"},
    })
    assert line.startswith("VWAP/EMA：")
    assert "VWAP `4,347`" in line
    assert "EMA9/55 `4,349`/`4,342`" in line
    assert "强趋势·多头排列" in line


def test_ema_line_fx_four_decimals():
    line = _ema_disclosure_line({
        "available": True,
        "vwap": {"vwap": 1.1638, "price_vs_vwap": "上", "in_band": "1σ内"},
        "ema": {"9": 1.164, "55": 1.162},
        "ema_cloud": {"trend_strength": "多头排列"},
    })
    assert "1.1638" in line
    assert "1.1640" in line


def test_ema_line_empty_when_unavailable():
    assert _ema_disclosure_line(None) == ""
    assert _ema_disclosure_line({}) == ""
    assert _ema_disclosure_line({"available": False}) == ""


def test_ema_line_partial_data_still_useful():
    line = _ema_disclosure_line({
        "available": True,
        "vwap": {"vwap": 77230.6, "price_vs_vwap": "下", "in_band": "2σ外"},
        "ema": {},
        "ema_cloud": {},
    })
    assert line.startswith("VWAP/EMA：")
    assert "77,230" in line or "77,231" in line


def test_ema_line_fallback_schema():
    """TV MCP fallback schema：vwap.value / price_above / 无 ema_cloud（2026-09-13 实测）。"""
    line = _ema_disclosure_line({
        "vwap": {"value": 4351.9, "price_above": False},
        "ema": {"9": 4348.4, "55": 4352.8},
        "source": "tv_mcp",
    })
    assert line.startswith("VWAP/EMA：")
    assert "4,352" in line
    assert "价在下" in line
    assert "EMA9/55 `4,348`/`4,353`" in line


def test_ema_line_wired_into_card_body():
    """防回退：_ema_disclosure_line 必须被 render_v96_card 调用。"""
    src = (ROOT / "scripts" / "render_v96.py").read_text(encoding="utf-8")
    assert "_ve_line = _ema_disclosure_line(vwap_ema, do_price=do_price, price=price)" in src


def test_vwap_ema_backfill_and_reuse_wired():
    """防回退：Step1 后处理回写 engine_data + render_card_locked 复用（数据流两处）。

    历史缺陷：Step1 引擎成功（打印快线/慢线）但结果未回写，render 本地重算
    因 XAU 无本地K线而失败 → 卡面 VWAP/EMA 行空白（2026-09-13 实测）。"""
    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert 'engine_data["_vwap_ema"] = _vwap_ema_result' in src
    assert '_ve_existing = engine_data.get("_vwap_ema")' in src
