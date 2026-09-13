#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-12 审计修复回归测试。

覆盖两处实测缺陷：
P0-1 `go_nogo_gate.check_gate` R:R 门 fail-open —— rr_a 缺失时用反侧 rr_b 冒充
     主线并点亮绿灯（实测 rr_a=0.547 / rr_b=3.404 → 卡面「🟢 主线R:R 1:3.3」）。
P0-2 `render_v96` 结构位跨周期混标 —— "D VAL"(77,388.5) 与 "15m VAH"(77,334)
     被压成同层，卡面出现「VAL 上 / VAH 下」的价值区倒挂伪结构。

运行：python scripts/test_audit_fixes_20260912.py   （pytest 亦可收集）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from go_nogo_gate import check_gate                      # noqa: E402
from render_v96 import (                                  # noqa: E402
    _prepare_levels,
    _structure_table,
    _level_kind,
    render_v96_card,
)

TF_PREFIX = re.compile(r"^(D|W|M|4h|1h|15m|5m)·(VAH|VAL|POC|VWAP|nPOC|FVG|阻|支|位)$")

# 23:39 实测样例（data/auto_card_BTCUSDT*.md + tv_live_BTCUSDT.json + candidates）
REAL_LEVELS = [
    {"level": 77388.5, "name": "D VAL", "side": "support"},
    {"level": 79660.1, "name": "D VAH", "side": "resistance"},
    {"level": 77209.0, "name": "15m VAL", "side": "support"},
    {"level": 77334.0, "name": "15m VAH", "side": "resistance"},
    {"level": 77261.5, "name": "15m POC", "side": "level"},
]
REAL_PRICE = 77382.4


# ── P0-1：R:R 门 fail-closed ────────────────────────────────────────────────

def _engine(final_state="GO-A", executable=True):
    return {
        "_snapshot_age_h": 0.1,
        "_banned_live": False,
        "_reviews_count": 20,
        "_wfo_efficiency": 0.72,
        "_final_verdict": {"state": final_state, "executable": executable,
                           "reason": "haldro_state_conflict/advanced_confluence"},
    }


def test_rr_gate_never_borrows_opposite_side():
    """rr_a=0/缺失时，R:R 门不得把反侧 rr_b 当主线点亮，且必须显式标注不可引用。"""
    res = check_gate("BTCUSDT", _engine("NO-GO", False),
                     {"data_grade": "A", "rr_a": 0, "rr_b": 3.404, "protections_status": "通过"})
    gate = res["gates"]["rr_ratio"]
    assert gate["status"] == "red", gate
    assert "主线R:R" not in gate["reason"], gate
    assert "不得用作放行依据" in gate["reason"], gate
    assert "rr_ratio" in res["red_gates"], res["red_gates"]
    assert res["go"] is False


def test_rr_gate_real_primary_below_two_is_red():
    """实测主侧 rr_a=0.547 必须红灯（旧实现被 rr_b=3.404 盖成绿灯）。"""
    res = check_gate("BTCUSDT", _engine("NO-GO", False),
                     {"data_grade": "A", "rr_a": 0.547, "rr_b": 3.404, "protections_status": "通过"})
    gate = res["gates"]["rr_ratio"]
    assert gate["status"] == "red", gate
    assert "1:0.5" in gate["reason"], gate


def test_rr_gate_legit_go_a_still_green():
    """回归：真实 GO-A 计划 rr_a=2.5 仍应绿灯（不得误伤）。"""
    res = check_gate("BTCUSDT", _engine("GO-A", True),
                     {"data_grade": "A", "rr_a": 2.5, "rr_b": 1.8, "protections_status": "通过"})
    gate = res["gates"]["rr_ratio"]
    assert gate["status"] == "green", gate
    assert "1:2.5" in gate["reason"], gate


# ── P0-2：结构位周期前缀 + 同周期价值区一致性 ───────────────────────────────

def test_value_area_labels_keep_timeframe_prefix():
    prepared = _prepare_levels(list(REAL_LEVELS), {}, REAL_PRICE)
    va_kinds = [p["kind"] for p in prepared if p["kind"].endswith(("VAL", "VAH"))]
    assert va_kinds, prepared
    for kind in va_kinds:
        assert TF_PREFIX.match(kind), f"{kind} 缺周期前缀 → 跨周期混标复发"


def test_structure_block_has_no_bare_val_vah():
    prepared = _prepare_levels(list(REAL_LEVELS), {}, REAL_PRICE)
    out = _structure_table(prepared, REAL_PRICE)
    for line in out.splitlines():
        if "VAL" not in line and "VAH" not in line:
            continue
        if not line.startswith("|"):
            continue
        label = re.sub(r"^[^\w\u4e00-\u9fff]+", "", line.split("|")[1].strip())
        label = re.sub(r"\s*[上下]\s*$", "", label)
        assert TF_PREFIX.match(label), f"裸价值区标签（跨周期混标复发）: {line}"
    # 旧缺陷字面量不得再出现（裸「VAL 上」/「VAH 下」）
    assert "| 🔴VAL 上" not in out and "| 🟢VAL 下" not in out, out
    assert "D·VAL" in out, out


def test_same_tf_inconsistent_value_area_is_demoted():
    bad = [
        {"level": 77400.0, "name": "15m VAL", "side": "support"},
        {"level": 77300.0, "name": "15m VAH", "side": "resistance"},
    ]
    prepared = _prepare_levels(bad, {}, REAL_PRICE)
    val = [p for p in prepared if "77400" in str(p["level"])][0]
    assert val["kind"] == "15m·位", val
    assert "不一致" in val["use"], val


def test_level_kind_unprefixed_names_unchanged():
    """无周期前缀的名字（如 config 的「价值区·VAH」）不得被误加前缀。"""
    label, _icon, use = _level_kind("价值区·VAH", "resistance", 77310.0, REAL_PRICE)
    assert label == "VAH" and use == "VAH上沿阻力", (label, use)


# ── P0-1 配套：结论文案不得与闸门矛盾 ──────────────────────────────────────

def _render(final_verdict, rr_a):
    return render_v96_card(
        symbol="BTCUSDT", status=final_verdict["state"], direction="wait", price=REAL_PRICE,
        high=77420.2, low=77336.7, chg=0.12, tf_lines="D🟢 · 15m⭐🟢",
        cvd_dir="卖", cvd_quality="A", taker_dir="sell", taker_ratio=1.1,
        funding_rate="0.0050%", kill_zone="非主窗口", vwap_ema={}, fg_v="68",
        levels=list(REAL_LEVELS), bearish=False,
        st_a={"entry": REAL_PRICE, "stop": REAL_PRICE - 100, "target": REAL_PRICE + 300},
        st_b={"entry": REAL_PRICE, "stop": REAL_PRICE + 100, "target": REAL_PRICE - 200},
        rr_a=rr_a, rr_b=3.404, rr_a_note="", rr_b_note="", risk_amt=100,
        leverage_text="Binance 100x", inv_line="—", prot_status="通过", data_grade="A",
        sweep_state="待扫", displacement="待判", one_reason="—", model_id="VWAP反抽",
        n5=1, eng_conf=0, klines={}, dual_indicator={"usable": True, "asset_is_crypto": True},
        final_verdict=final_verdict,
    )


def test_no_go_text_matches_real_constraint():
    """FinalVerdict=NO-GO 且 rr≥2 时，裁决行不得写「R:R不足」。"""
    txt = _render({"state": "NO-GO", "executable": False, "rr": 3.3,
                   "reason": "haldro_state_conflict"}, rr_a=3.3)
    verdict_line = [ln for ln in txt.splitlines() if ln.startswith("【裁决】")][0]
    assert "R:R不足" not in verdict_line, verdict_line
    assert "门控未通过" in verdict_line, verdict_line


def test_rr_below_two_text_still_flags_rr():
    txt = _render({"state": "WAIT", "executable": False, "rr": 0.547,
                   "reason": "rr_below_floor"}, rr_a=0.547)
    assert "R:R不足" in txt, txt


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
                passed += 1
            except AssertionError as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
                failed += 1
    print(f"\n{passed} passed / {failed} failed")
    sys.exit(1 if failed else 0)
