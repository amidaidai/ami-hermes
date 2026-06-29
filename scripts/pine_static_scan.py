#!/usr/bin/env python3
"""Pine 指标静态扫描 — 审计第 0 步，一次性输出所有客观指标。
用法: python pine_static_scan.py <指标文件.txt> [更多文件...]

输出: request.security 调用点 / plot 计数 / line-box-label 计数 /
      typed-def 重复(注意函数内局部变量是误报) / 关键变量 def 顺序 / 重绘信号。
人工只需对照阈值判读, 不必逐行通读。"""
import re
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEFPAT = re.compile(
    r'^\s*(?:var\s+)?(?:float|int|bool|string|color|line|box|label|table)\s+([A-Za-z_]\w*)\s*=')

# 关键变量必须先定义后引用 (def-before-use), 行号须严格递增
ORDER_CHAIN = ['pdPos', 'pdShort', 'kzShort', 'sweepCntText', 'dmiCompact',
               'actionBiasWord', 'panelEntryVal', 'actionStateText',
               'concTextCol', 'panelDirVal']


def scan(path):
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
    print(f"\n===== {path}  ({len(lines)} lines) =====")

    reqs = [(i, l.strip()) for i, l in enumerate(lines, 1)
            if 'request.security' in l and not l.strip().startswith('//')]
    print(f"[配额] request.security 调用点: {len(reqs)}  (上限 40; 函数被调 N 次 = N×函数内 req 数)")
    for i, l in reqs:
        print(f"   L{i}: {l[:100]}")

    plots = [i for i, l in enumerate(lines, 1) if re.match(r'\s*plot\(', l)]
    objs = sum(1 for l in lines if re.search(r'line\.new|box\.new|label\.new', l))
    print(f"[绘制] plot: {len(plots)} (<64)   line/box/label.new: {objs} (各<500)")

    # typed-def 重复 —— 函数内/循环内局部变量会误报, 需人工按行号判别作用域
    seen, dups = {}, []
    for i, l in enumerate(lines, 1):
        m = DEFPAT.match(l)
        if m:
            v = m.group(1)
            if v in seen:
                dups.append((v, seen[v], i))
            else:
                seen[v] = i
    print(f"[重复def] {dups if dups else 'none'}")
    print("   ⚠ 单字母/局部名(i,j,sec,v,eFast...)落在 f_xxx()=> 或 for 内 = 合法局部, 误报勿改")

    pos = {}
    for v in ORDER_CHAIN:
        for i, l in enumerate(lines, 1):
            if re.match(r'\s*(?:var\s+)?(?:float|int|bool|string|color)\s+' + re.escape(v) + r'\b', l):
                pos[v] = i
                break
    found = [(v, pos[v]) for v in ORDER_CHAIN if v in pos]
    bad = [found[k] for k in range(1, len(found)) if found[k][1] < found[k-1][1]]
    print(f"[def顺序] {found}")
    print(f"   def-before-use 违例: {bad if bad else 'none'}")

    rep = [(i, l.strip()[:90]) for i, l in enumerate(lines, 1)
           if re.search(r'lookahead|closeReclaim', l) or 'isSwept :=' in l]
    print(f"[重绘] lookahead/closeReclaim/isSwept 信号点: {len(rep)}")
    for i, l in rep:
        print(f"   L{i}: {l}")
    print("   规则: lookahead_on + [1]/[3] 已收柱偏移 = 非重绘正确写法, 勿标 P0")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for p in sys.argv[1:]:
        scan(p)
