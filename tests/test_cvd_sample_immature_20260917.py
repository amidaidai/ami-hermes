"""20260917 修复回归：CVD 低周期样本未成熟（bit128/2048）不得被当作行情否决。

背景（证据链）：
- Pine SVP 旧式 `((not cvdQualityOk or cvdLowSample) ? 2 : 0)` 把「1m 样本没攒够」
  与「行情质量真的差」合并成同一个码。
- 15m 图 + 1m 低周期、CVD_MIN_SAMPLES=5 时，每根 15m K 线前 5 分钟 cvdLowSample 必然为真。
- 影子账本 499 条信号中 43.9% 落在该窗口（+0..+4min），被误判为质量否决。
- 修复：Pine 拆出 bit128（Quality）/ bit2048（NoTrade）；decision_loop 只对
  非样本位落 wait；auto_card 影子账本增加 cvd_sample_mature 标记。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from decision_loop import resolve_final_verdict  # noqa: E402
from decision_regime import classify_decision_regime  # noqa: E402
from tv_indicator_contract import (  # noqa: E402
    NO_TRADE_BITS,
    decode_no_trade,
    decode_quality_code,
)


def _trend():
    return classify_decision_regime(
        adx=30, atr_ratio=1.0, ema_spread_atr=0.7,
        vwap_crosses_20=1, va_stay_ratio_20=0.2,
        displacement_atr=0.8, rvol=1.1,
    )


def _main(**overrides):
    data = {
        "grade": "A多", "direction": "long", "model_id": "fvg_pullback",
        "entry": 100.0, "stop": 98.0, "target": 105.0, "rr": 2.5,
        "mcp_fvg_quality_score": 82.0, "mcp_ob_quality_score": 70.0,
        "data_grade": "A", "snapshot_age_sec": 10.0,
        "location_valid": True, "trigger_confirmed": True, "bar_closed": True,
        "mcp_cvd_method_code": 1,
    }
    data.update(overrides)
    return data


def _dual(valid_code=2, conflict=False, **overrides):
    data = {
        "asset_is_crypto": True, "valid_code": valid_code, "conflict": conflict,
        "aligned": not conflict, "risk_code": 0,
    }
    data.update(overrides)
    return data


def _verdict(main_overrides):
    return resolve_final_verdict(
        "BTCUSDT", _main(**main_overrides), _dual(),
        regime=_trend(),
        risk={"allowed": True, "violations": [], "risk_usd": 1.0},
        advanced={"gate": {"execute": True}},
    )


# —— 契约解码层 ——

def test_contract_bit128_means_sample_immature():
    q = decode_quality_code(128)
    assert q["cvdSampleImmature"] is True
    assert q["cvdLowQuality"] is False
    assert q["raw"] == 128


def test_contract_bit2_is_still_low_quality():
    q = decode_quality_code(2)
    assert q["cvdLowQuality"] is True
    assert q["cvdSampleImmature"] is False


def test_contract_bit130_is_both():
    q = decode_quality_code(130)
    assert q["cvdLowQuality"] is True
    assert q["cvdSampleImmature"] is True


def test_contract_no_trade_2048_registered():
    assert 2048 in NO_TRADE_BITS
    assert decode_no_trade(2048) == ["CVD样本未成熟·待定"]


def test_contract_no_trade_1056_unchanged():
    # 现场实测值（2026-09-17 11:30）：32=CVD质量不达标 + 1024=副指标冲突/降权
    assert decode_no_trade(1056) == ["CVD质量不达标", "副指标冲突/降权"]


# —— 决策层：quality code ——

def test_quality_bit128_only_does_not_wait():
    out = _verdict({"mcp_quality_code": 128})
    assert "svp_quality_code" not in out.blockers
    assert any("svp_quality_pending" in w for w in out.warnings)


def test_quality_bit2_still_waits_regression():
    out = _verdict({"mcp_quality_code": 2})
    assert "svp_quality_code" in out.blockers


def test_quality_bit128_plus_bit2_still_waits():
    out = _verdict({"mcp_quality_code": 130})
    assert "svp_quality_code" in out.blockers


def test_quality_bit128_plus_other_bits_still_waits():
    # 128（样本未成熟）+ 4（低流动性）→ 低流动性是真原因，必须等
    out = _verdict({"mcp_quality_code": 132})
    assert "svp_quality_code" in out.blockers


def test_quality_zero_still_no_wait_regression():
    out = _verdict({"mcp_quality_code": 0})
    assert "svp_quality_code" not in out.blockers


# —— 决策层：no trade reason ——

def test_no_trade_bit2048_only_does_not_wait():
    out = _verdict({"mcp_no_trade_reason_code": 2048})
    assert "svp_no_trade_reason" not in out.blockers
    assert any("svp_no_trade_pending" in w for w in out.warnings)


def test_no_trade_1056_still_waits_regression():
    out = _verdict({"mcp_no_trade_reason_code": 1056})
    assert "svp_no_trade_reason" in out.blockers


def test_no_trade_bit2048_with_real_reason_still_waits():
    # 2048（样本未成熟）+ 256（本根未收线）→ 未收线是真原因，必须等
    out = _verdict({"mcp_no_trade_reason_code": 2304})
    assert "svp_no_trade_reason" in out.blockers


def test_no_trade_bit32_alone_still_waits():
    out = _verdict({"mcp_no_trade_reason_code": 32})
    assert "svp_no_trade_reason" in out.blockers
