#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Basic Packed Bus 合同核验: 编解码往返 + 精度上界 + 旧合同拒解.

用法: python pine_packed_bus_roundtrip.py [contract=22002] [n_random=13600]

默认位段(22002 布局, 双方须逐位对齐):
    contract*1e10 + state*1e9 + priceCode*1e8 + oiDirCode*1e7 + agree*1e5 + oiPctEnc*1e0
    然后 *10 + cvdBg
  oiPctEnc = round(clamp(oiPct,-999.9,999.9)*10) + 10000   -> 恒 5 位 [10000,19999]
  agree    = min(int(oiAgreementPct), 99)                   -> 0..99, 乘 1e5 后与 oiPctEnc 无进位
  priceCode/oiDirCode = 原值 + 1                            -> 0/1/2 (0 表示 na/无向)

必查三件事:
  1. 往返无损 (边界组合 + 随机)
  2. 最大打包值 < 2^53 (float64 精确整数上限), 否则 input.source 读回会丢精度
  3. 旧合同(如 22000)必须判 invalid, 不得被静默解码成 S 状态
"""
from __future__ import annotations

import random
import sys


def encode(state, price_code, oi_dir_code, agree, oi_pct, cvd_bg, contract):
    oi_pct_enc = int(round(max(-999.9, min(999.9, oi_pct)) * 10)) + 10000
    agree_enc = min(int(agree), 99)
    base = (contract * 10000000000 + state * 1000000000 + price_code * 100000000
            + oi_dir_code * 10000000 + agree_enc * 100000 + oi_pct_enc)
    return base * 10 + cvd_bg


def decode(packed, contract):
    packed = int(round(packed))
    cvd_bg = packed % 10
    raw = packed // 10
    got_contract = raw // 10000000000
    if got_contract != contract:
        return {"valid": False, "cvdBg": cvd_bg}
    return {
        "valid": True, "cvdBg": cvd_bg, "contract": got_contract,
        "state": (raw // 1000000000) % 10,
        "price": (raw // 100000000) % 10 - 1,
        "oiDir": (raw // 10000000) % 10 - 1,
        "agree": (raw // 100000) % 100,
        "oiPct": (raw % 100000 - 10000) / 10.0,
    }


def main() -> int:
    contract = int(sys.argv[1]) if len(sys.argv) > 1 else 22002
    n_random = int(sys.argv[2]) if len(sys.argv) > 2 else 13600

    boundary = []
    for state in range(0, 5):
        for pc in range(0, 3):
            for od in range(0, 3):
                for agree in (0, 1, 50, 98, 99):
                    for pct in (-999.9, -100.0, -0.1, 0.0, 0.1, 12.3, 100.0, 999.9):
                        for bg in range(0, 5):
                            boundary.append((state, pc, od, agree, pct, bg))

    random.seed(20260910)
    rnd = [(random.randint(0, 4), random.randint(0, 2), random.randint(0, 2),
            random.randint(0, 99), random.uniform(-999.9, 999.9), random.randint(0, 4))
           for _ in range(n_random)]

    # 20260910 修正（重要）：got 必须取自 decode() 的**返回值**。
    # 旧版把输入 (state, pc, od, agree, bg) 原样搬进 got，只有 oiPct 真的来自解码——
    # 其余五个字段恒等自比，测试会全绿却什么都没证明。
    # 方向字段还有语义偏移：AggVol 编码 priceCode/oiDirCode = 语义方向 + 1，
    # SVP 解码时 %10 - 1 还原成 -1/0/1，所以往返比对要用 (pc-1)/(od-1)。
    fails = []
    max_packed = 0
    for (state, pc, od, agree, pct, bg) in boundary + rnd:
        packed = encode(state, pc, od, agree, pct, bg, contract)
        max_packed = max(max_packed, packed)
        d = decode(packed, contract)
        want = (state, pc - 1, od - 1, min(int(agree), 99),
                round(max(-999.9, min(999.9, pct)) * 10) / 10.0, bg)
        got = ((d.get("state"), d.get("price"), d.get("oiDir"), d.get("agree"),
                round(d.get("oiPct", 0.0), 1), d.get("cvdBg")) if d["valid"] else None)
        if got != want:
            fails.append((want, d))

    total = len(boundary) + len(rnd)
    print(f"[bus] 样本 {total} 组, 失败 {len(fails)} 组（比对的是解码值，不是输入值）")
    print(f"[bus] 最大打包值 {max_packed} < 2^53 {2 ** 53} -> {max_packed < 2 ** 53}")
    old = (contract - 2) * 10000000000
    print(f"[bus] 旧合同 {contract - 2} -> {decode(old, contract)}")
    if fails:
        print("[bus] 前 3 反例:", fails[:3])
    return 1 if fails or max_packed >= 2 ** 53 else 0


if __name__ == "__main__":
    raise SystemExit(main())
