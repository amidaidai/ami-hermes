# -*- coding: utf-8 -*-
"""Pine 绘图槽位预算估算器 —— TradingView「脚本创建了太多绘图(N)。限制为64」的预检闸门。

为什么必须用它
--------------
TV 的 64 硬上限**不按 plot() 调用数计**。内部口径近似：

    TV_count ≈ series_color_plot × 2 + const_color_plot × 1
             + fill(1~2) + bgcolor(1~2) + barcolor(1~2)
             + table.new × 1

判定 series 色（→ 占 2 槽）的充分条件，只要 color= 表达式里含：
  · 三元 ?        （即使两个分支都是常量色，条件为 series，结果就是 series 色）
  · array.get(...)
  · 引用了 input.color() 声明的变量
字面 hex(#RRGGBB) / color.green / color.new(#RRGGBB, n) 常量 → 1 槽。

grep 数 plot( 个数会严重低估。2026-09-10 实案：本地按调用数估 45/64，TV 实际 65/64 直接报错。

用法
----
    python pine_plot_budget.py FILE.pine [FILE2.pine ...]

输出：每文件绘图声明数 / 按 TV 口径的估算槽位 / 距 64 的余量 / 逐条 series 色清单。
退出码：任一文件估算超过安全线则 1，否则 0 —— 可直接当交付闸门。

校准（重要）
------------
本仓库实测偏移稳定：TV_actual ≈ estimate + OFFSET，OFFSET = 4。
    AggVol v4  估 59 -> 实 63  ✓
    AggVol v5  估 61 -> 实 65  ✗ 超限
    AggVol v6  估 58 -> 预计 62 ✓
所以 SAFE_TARGET 默认 59（59 + 4 = 63 <= 64，留 1 槽）。
若脚本特性变化（新增 plotcandle、大量 table、大批 series 色 plot），偏移可能漂移，
需用一次真实报错/成功反推重新校准 OFFSET。

配套省槽手段见 references/aggvol-plot-slot-crisis-20260910.md。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

TV_HARD_LIMIT = 64
OFFSET = 4
SAFE_TARGET = 59

DRAW = r'(plotcandle|plotbar|plotarrow|plotshape|plotchar|plot|bgcolor|barcolor|hline|fill|alertcondition)'
CALL = re.compile(r'(?<![\w.])' + DRAW + r'\s*\(')
INPUT_COLOR = re.compile(r'^\s*([A-Za-z_]\w*)\s*=\s*input\.color\s*\(', re.M)
STRING_LIT = re.compile(r'[\'"]([^\'"]+)[\'"]')


def split_top(s: str) -> list:
    '按顶层逗号切分，忽略括号/方括号内的逗号。'
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    out.append(cur)
    return out


def balanced(line: str, lparen: int) -> str:
    '从 lparen（左括号下标）取到配平的右括号，返回整段调用文本。'
    depth, started, frag = 0, False, ''
    for ch in line[lparen:]:
        if ch == '(':
            depth += 1
            started = True
        elif ch == ')':
            depth -= 1
        frag += ch
        if started and depth == 0:
            break
    return frag


def analyze(path: Path) -> int:
    text = path.read_text(encoding='utf-8')
    lines = [l.split('//')[0] for l in text.split(chr(10))]  # 去注释再统计
    input_colors = set(INPUT_COLOR.findall(text))

    decls, const_n, series_rows = 0, 0, []
    for i, l in enumerate(lines, 1):
        m = CALL.search(l)
        if not m:
            continue
        decls += 1
        call = balanced(l, m.end() - 1)
        inner = call[call.index('(') + 1:]
        if inner.endswith(')'):
            inner = inner[:-1]
        color_expr = ''
        for a in split_top(inner):
            if re.match(r'\s*color\s*=', a):
                color_expr = a.split('=', 1)[1].strip()
        is_series = bool(color_expr) and (
            '?' in color_expr
            or 'array.get(' in color_expr
            or any(re.search(r'\b' + re.escape(v) + r'\b', color_expr) for v in input_colors)
        )
        if is_series:
            found = STRING_LIT.search(call)
            series_rows.append((i, m.group(1), color_expr[:64], found.group(1) if found else ''))
        else:
            const_n += 1

    n_table = len(re.findall(r'table\.new\s*\(', text))
    estimate = decls + len(series_rows) + n_table
    tv = estimate + OFFSET
    ok = estimate <= SAFE_TARGET

    print()
    print('=== ' + path.name + ' ===')
    print('绘图声明 ' + str(decls) + '   常量色 ' + str(const_n)
          + '   series 色 ' + str(len(series_rows)) + '(各占2)   table ' + str(n_table))
    verdict = '✓ 有余量' if ok else '✗ 逼近/超限，先省槽再谈新增'
    print('估算槽位 ' + str(estimate) + '  ->  预计 TV ' + str(tv) + '/' + str(TV_HARD_LIMIT)
          + '   ' + verdict + '   (安全线 estimate <= ' + str(SAFE_TARGET) + ')')
    if series_rows:
        print('--- series 色（各占 2 槽；改成字面 hex 常量可各省 1 槽，但有用户可见代价，须先问）---')
        for ln, kind, expr, title in series_rows:
            print('  L' + str(ln).ljust(5) + kind.ljust(12) + title[:26].ljust(28) + expr)
    return 0 if ok else 1


def main(argv: list) -> int:
    if not argv:
        print(__doc__)
        return 2
    rc = 0
    for f in argv:
        p = Path(f)
        if not p.exists():
            print('!! 找不到 ' + f)
            rc = 2
            continue
        rc |= analyze(p)
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
