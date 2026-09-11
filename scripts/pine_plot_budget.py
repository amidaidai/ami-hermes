#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 TV 内部槽位口径估算绘图预算：
   TV_count ≈ series_color_plot×2 + const_color_plot×1 + fill×(1~2) + bgcolor×(1~2) + table×1
判定 series 色：color 表达式里含三元 ?、array.get(、或引用了 input.color 声明的变量。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DRAW = r"(plotcandle|plotbar|plotarrow|plotshape|plotchar|plot|bgcolor|barcolor|hline|fill|alertcondition)"
CALL = re.compile(r"(?<![\w.])" + DRAW + r"\s*\(")
INPUT_COLOR = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*input\.color\s*\(", re.M)


def split_args(s: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur); cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def analyze(path: Path):
    text = path.read_text(encoding="utf-8")
    code_lines = [l.split("//")[0] for l in text.split("\n")]
    input_colors = set(INPUT_COLOR.findall(text))

    rows = []
    total_best = total_worst = 0
    for i, l in enumerate(code_lines, 1):
        m = CALL.search(l)
        if not m:
            continue
        name = m.group(1)
        # 抓取到行尾，做括号配平拿完整调用
        frag, depth, started = "", 0, False
        for ch in l[m.start():]:
            if ch == "(":
                depth += 1; started = True
            elif ch == ")":
                depth -= 1
            frag += ch
            if started and depth == 0:
                break
        args = split_args(frag[frag.index("(") + 1: -1])
        color_expr = ""
        for a in args:
            if re.match(r"\s*color\s*=", a):
                color_expr = a.split("=", 1)[1].strip()
        series = bool(color_expr) and ("?" in color_expr or "array.get(" in color_expr
                                       or any(re.search(r"\b" + re.escape(v) + r"\b", color_expr) for v in input_colors))
        slots = 2 if series else 1
        if name in ("fill", "bgcolor", "barcolor") and series:
            slots = 2
        total_best += 1
        total_worst += slots
        rows.append((i, name, slots, color_expr[:60]))

    n_table = len(re.findall(r"table\.new\s*\(", text))
    print(f"\n=== {path.name} ===")
    print(f"绘图类声明 {len(rows)} 个；乐观(series 也按1)={total_best}  最坏(series×2)={total_worst}  + table×{n_table}")
    print(f"TV 最坏估算 ≈ {total_worst + n_table}")
    print(f"input.color 变量 {len(input_colors)} 个: {sorted(input_colors)[:12]}")
    print("--- series 色(2 槽)清单 ---")
    for i, name, slots, ce in rows:
        if slots == 2:
            print(f"  L{i:<5d} {name:<12s} {ce}")
    return total_worst + n_table


for f in sys.argv[1:]:
    analyze(Path(f))
