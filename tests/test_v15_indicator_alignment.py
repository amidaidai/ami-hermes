#!/usr/bin/env python3
"""v16/v15 指标 ↔ 分析流程/分析卡 的对齐回归。

钉子（对应 2026-09-11 的指标定版）：
  F17  Coverage Feed Mode 四态：1聚合 / 2回退单图 / 3单源不参与协同 / 4异常。
       单源(3) 是设计内降级，不是异常(4)；旧码把 Single 也报成异常，语义相反。
  F05  合同 22003 起 oiPctEnc==0 = OI 缺失，与「持平 0.00%」必须可区分。
  F16  Trigger Pack 状态位偏移 +3（decode_trigger_pack 已覆盖，这里回归防护）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tv_indicator_contract as C


# ── F17 数据源四态 ───────────────────────────────────────────────────

def test_feed_mode_four_states():
    assert C.decode_feed_mode(1)["text"] == "聚合"
    assert C.decode_feed_mode(2)["text"] == "回退单图"
    assert C.decode_feed_mode(3)["text"] == "单源·不参与协同"
    assert C.decode_feed_mode(4)["text"] == "异常"


def test_single_is_not_abnormal():
    """旧码把 Single 落到 4（异常）。这条钉住两者必须分开。"""
    single, abnormal = C.decode_feed_mode(3), C.decode_feed_mode(4)
    assert single["single"] is True and single["abnormal"] is False
    assert abnormal["abnormal"] is True and abnormal["single"] is False


def test_feed_mode_usability_matches_indicator_side():
    """指标侧 haldroUsableA = 使用聚合 or 回退 → 只有 1/2 可用。"""
    assert C.decode_feed_mode(1)["usable"] is True
    assert C.decode_feed_mode(2)["usable"] is True
    assert C.decode_feed_mode(3)["usable"] is False
    assert C.decode_feed_mode(4)["usable"] is False


def test_feed_mode_tail_is_quiet_when_normal():
    """正常聚合态不撑宽卡面；非聚合态才标注。"""
    assert C.feed_mode_tail(1) == ""
    assert "单源" in C.feed_mode_tail(3)
    assert "回退" in C.feed_mode_tail(2)
    assert "异常" in C.feed_mode_tail(4)


def test_feed_mode_missing_and_unknown_never_crash():
    for bad in (None, "", "abc", -1):
        d = C.decode_feed_mode(bad)
        assert d["usable"] is False
        assert d["mode"] is None or isinstance(d["mode"], int)


# ── F05 OI 缺失 ──────────────────────────────────────────────────────

def _bus(contract, oi_pct, state=4):
    """按 Pine 侧编码构造总线：contract*1e11 + state*1e10 + ... + oiPct*10 + cvd。"""
    oi = 0 if oi_pct is None else int(round(oi_pct * 10)) + 10000
    return (contract * 10 ** 10 + state * 10 ** 9 + 2 * 10 ** 8 + 2 * 10 ** 7 + 99 * 10 ** 5 + oi) * 10 + 2


def test_oi_missing_differs_from_flat_on_new_contract():
    miss = C.decode_oi_presence(_bus(22003, None))
    flat = C.decode_oi_presence(_bus(22003, 0.0))
    assert miss["present"] is False and miss["pct"] is None and miss["text"] == "OI缺失"
    assert flat["present"] is True and flat["pct"] == 0.0 and flat["text"] == ""


def test_oi_old_contract_keeps_zero_as_flat():
    """向后兼容：22002 的 0 仍代表 0.00%，不能报成缺失。"""
    d = C.decode_oi_presence(_bus(22002, 0.0))
    assert d["present"] is True and d["pct"] == 0.0


def test_oi_unwired_reports_not_connected():
    """总线没接（合同不是 22002/22003）→ 必须说「未接」，不能说「缺失」或「持平」。"""
    d = C.decode_oi_presence(_bus(22000, 1.0))
    assert d["present"] is False and d["text"] == "OI未接"


def test_supported_contract_versions():
    assert C.SUPPORTED_CONTRACT_VERSIONS == (22002, 22003)
    assert C.CONTRACT_CURRENT == 22003
    assert C.CONTRACT_NON_CRYPTO == 22000


# ── F16 回归防护（状态位偏移 +3）────────────────────────────────────

def test_trigger_pack_x_state_round_trip_after_row_rework():
    """行优化不该动打包编码：X 态仍解出 signalState=-2、age=999。"""
    pack = (0 + 10) * 100000 + 999 * 100 + 0 + (-2 + 3)
    d = C.decode_trigger_pack(pack)
    assert d["signalState"] == -2 and d["age"] == 999 and d["fresh"] is False
