# -*- coding: utf-8 -*-
"""OI 族独立字段消费接入回归（2026-09-13 用户批准）

背景：消费矩阵审计发现 v13 独立字段（Basic Bus 的 oi_present/cvdBg、
CVD Anchor、OI Dispersion、Exchange Dominance、OI Breadth）导出后无消费，
其中 dual["oi_present"] 缺失导致 decision_loop 的 oi_agreement_low 从未生效。
本次接入三处：auto_card 组装、render_v96 ③表、decision_loop 降权。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from auto_card import _dual_indicator_verdict
from render_v96 import _multi_source_line

SAMPLE_BUS = 2200320299100072  # 实测缓存值：22003 合同 + state2 + oi 10007 + cvdBg2


def _main(**overrides):
    """与 test_decision_loop_vnext._main 同构（全字段，避免 zone_quality 误伤）。"""
    data = {
        "grade": "A多", "direction": "long", "model_id": "fvg_pullback",
        "entry": 100.0, "stop": 98.0, "target": 105.0, "rr": 2.5,
        "mcp_fvg_quality_score": 82.0, "mcp_ob_quality_score": 70.0,
        "data_grade": "A", "snapshot_age_sec": 10.0,
        "location_valid": True, "trigger_confirmed": True, "bar_closed": True,
    }
    data.update(overrides)
    return data


def _trend():
    from decision_regime import classify_decision_regime
    return classify_decision_regime(
        adx=30, atr_ratio=1.0, ema_spread_atr=0.7, vwap_crosses_20=1,
        va_stay_ratio_20=0.2, displacement_atr=0.8, rvol=1.1,
    )

_ED = {
    "_tv_main": {
        "sub_basic_packed_bus": SAMPLE_BUS,
        "sub_cvd_anchor_value": 3.237,
        "sub_oi_dispersion_ratio": 0.39,
        "sub_exchange_dominance_pct": 47,
        "sub_oi_breadth": 4,
        "sub_haldro_state_pack": 2,
    },
    "_tv_sub": {},
}


def test_dual_indicator_verdict_populates_oi_fields():
    dual = _dual_indicator_verdict("BTCUSDT", {"status": "C等待"}, dict(_ED))
    assert dual.get("oi_present") is True
    assert dual.get("cvd_anchor_text") == "锚3.24·滚动卖"
    assert dual.get("oi_dispersion_ratio") == 0.39
    assert dual.get("exchange_dominance_pct") == 47
    assert dual.get("oi_breadth") == 4
    quality = dual.get("haldro_quality") or ""
    assert "离散0.39" in quality
    assert "主导47%" in quality
    assert "广度+4" in quality


def test_dominance_over_70_flagged():
    ed = {"_tv_main": {"sub_exchange_dominance_pct": 72}, "_tv_sub": {}}
    dual = _dual_indicator_verdict("BTCUSDT", {"status": "C等待"}, ed)
    assert "主导72%⚠" in (dual.get("haldro_quality") or "")


def test_no_oi_fields_absent_silently():
    dual = _dual_indicator_verdict("BTCUSDT", {"status": "C等待"}, {"_tv_main": {}, "_tv_sub": {}})
    assert "oi_present" not in dual
    assert "cvd_anchor_text" not in dual
    assert "离散" not in (dual.get("haldro_quality") or "")


def test_multi_source_line_renders_anchor():
    line = _multi_source_line("中性", "", "", "", "", "", "", {"cvd_anchor_text": "锚3.24·滚动卖"})
    assert "锚3.24·滚动卖" in line
    line2 = _multi_source_line("中性", "", "", "", "", "", "", {})
    assert "锚" not in line2


def test_structure_table_renders_full_capacity():
    """v9.12：② 关键位改为「并簇 → 角色制 ≤4 行」，容量契约随之更新。

    旧契约（prepare 7 / render [:7] / [:6] 会吞第 7 位）在角色制下不再适用：
    现在 prepare 取 14 个候选 → 并簇成带 → 最多 4 行角色 → 其余下沉「远端」注脚，
    远端位不会丢，只是不再逐行占卡面。
    """
    src = (ROOT / "scripts" / "render_v96.py").read_text(encoding="utf-8")
    assert "_prepare_levels(levels or [], klines, price, limit=14)" in src
    assert "levels_prepared[:7]" not in src
    assert "levels_prepared[:6]" not in src


def test_level_kind_do_price_named():
    """DO Price 具名（消费矩阵建议 6）。"""
    from render_v96 import _level_kind
    label, _icon, use = _level_kind("D 日开", "resistance", 77242.8, 77260.0)
    assert label == "D·DO"
    assert "日开" in use


def test_do_price_wired_into_card():
    """DO Price 走环境行（消费矩阵建议 6）：auto_card 传参 + render 接线。"""
    ac = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert "_do_price_v = float" in ac
    assert "do_price=_do_price_v" in ac
    rv = (ROOT / "scripts" / "render_v96.py").read_text(encoding="utf-8")
    assert "do_price: float = 0.0" in rv
    assert "_ema_disclosure_line(vwap_ema, do_price=do_price, price=price)" in rv


def test_ema_line_with_do_price():
    from render_v96 import _ema_disclosure_line
    line = _ema_disclosure_line(
        {"vwap": {"vwap": 76750.0, "price_vs_vwap": "上", "in_band": "1σ内"},
         "ema": {"9": 76760.0, "55": 76700.0}, "ema_cloud": {"trend_strength": "多头排列"}},
        do_price=77242.8, price=76750.0)
    assert line.startswith("VWAP/EMA/DO：")
    assert "DO `77,243`" in line
    assert "+0.64%" in line


def test_do_only_line():
    from render_v96 import _ema_disclosure_line
    line = _ema_disclosure_line(None, do_price=77242.8, price=76750.0)
    assert line.startswith("DO：")
    assert "DO `77,243`" in line


def test_decision_loop_dispersion_high_triggers_wait():
    from decision_loop import resolve_final_verdict
    out = resolve_final_verdict(
        "BTCUSDT", _main(),
        {"asset_is_crypto": True, "valid_code": 2, "conflict": False,
         "aligned": True, "risk_code": 0,
         "oi_present": True, "oi_dispersion_ratio": 3.1},
        regime=_trend(),
    )
    assert "oi_dispersion_high" in out.blockers
    assert out.state in ("WAIT", "NO-GO")


def test_decision_loop_dispersion_normal_go_a():
    from decision_loop import resolve_final_verdict
    out = resolve_final_verdict(
        "BTCUSDT", _main(),
        {"asset_is_crypto": True, "valid_code": 2, "conflict": False,
         "aligned": True, "risk_code": 0,
         "oi_present": True, "oi_dispersion_ratio": 0.4},
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}},
    )
    assert out.state == "GO-A"
    assert "oi_dispersion_high" not in out.blockers
