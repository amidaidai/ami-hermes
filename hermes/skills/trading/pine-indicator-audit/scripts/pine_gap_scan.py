#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""computed-but-unrendered 可达性扫描（Pine 行动格内容缺口）。

用法:
    python scripts/pine_gap_scan.py <a.pine> [b.pine ...]

做的是什么：
    把脚本里所有赋值（`=` 与 `:=`，含 `var` 前缀）建成「变量 -> 它引用了谁」的有向图，
    以【渲染点】为根做反向可达。不可达的变量 = 算了但用户看不到 = 内容缺口候选。
    这与「数读取次数的死变量启发式」不同：那套只看某个名字被写了几次、读了几次，
    抓不到「被算出来又被另一个同样不被渲染的变量消费」的整条链。

根集合（缺一不可，2026-09-10 实案踩过）:
    - 副指标面板:  table.cell(...)
    - 主指标面板:  array.push(rowVals, X) / array.push(rowLabs, X)
                   （漏掉这两个 -> 整条 prevCompactText 链被误判为死）
    - 绘图:        plot / plotshape / plotcandle / plotbar / plotchar / bgcolor / hline / fill

已知限制（务必人工过滤再交付）:
    - UDT 方法体、循环局部量、`this.xxx` 字段、input 常量会产生大量假阳性；
    - 输出会很长（大脚本可达数百条）。按「用户可见的一行/一格」筛完再给人看。

2026-09-10 用它抓到的真实缺口（供校准期望）:
    lastWatchSide  var int lastWatchSide = 0   声明后从未渲染（用了 var 前缀，旧扫描器漏抓）
    oiCloseA       v6 删掉唯一消费者后成为孤儿
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ASSIGN = re.compile(
    r"^\s*(?:var\s+|varip\s+)?"
    r"(?:string|bool|float|int|color|array<\w+>|line|label|box|table)?\s*"
    r"([A-Za-z_]\w*)\s*(?::=|=)(?!=)"
)
IDENT = re.compile(r"(?<![\w.])([A-Za-z_]\w*)(?![\w])")
DRAW = re.compile(
    r"(?<![\w.])(plot|plotshape|plotcandle|plotbar|plotchar|bgcolor|hline|fill|alertcondition)\s*\("
)

# Pine 关键字 / 内置 / 常见局部名，避免噪声
BUILTIN = set("""
and or not if else for while var varip na nz math ta request str array color input plot
plotshape plotcandle plotbar plotchar bgcolor hline fill alertcondition table barstate
syminfo timeframe open high low close volume time int float bool string bar_index true false
line label box size shape location display format extend xloc position text chart
period tr le sa simple series const security
""".split())


def scan(path: Path) -> list[tuple[int, str, str]]:
    src = path.read_text(encoding="utf-8")
    lines = [l.split("//")[0] for l in src.split("\n")]

    uses: dict[str, set[str]] = {}
    defline: dict[str, int] = {}
    for i, l in enumerate(lines, 1):
        m = ASSIGN.match(l)
        if not m:
            continue
        name = m.group(1)
        if name in ("if", "else", "for", "while", "and", "or", "not"):
            continue
        uses.setdefault(name, set()).update(IDENT.findall(l[m.end():]))
        defline.setdefault(name, i)

    # 根：任何进入表格 / 绘图的引用
    live: set[str] = set()
    for l in lines:
        if ("table.cell(" in l or "array.push(rowVals," in l or "array.push(rowLabs," in l
                or DRAW.search(l)):
            live |= set(IDENT.findall(l))

    changed = True
    while changed:
        changed = False
        for k in list(live):
            for r in uses.get(k, ()):
                if r not in live:
                    live.add(r)
                    changed = True

    dead = []
    for name, ln in sorted(defline.items(), key=lambda kv: kv[1]):
        if name in live or name in BUILTIN or name.isupper() or len(name) <= 2:
            continue
        dead.append((ln, name, lines[ln - 1].strip()))
    return dead


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    for f in argv[1:]:
        p = Path(f)
        dead = scan(p)
        print(f"\n=== {p.name} ===")
        print(f"'算了但进不了表格/绘图' 候选 {len(dead)} 个（先人工筛，别原样交付）")
        for ln, name, txt in dead:
            print(f"  L{ln:<6d} {txt[:165]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
