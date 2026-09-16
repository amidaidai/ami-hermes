#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""价格/数值格式化的唯一实现（2026-09-16 抽出）。

背景：原生卡（`render_v96._num`）在 2026-09-13 修好了外汇精度
（|v|∈[0.01,10) 保留 4 位小数），但重排层 `card_reformat` 仍各自用
`f"{v:,.0f}"`，于是同一张 EURUSD 卡在重排后变成「1.1638 → 1」——
上游修好、下游又取整。两张卡必须共用同一个精度函数，本模块即唯一定义处。

调用方：
- `scripts/render_v96.py::_num`（原生卡所有价位/读数）
- `scripts/card_reformat.py`（v7 表格版首行、区间边、关键位、远端位）
"""
from __future__ import annotations


def fmt_rr(v, gate: float = 2.0) -> str:
    """R:R 显示 —— 决策带 [1.5, 2.05] 内给 2 位小数，其余 1 位。

    2026-09-16：闸门用 ``rr_a >= 2.0`` 判绿，显示却一律 ``:.1f`` —— rr_a=1.96 时
    同一张卡同时出现「R:R不足(<1:2)」和「当前主线1:2.0」。临界值必须能读出真实值，
    才能判断是显示问题还是闸门误判（实测该组合只可能来自 1 位小数四舍五入）。
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    if 1.5 <= f <= 2.05 or abs(f - gate) < 0.05:
        return f"1:{f:.2f}"
    return f"1:{f:.1f}"


def fmt_price(v, digits: int = 0) -> str:
    """按量级选择小数位；非法输入返回 ``—``。

    规则（与 2026-09-13 起的原生卡口径一致）：
    - ``>= 1000``：0 位小数 + 千分位（BTC/XAU/指数）
    - 显式 ``digits``：按指定小数位
    - |v| ∈ [0.01, 10)：4 位小数（外汇/小额价格）
    - 0 < |v| < 0.01：6 位小数并去尾零（小市值币种）
    - 其余：2 位小数
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    if f >= 1000:
        return f"{f:,.0f}"
    if digits:
        return f"{f:,.{digits}f}"
    a = abs(f)
    if 0.01 <= a < 10:
        # 2026-09-13 FX 精度修复：2 位小数不够——EURUSD 1.1638 曾显示成 "1.16"。
        return f"{f:.4f}"
    if 0 < a < 0.01:
        return f"{f:.6f}".rstrip("0").rstrip(".")
    return f"{f:.2f}"
