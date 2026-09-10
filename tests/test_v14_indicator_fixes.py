#!/usr/bin/env python3
"""v14 指标修复的系统侧回归（对应用户给的 GPT-5.6 审计 F16 / F05）。

钉子：
  F16 Trigger Pack 低位偏移 +1→+3，X 态不再借位；全组合往返一致。
  F05 合同 22003 起 oiPctEnc==0 表示「OI 缺失」，与「持平 0.00%」可区分；22002 向后兼容。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tv_indicator_contract as C


def enc_trigger(code, age, fresh, state):
    """与 Pine 侧 (triggerCode+10)*1e5 + age*100 + fresh*10 + (signalState+3) 同式。"""
    return (code + 10) * 100000 + min(age, 999) * 100 + (10 if fresh else 0) + (state + 3)


def enc_bus(contract, state, price_code, oi_dir_code, agree, oi_pct, cvd):
    oi = 0 if oi_pct is None else int(round(oi_pct * 10)) + 10000
    return (contract * 10 ** 10 + state * 10 ** 9 + price_code * 10 ** 8
            + oi_dir_code * 10 ** 7 + agree * 10 ** 5 + oi) * 10 + cvd


# ── F16 ──────────────────────────────────────────────────────────────

def test_trigger_pack_round_trip_all_states():
    for state in (-2, -1, 0, 1, 2, 3, 4):
        for code in (-7, -5, -2, -1, 0, 1, 2, 5, 7):
            for age in (0, 1, 3, 999):
                for fresh in (False, True):
                    d = C.decode_trigger_pack(enc_trigger(code, age, fresh, state))
                    assert d == {"triggerCode": code, "age": age,
                                 "fresh": fresh, "signalState": state}, (code, age, fresh, state, d)


def test_trigger_pack_never_negative_low_digit():
    """修复的本质：最低位恒非负，不会向十位借位。"""
    for state in (-2, -1, 0, 1, 2, 3, 4):
        pack = enc_trigger(0, 999, False, state)
        assert pack % 10 >= 0
        assert C.decode_trigger_pack(pack)["age"] == 999
        assert C.decode_trigger_pack(pack)["fresh"] is False


def test_x_state_old_bug_pack_would_have_borrowed():
    """旧编码（+1）在 X 态的典型包 1099899 会被拆成 998/9/——修复前的实际后果。"""
    old = (0 + 10) * 100000 + 999 * 100 + 0 + (-2 + 1)   # = 1099899
    assert old == 1099899
    d = C.decode_trigger_pack(old)
    assert (d["age"], d["fresh"]) == (998, False)   # 年龄被借位吃掉 1


def test_trigger_state_range_documented():
    """signalState 域 -2..4（X=-2、无向=0、几何=-1、未收线=1、B/C=2、A执行=3、不新鲜=4）。"""
    assert C.decode_trigger_pack(enc_trigger(0, 0, False, -2))["signalState"] == -2
    assert C.decode_trigger_pack(enc_trigger(0, 0, False, 4))["signalState"] == 4


# ── F05 ──────────────────────────────────────────────────────────────

def test_bus_new_contract_distinguishes_missing_oi_from_flat():
    missing = C.decode_basic_bus(enc_bus(22003, 4, 2, 2, 99, None, 2))
    flat = C.decode_basic_bus(enc_bus(22003, 4, 2, 2, 99, 0.0, 2))
    assert missing["oi_present"] is False and missing["oiPct"] is None
    assert flat["oi_present"] is True and flat["oiPct"] == 0.0


def test_bus_old_contract_keeps_zero_meaning_zero_percent():
    d = C.decode_basic_bus(enc_bus(22002, 4, 2, 2, 99, 0.0, 2))
    assert d["contract"] == 22002 and d["valid"] is True
    assert d["oi_present"] is True and d["oiPct"] == 0.0


def test_bus_values_round_trip():
    for pct in (-999.9, -3.4, 0.0, 2.1, 999.9):
        d = C.decode_basic_bus(enc_bus(22003, 4, 2, 2, 99, pct, 2))
        assert d["oiPct"] == pct, (pct, d["oiPct"])
        assert d["state"] == 4 and d["oiAgree"] == 99 and d["cvdBg"] == 2


def test_bus_contract_accepts_both_versions():
    assert C.decode_basic_bus(enc_bus(22002, 1, 2, 2, 50, 1.0, 0))["valid"] is True
    assert C.decode_basic_bus(enc_bus(22003, 1, 2, 2, 50, 1.0, 0))["valid"] is True
    assert C.decode_basic_bus(enc_bus(22000, 1, 2, 2, 50, 1.0, 0))["valid"] is False


def test_bus_max_value_stays_below_float53():
    """不换位设计的理由：上移合同号会越过 2^53，整数精度会崩。"""
    from math import inf
    # 最大合法：oiPct 字段最大值 19999（即 +999.9%），state 4，价格码 2，方向码 2，一致 99，cvd 4
    max_pack = (22003 * 10 ** 10 + 4 * 10 ** 9 + 2 * 10 ** 8 + 2 * 10 ** 7
                + 99 * 10 ** 5 + 19999) * 10 + 4
    assert max_pack < 2 ** 53, max_pack
    d = C.decode_basic_bus(max_pack)
    assert d["contract"] == 22003 and d["oiPct"] == 999.9
    # 若按「上移合同号」的方案（22003 * 1e12），就会越界：
    assert 22003 * 10 ** 12 > 2 ** 53


def test_contract_version_bumped():
    assert C.CONTRACT_VERSION == "v14"
